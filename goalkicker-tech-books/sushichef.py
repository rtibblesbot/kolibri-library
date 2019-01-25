#!/usr/bin/env python

import re
import requests

from bs4 import BeautifulSoup
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license
from ricecooker.utils.pdf import PDFParser


class GoalkickerChef(SushiChef):
    channel_info = {
        'CHANNEL_TITLE': 'Goalkicker',
        'CHANNEL_SOURCE_DOMAIN': 'goalkicker.com',
        'CHANNEL_SOURCE_ID': 'goalkicker',
        'CHANNEL_LANGUAGE': 'en',
        'CHANNEL_THUMBNAIL': 'https://goalkicker.com/JavaScriptBook/JavaScriptGrow.png', # picked an arbitrary book cover
        'CHANNEL_DESCRIPTION': 'Programming Notes for Professionals books',
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        # Soupify goalkicker main page
        gk_url = 'https://' + self.channel_info['CHANNEL_SOURCE_DOMAIN'] + '/'
        gk_soup = get_soup(gk_url)

        # Get urls for each goalkicker book
        els_with_page_urls = gk_soup.find_all(class_='bookContainer')
        page_urls = [gk_url + el.find('a')['href'] for el in els_with_page_urls]

        for page_url in page_urls:
            # Soupify book page
            page_soup = get_soup(page_url)

            # Extract and construct book info
            book_info = parse_book_info(page_soup)
            book_info['absolute_url'] = page_url + book_info['relative_url']

            # Add book to channel tree
            book_node_source_id = 'topic/' + book_info['subject']
            book_node = TopicNode(title=book_info['subject'], source_id=book_node_source_id)
            channel.add_child(book_node)

            # Get chapters info
            pdf_path = book_info['absolute_url']
            with PDFParser(pdf_path) as pdfparser:
                chapters = pdfparser.split_chapters()

            # Add chapter nodes
            for chapter in chapters:
                chapter_node_source_id = book_info['source_id'] + '/' + chapter['title']
                chapter_node = DocumentNode(
                    title=chapter['title'],
                    description=chapter['title'],
                    source_id=chapter_node_source_id,
                    license=get_license('CC BY-SA', copyright_holder='Stack Overflow'),
                    language='en',
                    files=[DocumentFile(path=chapter['path'], language='en')],
                )
                book_node.add_child(chapter_node)

        return channel


def get_soup(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html5lib')
    return soup


def parse_book_info(soup):
    str_with_book_title = soup.find(id='header').find('h1').get_text()
    suffix = ' book'
    book_title = str_with_book_title[:-len(suffix)] if str_with_book_title.endswith(suffix) else str_with_book_title

    suffix = ' Notes for Professionals'
    book_subject = book_title[:-len(suffix)] if book_title.endswith(suffix) else book_title

    book_description = 'A book about ' + book_subject

    book_source_id = 'book/' + book_subject

    str_with_book_url = soup.find('button', class_='download')['onclick']
    book_relative_url = re.search("location.href='(.+)'", str_with_book_url).group(1)

    return {
        'title': book_title,
        'subject': book_subject,
        'description': book_description,
        'source_id': book_source_id,
        'relative_url': book_relative_url
    }


if __name__ == '__main__':
    """
    Run this script on the command line using:
        python goalkicker_chef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    goalkicker_chef = GoalkickerChef()
    goalkicker_chef.main()

