#!/usr/bin/env python

import requests
import argparse
from cairosvg import svg2png
from lxml import html
from bs4 import BeautifulSoup
from itertools import groupby

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode,TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from le_utils.constants import licenses
from ricecooker.classes.licenses import get_license
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.config import LOGGER, DOWNLOAD_SESSION

# Variables
BASE_URL = 'https://storyweaver.org.in'
SIGNIN_URL = 'https://storyweaver.org.in/users/sign_in'
SEARCH_URL = 'https://storyweaver.org.in/search'
STORYWEAVER_THUMBNAIL = 'https://storyweaver.org.in/assets/Storyweaver-Beta-094e9dc433c9b2ed7a8ad010921cabeb.svg'
TEMPLATE_URL = 'https://storyweaver.org.in/search?page={page_num}\u0026search%5Bpublishers%5D%5B%5D={publisher_name}'
TEMPLATE_LANGUAGE_NODE_ID = '{publisher}_{language}'
TEMPLATE_LEVEL_NODE_ID = '{publisher}_{language}_{level}'
TEMPLATE_LEVEL_TITLE = 'Level {num}'

# Cache
session = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

session.mount('https://storyweaver.org.in/', forever_adapter)
session.mount(' https://storage.googleapis.com', forever_adapter)

_headers = {
    'X-CSRF-Token': 'ySOG84hNCKNit9G7arli4bSFzH00BeS9vVnRNnBY+hA=',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest'
}

"""
Helper method. Cut off invalid part of image url.
"""
def edit_img_ext(url):
    result = ''
    base = url.split('.')
    if base[-1] not in ('jpg', 'jepg', 'png'):
        tmp_ext = base.pop(-1)
        ext = tmp_ext.split('?')[0]
        result = '.'.join(base) + '.' + ext
    else:
        result = url
    return  result

"""
Helper method. Convert an svg image to a png image.
"""
def convert_svg_to_png(url):
    ext = url.split('.')
    path = 'channel_thumbnail.png'
    if ext[-1] != 'svg':
        print ("The image is not an svg.\n")
        path = url
    else:  
        svg2png(url=url, write_to=path, parent_width=130, parent_height=130, dpi=100)
    return path

"""
Get all the publishers from the website.
"""
def get_all_publishers():
    # Get the search page
    resp = session.get(SEARCH_URL)
    search_doc = BeautifulSoup(resp.content, 'html.parser')

    # Get a list of all the publishers
    publishers_lis = search_doc.find('ul', {'id': 'StoryPublishers'}).find_all('li')
    publishers = []
    for li in publishers_lis:
        # Change the name of StoryWeaver Community to match with the link provided by the website
        if li.find('label').text.strip() == 'StoryWeaver Community':
            publishers.append("storyweaver")
        # Created by Children publisher is redundant
        elif li.find('label').text.strip() == 'Created by Children':
            continue
        else:
            publishers.append(li.find('label').text.strip())

    # Remove the first item "All" from publishers
    publishers.pop(0)

    # Print info about publishers
    for pub in publishers:
        LOGGER.info('\tPublisher: %s\n' % (pub))
    LOGGER.info('\t====================\n')
    return publishers


"""
Get all the information about the books from the json file of each page 
for each publisher.
"""
def get_books_from_results(search_results, list):
    # Loop through all the books for one page
    for i in range(len(search_results)):
        download_link = BASE_URL + search_results[i]['links'][0]['download']['low_res_pdf']
        book_dict = {
            'link': download_link,
            'source_id': search_results[i]['id'],
            'title': search_results[i]['title'],
            'author': ', '.join(search_results[i]['authors']),
            'description': search_results[i]['synopsis'],
            'thumbnail': edit_img_ext(search_results[i]['image_url']),
            'language': search_results[i]['language'],
            'level': search_results[i]['reading_level']
        }
        list.append(book_dict)
    return list


"""
Get all the information about books for every publisher
"""
def books_for_each_publisher(pub):
    list = []

    LOGGER.info('\tCrawling books for %s......\n' % (pub))

    # Change the comma in the name string into %2C
    publisher = pub.replace(',', '%2C')
    # Parse the name of the publisher to put into url
    chars = publisher.split()
    name = ""
    for i in range(len(chars)-1):
        name = name + chars[i] + "+"
    name = name + chars[-1]

    # Get the first page of the publisher
    pub_first_page_url = TEMPLATE_URL.format(page_num="1", publisher_name=name)

    # Get the json file of the page and parse it
    response = session.get(pub_first_page_url, headers=_headers)
    data = response.json()

    # Get the total pages for the specific publisher
    total_pages = data['metadata']['total_pages']
    LOGGER.info('\tThere is(are) in total %s page(s) for %s......\n' % (str(total_pages), pub))

    search_results = data['search_results']
    # List of books for the first page
    LOGGER.info('\tCrawling books from page %s of %s......\n' % (str(1), pub))
    list = get_books_from_results(search_results, list)

    # get the rest of the pages' books
    for i in range(total_pages):
        if i == 0:
            continue
        else:
            LOGGER.info('\tCrawling books from page %s of %s......\n' % (str(i+1), pub))
            page_url = TEMPLATE_URL.format(page_num=i+1, publisher_name=name)
            response = session.get(page_url, headers=_headers)
            data=response.json()
            search_results = data['search_results']
            list = get_books_from_results(search_results, list)

    LOGGER.info('\tFinish crawling all the books for %s\n\t====================\n' % (pub))
    return list


"""
Group books for each publisher by different languages.
"""
def group_books_by_language(book_list):
    # sort languages alphabetically
    sorted_books = sorted(book_list, key=lambda book: book['language'])

    grouped_books = {}
    # group books by languages
    for lang, item in groupby(sorted_books, lambda book: book['language']):
        grouped_books[lang] = list(item)
    return grouped_books


"""
Group books in each language section of a publisher by different levels.
"""
def group_books_by_level(book_list):
    # sort levels by levels
    sorted_books = sorted(book_list, key=lambda book: book['level'])

    grouped_books = {}
    # group books by levels
    for level, item in groupby(sorted_books, lambda book: book['level']):
        grouped_books[level] = list(item)
    return grouped_books

"""
Add topics about publishers in the channel.
"""
def add_topic_pub(channel):
    # Get all the publishers and loop through them
    all_pubs = get_all_publishers()
    for publisher in all_pubs:
        if publisher == 'storyweaver':
            pub_title = 'StoryWeaver Community'
        else:
            pub_title = publisher

        # Add a topic for each publisher
        pubtopic = TopicNode(
            source_id = publisher.replace(" ", "_"), 
            title = pub_title,
            description = "Books from the publisher " + publisher
        )

        channel.add_child(pubtopic)
        add_sub_topic_lang(publisher, pubtopic)

"""
Add subtopics about languages under a specific publisher topic.
"""
def add_sub_topic_lang(publisher, pubtopic):
    # Get all the books info for each
    book_list = books_for_each_publisher(publisher)
    sorted_language_list = group_books_by_language(book_list)
    langs = sorted_language_list.keys()

    # Distribute books into subtopics according to languages
    for lang in langs:
        lang_id = TEMPLATE_LANGUAGE_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang)
        langsubtopic = TopicNode(
            source_id = lang_id, 
            title = lang,
            description = "Books from the publisher " + publisher + " in " + lang
        )
        pubtopic.add_child(langsubtopic)
        add_sub_topic_level(publisher, lang, langsubtopic, sorted_language_list)

"""
Add subtopics about levels of reading under a specific language subtopic.
"""
def add_sub_topic_level(publisher, lang, langsubtopic, sorted_language_list):
    sorted_level_list = group_books_by_level(sorted_language_list[lang])
    levels = sorted_level_list.keys()

    # Distribute books into subtopics according to levels
    for level in levels:
        level_id = TEMPLATE_LEVEL_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang, level=level)
        levelsubtopic = TopicNode(
            source_id = level_id, 
            title = TEMPLATE_LEVEL_TITLE.format(num=level),
            description = "Books from the publisher " + publisher + " in " + lang + " of level " + level 
        )
        langsubtopic.add_child(levelsubtopic)
        add_node_document(level, levelsubtopic, sorted_level_list)

"""
Add books under a specific level of reading.
"""
def add_node_document(level, levelsubtopic, sorted_level_list):
    # Add books according to level, language and publisher
    for item in sorted_level_list[level]:
        document_file = DocumentFile(path=item['link'])
        bookpdf = DocumentNode(
            title=item['title'], 
            source_id=str(item['source_id']), 
            author = item['author'],
            files=[document_file], 
            license=get_license(licenses.CC_BY),
            thumbnail = item.get('thumbnail'),
            description = item['description'],
        )
        levelsubtopic.add_child(bookpdf)


class PrathamBooksStoryWeaverSushiChef(SushiChef):
    # Add two additional arguments about login information.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arg_parser = argparse.ArgumentParser(parents=[self.arg_parser], description='Sushi Chef for Pratham Books\' StoryWeaver.')
        self.arg_parser.add_argument('--login_email', default='lywang07@gmail.com', help='Login email for Pratham Books\' StoryWeaver website.')
        self.arg_parser.add_argument('--login_password', default='1234567890', help='Login password for Pratham Books\' StoryWeaver website.')


    # Get the login information and log into the website with download_session.
    def pre_run(self, *args, **kwargs):
        arguments, options = self.parse_args_and_options()
        # Get login csrf token
        result = DOWNLOAD_SESSION.get(SIGNIN_URL)
        tree = html.fromstring(result.text)
        _authenticity_token = list(set(tree.xpath("//input[@name='authenticity_token']/@value")))[0]
        payload = {
            'authenticity_token': _authenticity_token,
            'user[email]': arguments['login_email'],
            'user[password]': arguments['login_password'],
        }

        # Login to StoryWeaver website
        DOWNLOAD_SESSION.post(SIGNIN_URL, data=payload)

    def get_channel(self, **kwargs):
        # Create a channel
        channel = ChannelNode(
            source_domain = 'storyweaver.org.in',
            source_id = 'Pratham_Books_StoryWeaver',
            title = 'Pratham Books\' StoryWeaver',
            thumbnail = convert_svg_to_png(STORYWEAVER_THUMBNAIL),
            description = '',
        )

        return channel

    def construct_channel(self, *args, **kwargs):
        channel = self.get_channel(**kwargs)

        # add topics and corresponding books to the channel
        add_topic_pub(channel)

        return channel


if __name__ == '__main__':

    # This code will run when the sushi chef is called from the command line.
    chef = PrathamBooksStoryWeaverSushiChef()
    chef.main()
