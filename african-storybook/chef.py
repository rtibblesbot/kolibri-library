#!/usr/bin/env python

"""
Sushi Chef for African Storybook: http://www.africanstorybook.org/
We make an HTML5 app out of each interactive reader.
"""

from collections import defaultdict
import html
import os
import re
import requests
import tempfile
import time
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

import le_utils.constants
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip


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


_LANGUAGE_NAME_LOOKUP = {l.name: l for l in le_utils.constants.languages.LANGUAGELIST}

def getlang_by_name(name):
    # TODO(davidhu): Change to the following once
    # https://github.com/learningequality/le-utils/pull/28/files gets merged:
    # return le_utils.constants.languages.getlang_by_name(name)
    return _LANGUAGE_NAME_LOOKUP.get(name)


class AfricanStorybookChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "www.africanstorybook.org",
        'CHANNEL_SOURCE_ID': "african-storybook",
        'CHANNEL_TITLE': "African Storybook",
        'CHANNEL_THUMBNAIL': "thumbnail.png",
        'CHANNEL_DESCRIPTION': "Open access to picture storybooks in the languages of Africa. For children's literacy, enjoyment and imagination.",
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
        )

        # Download the books into a dict {language: [list of books]}
        channel_tree = download_all()

        # ... now add them to the ricecooker channel tree!
        for language, levels in sorted(channel_tree.items(), key=lambda t: t[0]):
            # Skip creating topic node with the language called "0" -- a bug
            # from the ASB website itself. There's two books here, though, but
            # I can't tell in which language those two books are.
            if language == "0":
                continue

            language_node = nodes.TopicNode(source_id=language, title=language,
                    language=getlang_by_name(language))
            channel.add_child(language_node)

            for level, books in sorted(levels.items(), key=lambda t: t[0]):
                # TODO(davidhu): Translate this topic title "Level #" into the
                # topic's language.
                level_node = nodes.TopicNode(source_id=level, title="Level %s" % level)
                language_node.add_child(level_node)

                for book in books:
                    level_node.add_child(book)

        return channel


def download_all():
    with WebDriver("http://www.africanstorybook.org/", delay=20000) as driver:
        books = driver.execute_script("return bookItems;")
        total_books = len(books)

        # Build a dict of {African Storybook language ID: language name}
        languages_html = driver.execute_script("return languages;")
        language_id_map = {}
        for node in BeautifulSoup(languages_html, "html.parser"):
            language_id_map[node["value"]] = node.text.strip()

        channel_tree = defaultdict(lambda: defaultdict(list))
        for i, book in enumerate(books):
            book_id = book["id"]
            book_url = "http://www.africanstorybook.org/reader.php?id=%s" % book_id
            print("Downloading book %s of %s with url %s" % (i + 1, total_books, book_url))

            level = book["level"]
            language_ids = book["lang"].split(",")
            languages = [language_id_map[code.strip()] for code in language_ids if code]
            author = "%s; Others: %s" % (book["author"], book["people"])
            title = strip_level_from_title(html.unescape(book["title"]))
            description = html.unescape(book["summary"])

            book, languages = download_book(book_url, book_id, title, author, description, languages)

            if book:
                print("... downloaded a Level %s %s book titled %s" % (
                    level, "/".join(languages), title))
                for language in languages:
                    channel_tree[language][level].append(book)
            else:
                print("... WARNING: book not found")

    return channel_tree


def download_book(book_url, book_id, title, author, description, languages):
    """Downloads a single book from the African Storybook website given its URL.

    Return a tuple of (
        the downloaded book as an HTML5AppNode,
        the language of the book as a string).
    """
    # -- 0. Parse --

    doc = get_parsed_html_from_url(book_url)

    if "The storybook you wanted is not part of the African Storybook website" in doc.body.text:
        return None, None, []

    # -- 1. Extract --

    # Extract copyright holder.
    copyright_holder = str(doc.select_one(".backcover_copyright").contents[0]).strip(" ©")

    # Extract the language if we didn't get it already.
    if not languages:
        author_text_lines = replace_br_with_newlines(doc.select_one(".bookcover_author")).split("\n")
        language_raw = next(l for l in author_text_lines if l.startswith("Language"))
        languages = [language_raw.strip("Language").strip(" -")]

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

    with open(os.path.join(destination, "index.html"), "w") as f:
        f.write(str(doc))

    zip_path = create_predictable_zip(destination)
    return nodes.HTML5AppNode(
        source_id=book_id,
        title=truncate_metadata(title),
        license=licenses.CC_BYLicense(
            copyright_holder=truncate_metadata(copyright_holder)),
        description=description,
        author=truncate_metadata(author),
        thumbnail=thumbnail,
        files=[files.HTMLZipFile(zip_path)],
        language=getlang_by_name(languages[0]),
    ), languages


def strip_level_from_title(title):
    return re.sub("\(Level .\)", "", title).strip()


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


BG_IMG_RE = re.compile("background-image:url\((.*)\)")


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

    def css_middleware(url):
        # Somehow the minified app CSS doesn't render images. Download the
        # original.
        return url.replace("app.min.css", "app.css")

    # Download all static assets.
    # TODO(davidhu): Also download fonts referenced in http://www.africanstorybook.org/css/app.css
    download_assets("img[src]", "src")  # Images
    download_assets("link[href]", "href", url_middleware=css_middleware)  # CSS
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
        filename = "%s_%s" % (i, os.path.basename(url))
        node["style"] = BG_IMG_RE.sub("background-image:url(%s)" % filename, style)
        download_file(url, destination, request_fn=make_request, filename=filename)

        if node.has_attr("class") and "cover-image" in node.get("class"):
            thumbnail = os.path.join(destination, filename)

    return thumbnail


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
        "style": "left: 0; cursor: w-resize;",
        "onclick": "$$('#go-back').click();",
        "src": left_png,
    }

    right_flipper_html = base_flipper_html % {
        "id": "right-flipper",
        "width": width,
        "style": "right: 0; cursor: e-resize;",
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


def make_request(url, clear_cookies=True, timeout=60, *args, **kwargs):
    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = sess.get(url, headers=headers, timeout=timeout, *args, **kwargs)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            retry_count += 1
            print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                return Dummy404ResponseObject(url=url)

    if response.status_code != 200:
        print("NOT FOUND:", url)
    elif not response.from_cache:
        print("NOT CACHED:", url)

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
