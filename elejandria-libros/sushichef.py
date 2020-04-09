#!/usr/bin/env python
import cgi
import logging
import os
import requests
import scrapy
import shutil

from twisted.internet import reactor
from scrapy.crawler import CrawlerRunner

from le_utils.constants.licenses import PUBLIC_DOMAIN

from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import setup_logging
from ricecooker.exceptions import raise_for_invalid_channel
from scrapy.utils.log import configure_logging


# Run constants
################################################################################
CHANNEL_NAME = "Elejandria Libros"  # Name of channel
CHANNEL_SOURCE_ID = "elejandria-libros"  # Channel's unique id
CHANNEL_DOMAIN = "elejandria.com"  # Who is providing the content
CHANNEL_LANGUAGE = "es"  # Language of channel
CHANNEL_DESCRIPTION = "Elejandria es un sitio web que ofrece libros gratis de dominio público o publicados bajo licencias abiertas. La mayoría de los autores son clásicos de la literatura unviersal, pero también podrás descargar gratis libros de dominio público actuales con licencias de libre distribución."
CHANNEL_THUMBNAIL = (
    "channel_thumbnail.png"  # Local path or url to image file (optional)
)

# Additional constants
################################################################################

START_URL = "https://www.elejandria.com/colecciones"

DEBUG = True

DOWNLOADED_FILES_DIR = "downloads/"


logger = logging.getLogger(__name__)

setup_logging(
    level=logging.DEBUG if DEBUG else logging.INFO,
    error_log="errors.log",
    add_loggers=["scrapy"],
)

# The node tree that will finally be appended to the ChannelNode
NODE_TREE = []

# Maps nodes to URLs that should be downloaded and added after crawling
DOWNLOAD_JOBS = []


class DownloadJob:
    def __init__(self, node, file_cls, url):
        """
        node: the DocumentNode to create File object on
        file_cls: a class, either DocumentFile or EPubFile
        url: where to get the file from
        """
        self.file_cls = file_cls
        self.url = url
        self.node = node

    def download(self):
        logger.debug("Now downloading {}".format(self.url))
        save_path = download_file(self.url)
        instance = self.file_cls(save_path)
        self.node.add_file(instance)


def download_file(location, destdir=DOWNLOADED_FILES_DIR):
    """
    Copied from another chef.
    
    TODO: Add caching to avoid re-downloads?
    """
    response = requests.get(location, stream=True)

    filename_base = location.split("/")[-1]

    if response.status_code == 200:

        # TODO: Can this be shortened?
        _, params = cgi.parse_header(response.headers["Content-Disposition"])
        original_filename = params["filename"]
        filename_ext = original_filename.split(".")[-1]
        destination_filename = ".".join((filename_base, filename_ext))

        logger.debug("Fetching {} and storing as {}")

        out_path = os.path.join(destdir, destination_filename)

        if DEBUG and os.path.exists(out_path):
            logger.debug("Skipping {}, already downloaded".format(out_path))
        else:
            with open(out_path, "wb") as outf:
                shutil.copyfileobj(response.raw, outf)
            file_size_mb = os.path.getsize(out_path) / 1024.0 / 1024.0
            logger.info("Saved file {} of size {} MB".format(out_path, file_size_mb))
        return out_path

    else:
        logger.warning(
            "HTTP status {}, downloading: {}".format(response.status_code, location)
        )
        return None


class ElejandriaLibrosSpider(scrapy.Spider):

    name = "elejandria-base-collections-spider"
    start_urls = [START_URL]

    def __init__(self):
        super().__init__()

    def parse(self, response):
        """
        Parses collections on the main page.
        For each collection:
        
        * Create a TopicNode and append to Ricecooker tree
        * Spawn parsing for each collection 
        """
        logger.debug("Parsing collection base page: {}".format(response.url))
        for collection_link in response.css(".book-description h2 a"):
            title = collection_link.css("::text").get()
            url = collection_link.attrib["href"]
            logger.debug("Found collection with title: {}".format(title))
            ricecooker_node = nodes.TopicNode(title=title, source_id=url,)
            NODE_TREE.append(ricecooker_node)
            request = scrapy.Request(
                collection_link.attrib["href"],
                callback=self.parse_collection,
                cb_kwargs={"node": ricecooker_node},
            )
            yield request

    def parse_collection(self, response, node):
        """
        Example:
        https://www.elejandria.com/coleccion/descargar-gratis-20-libros-clasicos-para-sobrellevar-la-cuarentena
        """
        logger.debug('Parsing collection "{}": {}'.format(node.title, response.url))
        for book_link in response.css(".book div p a.primary-text-color"):
            url = book_link.attrib["href"]
            title = book_link.css("::text").get()
            logger.debug("Found book link: {} - ".format(title))
            request = scrapy.Request(
                url, callback=self.parse_book, cb_kwargs={"node": node}
            )
            yield request

    def parse_book(self, response, node):
        """
        Example:
        https://www.elejandria.com/libro/alicia-en-el-pais-de-las-maravillas/carroll-lewis/94
        """
        logger.debug("Parsing book page: {}".format(node.title, response.url))

        book_title = response.css("h1.bordered-heading::text").get()
        author = response.css("h2 a.secondary-text-color::text").get()
        thumbnail = response.css("img.img-book-cover::attr(src)").get()

        # Fetch a description based on all the text in P containers
        # There aren't really any semantic tags around this, so it's
        # probably going to break some day...
        description = "\n\n".join(
            response.css(
                "div.col-lg-8 div.row div.offset-top div.text-justify p::text"
            ).getall()
        )

        document_node = nodes.DocumentNode(
            source_id=response.url,
            title=book_title,
            license=licenses.get_license(PUBLIC_DOMAIN),
            author=author,
            provider=CHANNEL_NAME,
            description=description,
            thumbnail=thumbnail,
            derive_thumbnail=True,
            files=[],
        )
        node.add_child(document_node)

        versions = {}
        for download_button in response.css("a.download-link"):
            button_text = download_button.css("::text").get() or ""
            url = download_button.attrib["href"]
            if "ePub" in button_text:
                versions["ePub"] = url
            elif "PDF" in button_text:
                versions["PDF"] = url

        # Prefer ePub, fall back to PDF
        file_cls = None
        url = None
        if "ePub" in versions:
            url = versions["ePub"]
            file_cls = files.EPubFile
        elif "PDF" in versions:
            url = versions["PDF"]
            file_cls = files.DocumentFile
        else:
            logger.error("No PDF or ePub version found: {}".format(response.url))
            return

        request = scrapy.Request(
            url,
            callback=self.parse_download,
            cb_kwargs={"node": document_node, "file_cls": file_cls},
        )
        yield request

    def parse_download(self, response, node, file_cls):
        logger.debug("Downloading ePub: {}".format(node.title, response.url))
        url = response.css(".book-description a.download-link::attr(href)").get()
        if not url:
            logger.error("Could not find download link: {}".format(url))
        else:
            DOWNLOAD_JOBS.append(DownloadJob(node, file_cls, url))


# The chef subclass
################################################################################
class ElejandriaLibrosChef(SushiChef):

    RICECOOKER_JSON_TREE = "ricecooker_json_tree.json"

    """
    This class uploads the Elejandria Libros channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {  # Channel Metadata
        "CHANNEL_SOURCE_DOMAIN": CHANNEL_DOMAIN,  # Who is providing the content
        "CHANNEL_SOURCE_ID": CHANNEL_SOURCE_ID,  # Channel's unique id
        "CHANNEL_TITLE": CHANNEL_NAME,  # Name of channel
        "CHANNEL_LANGUAGE": CHANNEL_LANGUAGE,  # Language of channel
        "CHANNEL_THUMBNAIL": CHANNEL_THUMBNAIL,  # Local path or url to image file (optional)
        "CHANNEL_DESCRIPTION": CHANNEL_DESCRIPTION,  # Description of the channel (optional)
    }

    def crawl(self, args, options):
        # Invoke Scrapy this way -- it's the only way to avoid it from
        # calling its own configure_logging, which messes up logging
        # outputs from our own configuration
        runner = CrawlerRunner()
        d = runner.crawl(ElejandriaLibrosSpider)
        d.addBoth(lambda _: reactor.stop())
        reactor.run()

    def scrape(self, args, options):
        for job in DOWNLOAD_JOBS:
            job.download()

    def transform(self, args, options):
        pass

    def pre_run(self, args, options):
        # data_dirs = [TREES_DATA_DIR, DOWNLOADED_FILES_DIR, TRANSFORMED_FILES_DIR]
        # for dir in data_dirs:
        #     if not os.path.exists(dir):
        #         os.makedirs(dir, exist_ok=True)
        self.crawl(args, options)
        self.scrape(args, options)
        self.transform(args, options)

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(
            *args, **kwargs
        )  # Create ChannelNode from data in self.channel_info

        for node in NODE_TREE:
            channel.add_child(node)

        # TODO: Replace next line with chef code
        # raise NotImplementedError("constuct_channel method not implemented yet...")

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        # return channel


# CLI
################################################################################
if __name__ == "__main__":
    # This code runs when sushichef.py is called from the command line
    chef = ElejandriaLibrosChef()
    chef.main()
