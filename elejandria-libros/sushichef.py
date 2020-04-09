#!/usr/bin/env python
import logging
import os
import scrapy
import sys
from twisted.internet import reactor
from scrapy.crawler import CrawlerRunner

from scrapy.crawler import CrawlerProcess

from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import setup_logging
from ricecooker.exceptions import raise_for_invalid_channel
from scrapy.utils.log import configure_logging


# Run constants
################################################################################
CHANNEL_NAME = "Elejandria Libros"              # Name of channel
CHANNEL_SOURCE_ID = "elejandria-libros"    # Channel's unique id
CHANNEL_DOMAIN = "elejandria.com"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = "Elejandria es un sitio web que ofrece libros gratis de dominio público o publicados bajo licencias abiertas. La mayoría de los autores son clásicos de la literatura unviersal, pero también podrás descargar gratis libros de dominio público actuales con licencias de libre distribución."
CHANNEL_THUMBNAIL = "channel_thumbnail.png"                                    # Local path or url to image file (optional)

# Additional constants
################################################################################

START_URL = "https://www.elejandria.com/colecciones"

DEBUG = True


logger = logging.getLogger(__name__)

setup_logging(
    level=logging.DEBUG if DEBUG else logging.INFO,
    error_log="errors.log",
    add_loggers=["scrapy"],
)

# The node tree that will finally be appended to the ChannelNode
NODE_TREE = []


class ElejandriaLibrosSpider(scrapy.Spider):

    name = "elejandria-base-collections-spider"
    start_urls = [START_URL]

    def __init__(self):
        super().__init__()
        self.node_tree = []

    def parse(self, response):
        """
        Parses collections on the main page.
        For each collection:
        
        * Create a TopicNode and append to Ricecooker tree
        * Spawn parsing for each collection 
        """
        # logger.debug("Parsing collection base page: {}".format(response.url))
        for collection_link in response.css(".book-description h2 a").getall():
            print(collection_link)
            # logger.debug("Found collection with title: {}".format(collection_link.css("::text").get()))
            #ricecooker_node = nodes.TopicNode(
            #    title="lala",
            #    source_id=collection_link.attrib("href"),
            #)
            self.node_tree.append(
                ""
            )
            request = scrapy.Request(
                collection_link["href"],
                callback=self.parse_collection,
                cb_kwargs={'node': ""}
            )
            yield request

    def parse_collection(self, response, node):
        # logger.debug("Parsing collection \"{}\": {}".format(node.title, response.url))
        for book_link in response.css(".book a").getall():
            logger.debug("Found book")
            # logger.debug("Found book with title: {}".format(book_link.text()))


# The chef subclass
################################################################################
class ElejandriaLibrosCheffos(SushiChef):

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
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }
    # Your chef subclass can override/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def crawl(self, args, options):
        # Invoke Scrapy this way -- it's the only way to avoid it from
        # calling its own configure_logging, which messes up logging
        # outputs from our own configuration
        runner = CrawlerRunner()
        d = runner.crawl(ElejandriaLibrosSpider)
        d.addBoth(lambda _: reactor.stop())
        reactor.run()

    def transform(self, args, options):
        pass

    def pre_run(self, args, options):
        # data_dirs = [TREES_DATA_DIR, DOWNLOADED_FILES_DIR, TRANSFORMED_FILES_DIR]
        # for dir in data_dirs:
        #     if not os.path.exists(dir):
        #         os.makedirs(dir, exist_ok=True)
        self.crawl(args, options)
        # self.scrape(args, options)
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
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        for node in NODE_TREE:
            channel.add_child(node)

        # TODO: Replace next line with chef code
        # raise NotImplementedError("constuct_channel method not implemented yet...")

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        # return channel



# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = ElejandriaLibrosCheffos()
    chef.main()
