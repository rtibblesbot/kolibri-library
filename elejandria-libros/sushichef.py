#!/usr/bin/env python
import logging
import scrapy
import signal
import sys

from twisted.internet import reactor
from scrapy.crawler import CrawlerRunner

from le_utils.constants.licenses import PUBLIC_DOMAIN

from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.config import setup_logging
from ricecooker.exceptions import raise_for_invalid_channel


# Run constants
################################################################################
CHANNEL_NAME = "Elejandria Libros"
CHANNEL_SOURCE_ID = "elejandria-libros"
CHANNEL_DOMAIN = "elejandria.com"
CHANNEL_LANGUAGE = "es"
CHANNEL_DESCRIPTION = "Elejandria es un sitio web que ofrece libros gratis de dominio público o publicados bajo licencias abiertas. La mayoría de los autores son clásicos de la literatura unviersal, pero también podrás descargar gratis libros de dominio público actuales con licencias de libre distribución."
CHANNEL_THUMBNAIL = (
    "channel_thumbnail.png"  # Local path or url to image file (optional)
)

# Additional constants
################################################################################

DEBUG = True

logger = logging.getLogger(__name__)

setup_logging(
    level=logging.DEBUG if DEBUG else logging.INFO,
    error_log="errors.log",
    add_loggers=["scrapy"],
)

# The top-level node tree that will be appended to the ChannelNode
NODE_TREE = []

# Scraped book URLs are stored here. Don't worry about concurrency,
# Scrapy is single-threaded for parsing, only network requests are
# concurrent.
BOOKS = {}


class ElejandriaLibrosSpider(scrapy.Spider):
    """
    Crawls collections and categories, creates a topic for each
    collection and category.
    
    Books (leaf nodes) are duplicated, hence stored in a local key-value.
    """

    name = "elejandria-spider"

    def __init__(self):
        super().__init__()

    def start_requests(self):
        """
        This is where the spider begins: Create the top-level nodes in
        the channel tree and start crawling collections and categories.
        """
        collections_node = nodes.TopicNode(title="Libros organizados por colección", source_id="colecciones",)
        categories_node = nodes.TopicNode(title="Libros organizados por categoria", source_id="categorias",)
        NODE_TREE.append(collections_node)
        NODE_TREE.append(categories_node)
        return [
            scrapy.Request(
                "https://www.elejandria.com/categorias",
                callback=self.parse_categories,
                cb_kwargs={"node": categories_node, "top_level": True}
            ),
            scrapy.Request(
                "https://www.elejandria.com/colecciones",
                callback=self.parse_collections,
                cb_kwargs={"node": collections_node}
            ),
        ]

    def parse_categories(self, response, node, top_level=False):
        """
        Parse a category index (list of categories). This can be the
        top-level page:
        https://www.elejandria.com/categorias
        
        Or a sub-category:
        https://www.elejandria.com/categorias/literatura-y-ficcion/13
        """
        for category_link in response.css("h3.book-description a"):
            title = category_link.css("::text").get()
            url = category_link.attrib["href"]
            category_node = nodes.TopicNode(title=title, source_id=url,)
            node.add_child(category_node)
            if top_level:
                request = scrapy.Request(
                    url,
                    callback=self.parse_categories,
                    cb_kwargs={"node": category_node},
                )
            else:
                request = scrapy.Request(
                    url,
                    callback=self.parse_category,
                    cb_kwargs={"node": category_node},
                )
            yield request            

    def parse_category(self, response, node):
        """
        Example:
        https://www.elejandria.com/coleccion/descargar-gratis-20-libros-clasicos-para-sobrellevar-la-cuarentena
        """
        logger.debug('Parsing collection "{}": {}'.format(node.title, response.url))
        for book_link in response.css(".book div p a.primary-text-color"):
            url = book_link.attrib["href"]
            title = book_link.css("::text").get()
            logger.debug("Found book link: {}".format(title))
            request = scrapy.Request(
                url, callback=self.parse_book, cb_kwargs={"node": node}
            )
            yield request

    def parse_collections(self, response, node):
        """
        Parses collections on the main page. For each collection:
        
        * Create a :class:`ricecooker.classes.nodes.TopicNode` and
          append to Ricecooker tree
        * Spawn parsing for each collection
        """
        logger.debug("Parsing collection base page: {}".format(response.url))
        for collection_link in response.css(".book-description h2 a"):
            title = collection_link.css("::text").get()
            url = collection_link.attrib["href"]
            logger.debug("Found collection with title: {}".format(title))
            collection_node = nodes.TopicNode(title=title, source_id=url,)
            node.add_child(
                collection_node
            )
            request = scrapy.Request(
                collection_link.attrib["href"],
                callback=self.parse_collection,
                cb_kwargs={"node": collection_node},
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

        if response.url in BOOKS:
            book = BOOKS[response.url]
            logger.debug("Already visited book page, adding {} to {}".format(book.title, node.title))
            node.add_child(book)
            return

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
            files=[],
        )

        # Save in key-value store if we re-visit this page
        BOOKS[response.url] = document_node

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

        # Add the node now that we know a PDF or ePub exists
        node.add_child(document_node)

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
            node.add_file(file_cls(url))


def stop_crawling():
    logger.error("Stopping engine")
    # def customHandler(signum, stackframe):
    #     reactor.callFromThread(reactor.stop) # to stop twisted code when in the reactor loop
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.exit(1)


# The chef subclass
################################################################################
class ElejandriaLibrosChef(SushiChef):

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
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": CHANNEL_DOMAIN,
        "CHANNEL_SOURCE_ID": CHANNEL_SOURCE_ID,
        "CHANNEL_TITLE": CHANNEL_NAME,
        "CHANNEL_LANGUAGE": CHANNEL_LANGUAGE,
        "CHANNEL_THUMBNAIL": CHANNEL_THUMBNAIL,
        "CHANNEL_DESCRIPTION": CHANNEL_DESCRIPTION,
    }

    def crawl(self, args, options):
        """
        Start Scrapy with CrawlerRunner -- it's the only way to keep it
        from calling its own configure_logging, which messes up logging
        outputs from our own configuration
        """
        runner = CrawlerRunner()
        
        d = runner.crawl(ElejandriaLibrosSpider)
        # d.addBoth(stop_crawling)
        d.addBoth(lambda _: reactor.stop())
        reactor.run()

    def scrape(self, args, options):
        pass

    def transform(self, args, options):
        pass

    def pre_run(self, args, options):
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
        )

        for node in NODE_TREE:
            channel.add_child(node)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel


# CLI
################################################################################
if __name__ == "__main__":
    
    # This code runs when sushichef.py is called from the command line
    chef = ElejandriaLibrosChef()
    chef.main()
