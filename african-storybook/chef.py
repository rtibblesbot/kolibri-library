#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sushi Chef for African Storybook: http://www.africanstorybook.org/
We make an HTML5 app out of each interactive reader.
"""

import os
import re
import requests
from collections import OrderedDict
import html

from pyppeteer import launch
import time
import asyncio
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
FOLDER_STORAGE_BROWSER = os.path.join(os.getcwd(), 'chefdata', "test3")
# copyright_holder = 'African Storybook Initiative'
COPYRIGHT_HOLDER = 'African Storybook Initiative'

if not os.path.exists(FOLDER_STORAGE):
    os.mkdir(FOLDER_STORAGE)

if not os.path.exists(FOLDER_STORAGE_PARALLEL):
    os.mkdir(FOLDER_STORAGE_PARALLEL)

if not os.path.exists(FOLDER_STORAGE_BROWSER):
    os.mkdir(FOLDER_STORAGE_BROWSER)

ABS_FOLDER_STORAGE_BROWSER = os.path.abspath(FOLDER_STORAGE_BROWSER)


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
        'CHANNEL_SOURCE_ID': "african-storybook-2",
        'CHANNEL_TITLE': "African Storybook Library (multiple languages)",
        'CHANNEL_THUMBNAIL': "asb120.png",
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
            thumbnail=channel_info.get('CHANNEL_THUMBNAIL'),
            description=channel_info.get('CHANNEL_DESCRIPTION'),
            language="mul",
        )

        books, dict_languages = get_languages_and_books()
        LOGGER.debug('STARTING TO CREATE THE RICECOOKER CHANNEL TREE')
        dict_node_languages = {}
        dict_node_levels = OrderedDict()

        for key_language in dict_languages:
            if key_language == "0":
                LOGGER.info('skipping language 0')
                continue
            language = dict_languages.get(key_language)
            lang_obj = get_lang_by_name_with_fallback(language)
            LOGGER.debug('LANGUAGE ' + language + '   lang_obj=' + str(lang_obj))

            language_node = nodes.TopicNode(source_id=language, title=language, language=lang_obj.code)
            dict_node_languages[key_language] = language_node
            channel.add_child(language_node)

        for book in books:
            book_lang = dict_languages.get(book.get('lang'))
            if book_lang:
                lang_node = dict_node_languages.get(book.get('lang'))
                if not dict_node_levels.get(book_lang) or not dict_node_levels.get(book_lang).get(book.get('level')):
                    topic_level_node = nodes.TopicNode(source_id="{}-{}".format(book_lang, book.get('level')),
                                                       title='Level {}'.format(book.get('level')),
                                                       )
                    if not dict_node_levels.get(book_lang):
                        dict_node_levels[book_lang] = {book.get('level'): topic_level_node}
                    else:
                        dict_node_levels[book_lang].update({book.get('level'): topic_level_node})
                    lang_node.add_child(topic_level_node)
                    lang_node.sort_children()
                else:
                    topic_level_node = dict_node_levels.get(book_lang).get(book.get('level'))

                book_name = 'asb{}.epub'.format(book.get('id'))
                book_path = os.path.join(FOLDER_STORAGE, book_name)
                book_node = nodes.DocumentNode(
                    source_id="%s|%s|%s" % (book_lang, book.get('level'), book_name),
                    title=truncate_metadata(html.unescape(book.get('title'))),
                    license=licenses.CC_BYLicense(copyright_holder=truncate_metadata(COPYRIGHT_HOLDER)),
                    description=book.get('summary'),
                    author=truncate_metadata(book.get('author')),
                    files=[files.EPubFile("{}".format(book_path))],
                    language=get_lang_by_name_with_fallback(book_lang),
                )
                topic_level_node.add_child(book_node)
        return channel


async def download_all_epubs():
    dict_page_download = {}
    browser = await launch(headless=True)
    # await browser.close()
    pages = await browser.pages()
    page = pages[0]
    await page.goto('https://www.africanstorybook.org/', {'waitUntil': 'networkidle2'})
    await page._client.send('Page.setDownloadBehavior',
                            {'behavior': 'allow', 'downloadPath': FOLDER_STORAGE_BROWSER, 'waitUntil': 'networkidle2'})
    time.sleep(10)
    books = await page.evaluate('bookItems')
    lst_books = os.listdir(FOLDER_STORAGE_BROWSER)
    await page.close()
    # books = books[0:1000]
    for book in books:
        book_name = "asb{}.epub".format(book.get('id'))
        if book_name not in lst_books:
            LOGGER.info("Book name %s" % book_name)
            page, browser = await download_epub_book(book.get('id'))
            dict_page_download[book_name] = {'page': page, 'browser': browser}
            lst_finished_dl_book = await find_finished_download(dict_page_download)
            if len(lst_finished_dl_book) > 1:
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
    lst_finished_dl_book = []
    for book_name in dict_page_download:
        if os.path.exists(os.path.join(ABS_FOLDER_STORAGE_BROWSER, book_name)):
            lst_finished_dl_book.append(book_name)
    return lst_finished_dl_book


def get_languages_and_books():
    with WebDriver("https://www.africanstorybook.org/", delay=10000) as driver:
        books = driver.execute_script("return bookItems;")
        languages_html = driver.execute_script("return languages;")
        language_id_map = {}
        bs_html_page = BeautifulSoup(languages_html, "html.parser")
        for node in bs_html_page:
            language_id_map[node["value"]] = node.text.strip()

    return books, language_id_map


def strip_level_from_title(title):
    return re.sub("\(Level .\)", "", title).strip()


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    First need to be run only with asyncio.run to download all epub books 
    chef = AfricanStorybookChef()
    chef.main()
    
    NEED TO make this work in one call
    """
    # asyncio.run(download_all_epubs())
    AfricanStorybookChef().main()
