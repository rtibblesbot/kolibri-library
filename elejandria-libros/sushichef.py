#!/usr/bin/env python
import logging
import scrapy
import signal

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

# For every book, add a counter when we meet it. Sanity check later.
# Some books are contained in a lot of collections. Example:
# https://www.elejandria.com/libro/orgullo-y-prejuicio/jane-austen/20
NODE_COUNTERS = {}


class ElejandriaLibrosSpider(scrapy.Spider):
    """
    Crawls collections and categories, creates a topic for each
    collection and category.
    
    Books (leaf nodes) are duplicated, hence stored in a local key-value.
    """

    name = "elejandria-spider"

    def __init__(self):
        super().__init__()


    def spider_closed(self, spider):
        signal.signal(signal.SIGINT, signal.default_int_handler)
        logger.info('Spider closed: %s', spider.name)

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
        logger.debug("Parsing categories: {}".format(response.url))
        for category_link in response.css("h3.book-description a"):
            # There are two sibling <a> links, we are skipping the second one
            if "btn" in category_link.attrib.get("class", ""):
                continue
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
                url,
                callback=self.parse_book,
                dont_filter=True,
                cb_kwargs={"node": node, "source_prefix": "category"}
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
                url,
                callback=self.parse_book,
                dont_filter=True,
                cb_kwargs={"node": node, "source_prefix": "collection"}
            )
            yield request

    def parse_book(self, response, node, source_prefix=""):
        """
        Example:
        https://www.elejandria.com/libro/alicia-en-el-pais-de-las-maravillas/carroll-lewis/94
        
        :param source_prefix: Prefix a DocumentNode's source_id because the same books are added in different subtrees
        """
        logger.debug("Visiting from category '{}' - parsing book page: {}".format(node.title, response.url))

        # Book titles prefixed "Libro <Book Title>"
        book_title = response.css("h1.bordered-heading::text").get().replace("Libro ", "", 1)
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

        if book_title not in NODE_COUNTERS:
            NODE_COUNTERS[book_title] = 1
        else:
            NODE_COUNTERS[book_title] += 1

        document_node = nodes.DocumentNode(
            source_id="{}-{}-{}".format(source_prefix, NODE_COUNTERS[book_title], response.url),
            title=book_title,
            license=licenses.get_license(PUBLIC_DOMAIN),
            author=author,
            provider=CHANNEL_NAME,
            description=description,
            thumbnail=thumbnail,
            files=[],
        )

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
            dont_filter=True,
            cb_kwargs={"document_node": document_node, "file_cls": file_cls, "parent_node": node},
        )
        yield request

    def parse_download(self, response, document_node, parent_node, file_cls):
        logger.debug("Downloading ePub: {}".format(document_node.title, response.url))
        url = response.css(".book-description a.download-link::attr(href)").get()
        if not url:
            logger.error("Could not find download link: {}".format(url))
        else:
            document_node.add_file(file_cls(url))

        # Add the node now that we know a PDF or ePub exists
        parent_node.add_child(document_node)


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
        
        # Settings add HttpCacheMiddleware, read more here:
        # https://scrapy.readthedocs.io/en/latest/topics/downloader-middleware.html
        
        if DEBUG:
            logger.info("Using Scrapy's cache to store HTTP responses in .scrapy/")
        
        runner = CrawlerRunner(
            settings={
                'HTTPCACHE_ENABLED': DEBUG,
                'HTTPCACHE_ALWAYS_STORE': DEBUG,
                'DOWNLOADER_MIDDLEWARES': {
                    # Non-defaults:
                    'scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware': 99,
                    # Defaults:
                    'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware': 100,
                    'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware': 300,
                    'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware': 350,
                    'scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware': 400,
                    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': 500,
                    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 550,
                    'scrapy.downloadermiddlewares.ajaxcrawl.AjaxCrawlMiddleware': 560,
                    'scrapy.downloadermiddlewares.redirect.MetaRefreshMiddleware': 580,
                    'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 590,
                    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': 600,
                    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': 700,
                    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 750,
                    'scrapy.downloadermiddlewares.stats.DownloaderStats': 850,
                    'scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware': 900,
                }
            }
        )
        d = runner.crawl(ElejandriaLibrosSpider)
        # d.addBoth(stop_crawling)
        d.addBoth(lambda _: reactor.stop())
        reactor.run()
        signal.signal(signal.SIGINT, signal.default_int_handler)

    def consistency(self):
        for book, count in NODE_COUNTERS.items():
            # Most books apper twice: Once in a collection and once in
            # a category.
            if count > 2:
                logger.warning("{} appears {} times".format(book, count))
            if count > 8:
                raise AssertionError("Found the same book too many times")

    def transform(self, args, options):
        pass

    def pre_run(self, args, options):
        self.crawl(args, options)
        self.consistency()

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
