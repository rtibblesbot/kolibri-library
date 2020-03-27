#!/usr/bin/env python

"""
Sushi Chef for African Storybook: http://www.africanstorybook.org/
We make an HTML5 app out of each interactive reader.
"""

from collections import defaultdict
import html
import os
import random
import re
import requests
import tempfile
import time

from bs4 import BeautifulSoup

from le_utils.constants.languages import getlang_by_name, getlang_by_native_name
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.config import LOGGER
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip


NETWORK_ERRORS = (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout)


CHEF_TMPDIR = 'chefdata/tmp/'  # use local tmp dir for saving HTML5 Apps content
os.environ['TMPDIR'] = CHEF_TMPDIR
if not os.path.exists(CHEF_TMPDIR):
    os.makedirs(CHEF_TMPDIR, exist_ok=True)


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://www.africanstorybook.org/', forever_adapter)
sess.mount('https://fonts.googleapis.com/', forever_adapter)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}


def get_lang_by_name_with_fallback(language_name):
    lang_obj = getlang_by_name(language_name)
    if lang_obj is None:
        lang_obj = getlang_by_native_name(language_name)
        if lang_obj is None:
            # currently non-supported language codes are tagged as Undereminded
            lang_obj = getlang_by_name('Undetermined')
    return lang_obj


class AfricanStorybookChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "www.africanstorybook.org",
        'CHANNEL_SOURCE_ID': "african-storybook",
        'CHANNEL_TITLE': "African Storybook Library (multiple languages)",
        'CHANNEL_THUMBNAIL': "thumbnail.png",
        'CHANNEL_DESCRIPTION': "Library of picture storybooks in all the languages of African countries, designed to promote basic literacy and reading for learners of young ages and varying literacy levels.",
    }

    def construct_channel(self, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        # create channel
        channel_info = self.channel_info
        channel = nodes.ChannelNode(
            source_domain = channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = channel_info['CHANNEL_SOURCE_ID'],
            title = channel_info['CHANNEL_TITLE'],
            thumbnail = channel_info.get('CHANNEL_THUMBNAIL'),
            description = channel_info.get('CHANNEL_DESCRIPTION'),
            language= "mul",
        )

        #download_book("http://www.africanstorybook.org/reader.php?id=16451", "16451", "title", "author", "description", "en")

        # Download the books into a dict {language: [list of books]}
        channel_tree = download_all(kwargs)

        # ... now add them to the ricecooker channel tree!
        LOGGER.debug('STARTING TO CREATE THE RICECOOKER CHANNEL TREE')
        for language, levels in sorted(channel_tree.items(), key=lambda t: t[0]):
            # Skip creating topic node with the language called "0" -- a bug
            # from the ASB website itself. There's two books here, though, but
            # I can't tell in which language those two books are.
            if language == "0":
                LOGGER.info('skipping language 0')
                continue
                
            lang_obj = get_lang_by_name_with_fallback(language)
            LOGGER.debug('LANGUAGE ' + language + '   lang_obj=' + str(lang_obj))

            language_node = nodes.TopicNode(source_id=language, title=language, language=lang_obj.code)
            channel.add_child(language_node)

            for level, books in sorted(levels.items(), key=lambda t: t[0]):
                LOGGER.debug('   LEVEL %s' % level) 
                # TODO(davidhu): Translate this topic title "Level #" into the
                # topic's language.
                level_node = nodes.TopicNode(source_id=level, title="Level %s" % level)
                language_node.add_child(level_node)

                for book in books:
                    LOGGER.debug('      BOOK source_id=' + book.source_id) 
                    level_node.add_child(book)

        return channel


def download_all(kwargs):
    scraped_ids = set()

    with WebDriver("http://www.africanstorybook.org/", delay=20000) as driver:
        books = driver.execute_script("return bookItems;")
        if 'sample' in kwargs and kwargs['sample']:
            random.seed(42)
            sample_size = int(kwargs['sample'])
            books = random.sample(books, sample_size)
        total_books = len(books)

        # Build a dict of {African Storybook language ID: language name}
        languages_html = driver.execute_script("return languages;")
        language_id_map = {}
        for node in BeautifulSoup(languages_html, "html.parser"):
            language_id_map[node["value"]] = node.text.strip()

        channel_tree = defaultdict(lambda: defaultdict(list))
        for i, book in enumerate(books):
            book_id = book["id"]
            if book_id in scraped_ids:
                continue
            scraped_ids.add(book_id)

            book_url = "http://www.africanstorybook.org/reader.php?id=%s" % book_id
            LOGGER.info("Downloading book %s of %s from url %s" % (i + 1, total_books, book_url))

            level = book["level"]
            language_ids = book["lang"].split(",")
            languages = [language_id_map[code.strip()] for code in language_ids if code]
            author = "%s; Others: %s" % (book["author"], book["people"])
            title = strip_level_from_title(html.unescape(book["title"]))
            description = html.unescape(book["summary"])

            for language in languages:
                book = download_book(book_url, book_id, title, author, description, language)
                # book = {'book_url':book_url,
                #         'book_id': book_id,
                #         'title': title,
                #         'language': language}
                if book:
                    LOGGER.info("... downloaded a Level %s %s book titled %s" % (level, language, title))
                    channel_tree[language][level].append(book)
                else:
                    LOGGER.warning("... WARNING: book %s not found in %s" % (book_id, language))

    # import json
    # with open('channel_tree.json', 'w') as jsonf:
    #     json.dump(channel_tree, jsonf, indent=4)
    return channel_tree


def download_book(book_url, book_id, title, author, description, language):
    """Downloads a single book from African Storybook website given its URL."""
    # -- 0. Parse --

    doc = get_parsed_html_from_url(book_url)

    if "The storybook you wanted is not part of the African Storybook website" in doc.body.text:
        return None, None, []

    # -- 1. Extract --

    # Extract copyright holder.
    back_cover = doc.select_one(".backcover_copyright")
    if back_cover:
        copyright_holder = str(back_cover.contents[0]).strip(" ©")
    else:
        LOGGER.warning("WARNING: failed to find backcover_copyright for url:" + book_url)
        copyright_holder = 'African Storybook Initiative'


    # -- 2. Modify and write files --

    destination = tempfile.mkdtemp()
    thumbnail = download_static_assets(doc, destination)

    # Hide the African Storybook header nav bar.
    header = doc.select_one("#headerBar")
    if header:
        header["style"] = "display: none;"

    # Add page flipper buttons
    left_png, response = download_file("http://www.africanstorybook.org/img/left.png",
            destination, request_fn=make_request)
    right_png, response = download_file("http://www.africanstorybook.org/img/right.png",
            destination, request_fn=make_request)
    add_page_flipper_buttons(doc, left_png, right_png)

    # Remove calls to third-party sources before writing out the index.html
    with open(os.path.join(destination, "index.html"), "w") as f:
        index_html = str(doc)
        index_html = index_html.replace("//www.google-analytics.com/analytics.js", "")
        index_html = index_html.replace("js-agent.newrelic.com/nr-1044.min.js", "")
        index_html = index_html.replace("//connect.facebook.net/en_US/sdk.js", "")
        f.write(index_html)

    #preview_in_browser(destination)

    zip_path = create_predictable_zip(destination)
    return nodes.HTML5AppNode(
        source_id="%s|%s" % (book_id, language),
        title=truncate_metadata(title),
        license=licenses.CC_BYLicense(
            copyright_holder=truncate_metadata(copyright_holder)),
        description=description,
        author=truncate_metadata(author),
        thumbnail=thumbnail,
        files=[files.HTMLZipFile(zip_path)],
        language=get_lang_by_name_with_fallback(language),
    )


def strip_level_from_title(title):
    return re.sub("\(Level .\)", "", title).strip()


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


FONT_SRC_RE = re.compile(r"src:\W?url\(.*?fonts/(.*?)['\"]?\)")
UP_DIR_IMG_RE = re.compile(r"url\(['\"]?../im.*?\)")
BG_IMG_RE = re.compile("background-image:url\((.*)\)")

with open("resources/font_sizing.css") as f:
    FONT_SIZING_CSS = f.read()


def download_static_assets(doc, destination):
    """Download all the static assets for a given book's HTML soup.

    Return the downloaded filename of an image to use for the book's thumbnail.
    """
    def download_assets(selector, attr, url_middleware=None, content_middleware=None):
        nodes = doc.select(selector)
        for i, node in enumerate(nodes):
            url = make_fully_qualified_url(node[attr])
            if url_middleware:
                url = url_middleware(url)
            filename = "%s_%s" % (i, os.path.basename(url))
            node[attr] = filename
            download_file(url, destination, request_fn=make_request,
                    filename=filename, middleware_callbacks=content_middleware)

    def js_middleware(content, url, **kwargs):
        # Polyfill window.localStorage as iframes can't access localStorage.
        return content.replace("window.localStorage",
                "({setItem: function(){}, removeItem: function(){}})")

    def css_url_middleware(url):
        # Somehow the minified app CSS doesn't render images. Download the
        # original.
        return url.replace("app.min.css", "app.css")

    def css_content_middleware(content, url, **kwargs):
        if "app.css" in url:
            # Download linked fonts
            for match in FONT_SRC_RE.finditer(content):
                filename = match.groups()[0]
                url = make_fully_qualified_url("fonts/%s" % filename)
                download_file(url, destination, request_fn=make_request)
            processed_css = FONT_SRC_RE.sub(r"src: url('\1')", content)

            # ... and we don't need references to images. Remove them else they
            # may cause a 500 on the server.
            processed_css = UP_DIR_IMG_RE.sub('url("")', content)

            # ... and then append additional CSS to reduce font sizing to fit
            # better on shorter screens (for previewing in Kolibri's iframe
            # when not full-screen).
            return processed_css + FONT_SIZING_CSS

        else:
            return content

    # Download all static assets.
    # TODO(davidhu): Also download fonts referenced in http://www.africanstorybook.org/css/app.css
    download_assets("img[src]", "src")  # Images
    download_assets("link[href]", "href", url_middleware=css_url_middleware,
            content_middleware=css_content_middleware)  # CSS
    download_assets("script[src]", "src", content_middleware=js_middleware) # JS

    # Download all background images, e.g. <div style="background-image:url()">
    # (africanstorybook.org uses these for the main picture found on each page
    # of the storybook.)
    thumbnail = None
    bg_img_nodes = doc.select("div[style*=\"background-image:url(\"]")
    for i, node in enumerate(bg_img_nodes):
        style = node["style"]
        match = BG_IMG_RE.search(style)
        if not match:
            continue

        url = make_fully_qualified_url(match.group(1))
        image_url = pre_flight_image(url)
        if image_url is None:
            LOGGER.warning('WARNING: Could not get image from url=' + url)
            continue

        filename = "%s_%s" % (i, os.path.basename(url))
        node["style"] = BG_IMG_RE.sub("background-image:url(%s)" % filename, style)
        download_file(url, destination, request_fn=make_request, filename=filename)

        if node.has_attr("class") and "cover-image" in node.get("class"):
            thumbnail = os.path.join(destination, filename)

    return thumbnail


def pre_flight_image(url):
    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = sess.get(url)
            if not response.ok:
                return None
            else:
                return url
        except NETWORK_ERRORS as e:
            retry_count += 1
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                return None


def add_page_flipper_buttons(doc, left_png, right_png):
    width = "6%"
    base_flipper_html = """
    <div id="%(id)s"
            style="display: block; position: absolute; top: 0; bottom: 0; width: %(width)s; z-index: 9001; background: #757575; %(style)s"
            onclick="%(onclick)s">
        <img style="display: block; position: absolute; top: 50%%; margin-top: -16px; left: 50%%; margin-left: -16px;"
                src="%(src)s" />
    </div>"""

    left_flipper_html = base_flipper_html % {
        "id": "left-flipper",
        "width": width,
        "style": "left: 0; cursor: pointer;",
        "onclick": "$$('#go-back').click();",
        "src": left_png,
    }

    right_flipper_html = base_flipper_html % {
        "id": "right-flipper",
        "width": width,
        "style": "right: 0; cursor: pointer;",
        "onclick": "$$('#go-next').click();",
        "src": right_png,
    }

    flippers = BeautifulSoup("<div>%s%s</div>" % (left_flipper_html, right_flipper_html),
            "html.parser")

    root_node = doc.select_one(".views")
    root_node["style"] = "padding-left: %(width)s; padding-right: %(width)s; box-sizing: border-box;" % {"width": width}
    root_node.append(flippers.find(id="left-flipper"))
    root_node.append(flippers.find(id="right-flipper"))


def replace_br_with_newlines(element):
    text = ''
    for elem in element.recursiveChildGenerator():
        if isinstance(elem, str):
            text += elem
        elif elem.name == 'br':
            text += '\n'

    # Merge consecutive spaces
    return re.sub(" +", " ", text.strip())


class Dummy404ResponseObject(requests.Response):
    def __init__(self, url):
        super(Dummy404ResponseObject, self).__init__()
        self._content = b""
        self.status_code = 404
        self.url = url

def make_request(url, clear_cookies=True, timeout=60, *args, **kwargs):
    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = sess.get(url, headers=headers, timeout=timeout, *args, **kwargs)
            break
        except NETWORK_ERRORS as e:
            retry_count += 1
            LOGGER.error("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                return Dummy404ResponseObject(url=url)

    if response.status_code != 200:
        LOGGER.error("HTTP CODE " + str(response.status_code) + ' for ' + url)

    return response


def get_parsed_html_from_url(url, *args, **kwargs):
    html = make_request(url, *args, **kwargs).content
    return BeautifulSoup(html, "html.parser")


def make_fully_qualified_url(url):
    if url.startswith("//"):
        return "http:" + url
    if url.startswith("/"):
        return "http://www.africanstorybook.org" + url
    if not url.startswith("http"):
        return "http://www.africanstorybook.org/" + url
    return url



if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = AfricanStorybookChef()
    chef.main()
