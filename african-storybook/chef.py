#!/usr/bin/env python

"""
Sushi Chef for African Storybook: http://www.africanstorybook.org/
We make an HTML5 app out of each interactive reader.
"""

import os
import re
import requests
import tempfile
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

from le_utils.constants import content_kinds, file_formats, licenses
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://www.africanstorybook.org/', forever_adapter)
sess.mount('https://fonts.googleapis.com/', forever_adapter)


# A selection of 50 popular titles, from doc referenced in the sushi chef spec sheet:
# https://docs.google.com/document/d/1EcYjHApp2ghJ4Yfs67kN8nCfi98xdXDFwzepimH7oR8/edit
SELECTION_OF_POPULAR_TITLES = [
    "http://www.africanstorybook.org/reader.php?id=918&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19760&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19762&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9879&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19763&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19764&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19765&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19767&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=13626&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=13263&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19761&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9097&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19876&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9748&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=12083&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=1881&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=17197&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9296&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=6380&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=11990&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=8491&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=5266&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19292&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=12155&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=14771&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=18420&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=18773&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=16988&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=15055&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=13539&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=18769&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=14497&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19467&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9787&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=14792&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=13623&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=12084&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=13548&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9526&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=14415&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=15291&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9243&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19074&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=19421&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=9796&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=10210&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=13213&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=16510&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=6895&d=0&a=1",
    "http://www.africanstorybook.org/reader.php?id=17115&d=0&a=1",
]


class AfricanStorybookChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "www.africanstorybook.org",
        'CHANNEL_SOURCE_ID': "african-storybook",
        'CHANNEL_TITLE': "African Storybook",
        'CHANNEL_THUMBNAIL': "http://www.africanstorybook.org/img/asb120.png",
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

        # build tree
        for url in SELECTION_OF_POPULAR_TITLES:
            channel.add_child(download_book(url))

        # ... and just for test purposes, add a book in the Zulu language
        channel.add_child(download_book("http://www.africanstorybook.org/reader.php?id=16511"))

        return channel


BG_IMG_RE = re.compile("background-image:url\((.*)\)")
SEND_FACEBOOK_RE = re.compile("sendFacebook\([^,]*,[^,]*,(.*)\)")


def download_book(book_url):
    doc = get_parsed_html_from_url(book_url)
    destination = tempfile.mkdtemp()

    def download_assets(selector, attr, middleware=None):
        nodes = doc.select(selector)
        for i, node in enumerate(nodes):
            url = make_fully_qualified_url(node[attr])
            filename = "%s_%s" % (i, os.path.basename(url))
            node[attr] = filename
            download_file(url, destination, request_fn=make_request, filename=filename, middleware_callbacks=middleware)

    def js_middleware(content, url, **kwargs):
        # Polyfill window.localStorage as iframes can't access localStorage.
        return content.replace("window.localStorage",
                "({setItem: function(){}, removeItem: function(){}})")

    # Download all static assets.
    # TODO(davidhu): Also download fonts referenced in http://www.africanstorybook.org/css/app.css
    download_assets("img[src]", "src")  # Images
    download_assets("link[href]", "href")  # CSS
    download_assets("script[src]", "src", middleware=js_middleware) # JS

    # Download all background images, e.g. <div style="background-image:url()">
    # (africanstorybook.org uses these for the main picture found on each page
    # of the storybook.)
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

    # Hide the African Storybook header nav bar.
    header = doc.select_one("#headerBar")
    if header:
        header["style"] = "display: none;"

    with open(os.path.join(destination, "index.html"), "w") as f:
        f.write(str(doc))

    zip_path = create_predictable_zip(destination)

    source_id = parse_qs(urlparse(book_url).query)['id'][0]
    raw_title = doc.select_one("head title").text
    title = raw_title.replace('African Storybook -', '').strip()

    # Extract the description from the "Share to Facebook" text.
    # TODO(davidhu): Find a more robust way to get the book description -- the
    # description doesn't seem to exist in another way in the page source.
    send_facebook_node = doc.select_one("a[onclick*=\"sendFacebook\"]")
    send_facebook_text = send_facebook_node["onclick"]
    match = SEND_FACEBOOK_RE.search(send_facebook_text)
    if match:
        description = match.group(1).strip("'\" ")
    else:
        raise Exception("Could not extract book description from Share to Facebook text: %s" % send_facebook_text)

    return nodes.HTML5AppNode(
        source_id=source_id,
        title=title,
        license=licenses.CC_BY,
        description=description,
        files=[files.HTMLZipFile(zip_path)],
    )


def make_request(url, *args, **kwargs):
    response = sess.get(url, *args, **kwargs)
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
