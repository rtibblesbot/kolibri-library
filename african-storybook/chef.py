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

import asyncio
from pyppeteer import launch
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
sess.mount('https://www.africanstorybook.org/', forever_adapter)
sess.mount('https://fonts.googleapis.com/', forever_adapter)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}

FOLDER_STORAGE = os.path.join(os.getcwd(), 'chefdata', "storage")
FOLDER_STORAGE_PARALLEL = os.path.join(os.getcwd(), 'chefdata', "parallel")
FOLDER_STORAGE_BROWSER = os.path.join(os.getcwd(), 'chefdata', "test2")

if not os.path.exists(FOLDER_STORAGE):
    os.mkdir(FOLDER_STORAGE)

if not os.path.exists(FOLDER_STORAGE_PARALLEL):
    os.mkdir(FOLDER_STORAGE_PARALLEL)

if not os.path.exists(FOLDER_STORAGE_BROWSER):
    os.mkdir(FOLDER_STORAGE_BROWSER)


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
        'CHANNEL_SOURCE_ID': "african-storybook_2",
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
            source_domain=channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id=channel_info['CHANNEL_SOURCE_ID'],
            title=channel_info['CHANNEL_TITLE'],
            # thumbnail=channel_info.get('CHANNEL_THUMBNAIL'),
            description=channel_info.get('CHANNEL_DESCRIPTION'),
            language="mul",
        )

        # download_book("https://www.africanstorybook.org/reader.php?id=16451", "16451", "title", "author", "description", "en")

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
                    print(book)
                    LOGGER.debug('      BOOK source_id=' + book.source_id)
                    level_node.add_child(book)

        return channel


async def download_all_epubs():
    dict_page_download = {}
    browser = await launch(headless=True)
    page = await browser.newPage()
    await page.goto('https://www.africanstorybook.org/', {'waitUntil': 'networkidle2'})
    await page._client.send('Page.setDownloadBehavior',
                            {'behavior': 'allow', 'downloadPath': FOLDER_STORAGE_BROWSER, 'waitUntil': 'networkidle2'})
    time.sleep(10)
    books = await page.evaluate('bookItems')
    lst_books = os.listdir(FOLDER_STORAGE_BROWSER)
    await page.close()
    await browser.close()
    for book in books:
        book_name = "asb{}.epub".format(book.get('id'))
        if book_name not in lst_books:
            LOGGER.info("Book name %s" % book_name)
            page, browser = await download_epub_book(book.get('id'))
            dict_page_download[book_name] = {'page': page, 'browser':browser}
            lst_finished_dl_book = await find_finished_download(dict_page_download)
            if len(lst_finished_dl_book) > 2:
                for book_name_finish in lst_finished_dl_book:
                    dict_page_browser = dict_page_download.get(book_name_finish)
                    if not dict_page_browser.get('page').isClosed():
                        page_finished = dict_page_browser.get('page')
                        browser_finished = dict_page_browser.get('browser')
                        await page_finished.close()
                        await browser_finished.close()
                        dict_page_download.pop(book_name_finish)
        else:
            LOGGER.info("Book name %s already exists" % book_name)
    await browser.close()


async def download_epub_book(book_id):
    browser = await launch(headless=True)
    pages = await browser.pages()
    page = pages[0]
    await page.goto('https://www.africanstorybook.org/', {'waitUntil': 'networkidle2'})
    await page._client.send('Page.setDownloadBehavior',
                            {'behavior': 'allow', 'downloadPath': FOLDER_STORAGE_BROWSER, 'waitUntil': 'networkidle2'})
    await page.evaluate(pageFunction="doDownloadEpub('{}')".format(book_id))
    LOGGER.info("Downloading book %s" % (book_id))
    return page, browser


async def find_finished_download(dict_page_download):
    book_downloads = os.listdir(FOLDER_STORAGE_BROWSER)
    lst_finished_dl_book = []
    for book_name in dict_page_download:
        if book_name in book_downloads:
            lst_finished_dl_book.append(book_name)
    return lst_finished_dl_book


def download_all(kwargs):
    scraped_ids = set()

    with WebDriver("https://www.africanstorybook.org/", delay=20000) as driver:
        books = driver.execute_script("return bookItems;")
        if 'sample' in kwargs and kwargs['sample']:
            random.seed(42)
            sample_size = int(kwargs['sample'])
            books = random.sample(books, sample_size)
        # total_books = len(books)

        # Build a dict of {African Storybook language ID: language name}
        lst_books = os.listdir(FOLDER_STORAGE)

        languages_html = driver.execute_script("return languages;")
        language_id_map = {}
        for node in BeautifulSoup(languages_html, "html.parser"):
            language_id_map[node["value"]] = node.text.strip()
        channel_tree = defaultdict(lambda: defaultdict(list))

        for i, book in enumerate(books):
            is_approved = False
            book_id = book["id"]
            if book.get('approved') == "1":
                is_approved = True
            if book_id in scraped_ids and not is_approved:
                continue
            scraped_ids.add(book_id)

            # book_url = "http://www.africanstorybook.org/reader.php?id=%s" % book_id
            if is_approved:
                # book_url = "https://www.africanstorybook.org/read/downloadbook.php?id=%s&a=1&d=0&layout=landscape" % book_id

                book_name = 'asb{}.epub'.format(book_id)
                book_path = None
                if book_name in lst_books:
                    book_path = os.path.join(FOLDER_STORAGE, book_name)
                    level = book["level"]
                    language_ids = book["lang"].split(",")
                    languages = [language_id_map[code.strip()] for code in language_ids if code.strip()]
                    author = "%s; Others: %s" % (book["author"], book["people"])
                    title = strip_level_from_title(html.unescape(book["title"]))
                    description = html.unescape(book["summary"])

                    for language in languages:
                        book = create_node_for_book(book_path, book_name, book_id, title, author, description, language)

                        if book:
                            LOGGER.info("... downloaded a Level %s %s book titled %s" % (
                            level, language, str(title).encode('utf8')))
                            channel_tree[language][level].append(book)
                        else:
                            LOGGER.warning("... WARNING: book %s not found in %s" % (book_id, language))
    return channel_tree


def create_node_for_book(book_path, book_name, book_id, title, author, description, language):
    """Downloads a single book from African Storybook website given its URL."""
    # -- 0. Parse --
    # doc = get_parsed_html_from_url(book_url)
    #
    # if doc.body and "The storybook you wanted is not part of the African Storybook website" in doc.body.text:
    #     return None, None, []
    #
    # # Extract copyright holder.
    # back_cover = doc.select_one(".backcover_copyright")
    # if back_cover:
    #     copyright_holder = str(back_cover.contents[0]).strip(" ©")
    # else:
    #     LOGGER.warning("WARNING: failed to find backcover_copyright for url:" + book_url)
    copyright_holder = 'African Storybook Initiative'

    return nodes.DocumentNode(
        source_id="%s|%s|%s" % (language, book_id, book_name),
        title=truncate_metadata(title),
        license=licenses.CC_BYLicense(
            copyright_holder=truncate_metadata(copyright_holder)),
        description=description,
        author=truncate_metadata(author),
        files=[files.EPubFile("{}".format(book_path))],
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
    html = make_request(url, *args, **kwargs).text
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
    start_time = time.time()
    print(start_time)
    print(time.localtime(start_time))
    asyncio.run(download_all_epubs(),debug=True)
    end_time = time.time()
    print(end_time)
    print(end_time - start_time)
    # chef = AfricanStorybookChef()
    # chef.main()
