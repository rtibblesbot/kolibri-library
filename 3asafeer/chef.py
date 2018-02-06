#!/usr/bin/env python

"""
Sushi Chef for http://3asafeer.com/
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
import uuid

from bs4 import BeautifulSoup

import le_utils.constants
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip
import selenium.webdriver.support.ui as selenium_ui
from distutils.dir_util import copy_tree


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://3asafeer.com/', forever_adapter)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}


class ThreeAsafeerChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "3asafeer.com",
        'CHANNEL_SOURCE_ID': "3asafeer",
        'CHANNEL_TITLE': "3asafeer",
        'CHANNEL_THUMBNAIL': "thumbnail.png",
        'CHANNEL_DESCRIPTION': "An online digital library for reading in Arabic with pictures and audio.",
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
            language = "en",
        )

        channel.add_child(download_single())

        return channel


def download_single():
    with WebDriver("http://3asafeer.com/", delay=3000) as driver:

        print('Closing popup')
        close_popup = driver.find_element_by_css_selector('.fancybox-item.fancybox-close')
        close_popup.click()
        time.sleep(1)

        print('Clicking "read"')
        read_link = driver.find_element_by_css_selector('#readLink')
        read_link.click()

        selenium_ui.WebDriverWait(driver, 60).until(
                lambda driver: driver.find_element_by_id('list-container'))
        time.sleep(2)

        print('Clicking book 13')
        book = driver.find_element_by_css_selector('#cover-13 .story')
        book.click()

        #driver.find_elements_by_css_selector('.story-cover')

        selenium_ui.WebDriverWait(driver, 60).until(
                lambda driver: driver.find_element_by_id('reader-viewport'))

        # XXX also wait for the actual images themselves to be loaded or
        # something

        #print('Scraping book 13')
        #book_content = driver.find_element_by_css_selector('#maincontent')
        #book_html = book_content.get_attribute('innerHTML')

        destination = tempfile.mkdtemp()

        doc = BeautifulSoup(driver.page_source, "html.parser")
        download_static_assets(doc, destination)

        doc.select_one('base')['href'] = ''
        doc.select_one('#loading').decompose()
        doc.select_one('#finishedActions').decompose()
        doc.select_one('.bookmarkbtn').decompose()
        doc.select_one('.reader-expand').decompose()
        doc.select_one('#progressBar').decompose()
        doc.select_one('#androidNotification').decompose()
        doc.select_one('#exit').decompose()

        with open(os.path.join(destination, "index.html"), "w") as f:
            f.write(str(doc))

        print("destination is", destination)
        preview_in_browser(destination)

        zip_path = create_predictable_zip(destination)
        return nodes.HTML5AppNode(
            source_id='cover-13',
            title=truncate_metadata('Book of animals'),
            license=licenses.CC_BYLicense(
                copyright_holder=truncate_metadata('copyright holder')),
            description='book of animals',
            author=truncate_metadata('3asafeer'),
            #thumbnail='',  # XXX
            files=[files.HTMLZipFile(zip_path)],
            #language=getlang_by_name(languages[0]),
            language="en",
        )


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

    #preview_in_browser(destination)

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


CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")
BG_IMG_RE = re.compile("background-image:url\((.*)\)")
IMAGES_IN_JS_RE = re.compile(r"images/(.*?)['\")]")


url_blacklist = [
    'google-analytics.com/analytics.js',
    'fbds.js',
    # TODO(davidhu): Remove Mailchimp and some other scripts too
]


def is_blacklisted(url):
    return any((item in url) for item in url_blacklist)


def derive_filename(url):
    return "%s.%s" % (uuid.uuid4().hex, os.path.basename(urlparse(url).path))


def download_static_assets(doc, destination):
    """Download all the static assets for a given book's HTML soup.

    Return the downloaded filename of an image to use for the book's thumbnail.
    """
    def download_assets(selector, attr, url_middleware=None,
            content_middleware=None, node_filter=None):
        nodes = doc.select(selector)

        for i, node in enumerate(nodes):

            if node_filter:
                if not node_filter(node):
                    src = node[attr]
                    node[attr] = ''
                    print('Skipping node with src ', src)
                    continue

            url = make_fully_qualified_url(node[attr])

            if is_blacklisted(url):
                print('Skipping downloading blacklisted url', url)
                node[attr] = ""
                continue

            if 'jquery.fancybox.pack.js' in url:
                node[attr] = "static/jquery.fancybox.dummy.js"
                continue

            if url_middleware:
                url = url_middleware(url)

            filename = derive_filename(url)
            node[attr] = filename

            print("Downloading", url, "to filename", filename)
            download_file(url, destination, request_fn=make_request,
                    filename=filename, middleware_callbacks=content_middleware)

    def js_middleware(content, url, **kwargs):
        # Download all images referenced in JS files
        for img in IMAGES_IN_JS_RE.findall(content):
            url = make_fully_qualified_url('/images/%s' % img)
            print("Downloading file", img, "from url", url)
            download_file(url, destination, subpath="images",
                    request_fn=make_request, filename=img)

        # Polyfill localStorage and document.cookie as iframes can't access
        # them
        return (content
            .replace("localStorage", "_localStorage")
            .replace('document.cookie.split', '"".split')
            .replace('document.cookie', 'window._document_cookie'))

    def css_url_middleware(url):
        # Somehow the minified app CSS doesn't render images. Download the
        # original.
        return url.replace("app.min.css", "app.css")

    def css_node_filter(node):
        return "stylesheet" in node["rel"]

    def css_content_middleware(content, url, **kwargs):
        # Download linked fonts and images
        def repl(match):
            src = match.group(1)
            if src.startswith('//localhost'):
                return 'src()'
            if src.startswith('data:'):
                return match.group(0)
            src_url = make_fully_qualified_url(src)
            derived_filename = derive_filename(src_url)
            download_file(src_url, destination, request_fn=make_request,
                    filename=derived_filename)
            return 'src("%s")' % derived_filename

        return CSS_URL_RE.sub(repl, content)

    # Download all static assets.
    download_assets("img[src]", "src")  # Images
    download_assets("link[href]", "href", url_middleware=css_url_middleware,
            content_middleware=css_content_middleware,
            node_filter=css_node_filter)  # CSS
    download_assets("script[src]", "src", content_middleware=js_middleware) # JS
    download_assets("source[src]", "src") # Audio
    download_assets("source[srcset]", "srcset") # Audio

    # ... and also run the middleware on associated CSS/JS to get linked files
    for node in doc.select('style'):
        node.string = css_content_middleware(node.get_text(), url='')
    for node in doc.select('script'):
        if not node.attrs.get('src'):
            node.string = js_middleware(node.get_text(), url='')

    copy_tree("static", os.path.join(destination, "static"))

    chef_head_script = doc.new_tag("script", src="static/chef_end_of_head.js")
    doc.select_one('head').append(chef_head_script)

    chef_body_script = doc.new_tag("script", src="static/chef_end_of_body.js")
    doc.select_one('body').append(chef_body_script)

    chef_css = doc.new_tag("link", href="static/chef.css")
    doc.select_one('head').append(chef_css)

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

    return response


def get_parsed_html_from_url(url, *args, **kwargs):
    html = make_request(url, *args, **kwargs).content
    return BeautifulSoup(html, "html.parser")


def make_fully_qualified_url(url):
    if url.startswith("../images"):
        return "http://3asafeer.com" + url[2:]
    if url.startswith("../scripts"):
        return "http://3asafeer.com" + url[2:]
    if url.startswith("//"):
        return "http:" + url
    if url.startswith("/"):
        return "http://3asafeer.com" + url
    if not url.startswith("http"):
        return "http://3asafeer.com/" + url
    return url


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = ThreeAsafeerChef()
    chef.main()
