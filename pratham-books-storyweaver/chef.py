#!/usr/bin/env python3

import requests
import argparse
import cairosvg
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
TEMPLATE_URL = SEARCH_URL + '?page={page_num}\u0026search%5Bpublishers%5D%5B%5D={publisher_name}'
TEMPLATE_CREATED_BY_CHILDREN_URL = SEARCH_URL + '?page={page_num}\u0026search%5Bchild_created%5D=true'
TEMPLATE_LANGUAGE_NODE_ID = '{publisher}_{language}'
TEMPLATE_LEVEL_NODE_ID = '{publisher}_{language}_{level}'
TEMPLATE_LEVEL_TITLE = 'Level {num}'


# Cache
session = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter()
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

session.mount('https://storyweaver.org.in', basic_adapter)
session.mount(' https://storage.googleapis.com', basic_adapter)

_headers = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Connection': 'keep-alive'
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
        else:
            publishers.append(li.find('label').text.strip())

    # Remove the first item "All" from publishers
    publishers.pop(0)

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

    # Parse the name of the publisher to put into url
    publisher = pub.replace(',', '%2C')
    name = publisher.replace(' ', '+')

    # Get the first page of the publisher
    if (pub == 'Created by Children'):
        pub_first_page_url = TEMPLATE_CREATED_BY_CHILDREN_URL.format(page_num="1")
    else:
        pub_first_page_url = TEMPLATE_URL.format(page_num="1", publisher_name=name)
    
    # Get the json file of the page and parse it
    response = session.get(pub_first_page_url, headers=_headers)
    data = response.json()
    total_pages = data['metadata']['total_pages']
    LOGGER.info('\tThere is(are) in total %s page(s) for %s......\n' % (str(total_pages), pub))

    # List of books for the first page
    list = get_books_from_results(data['search_results'], list)

    # get the rest of the pages' books
    for i in range(1, total_pages):
        if (pub == 'Created by Children'):
            page_url = TEMPLATE_CREATED_BY_CHILDREN_URL .format(page_num=i+1)
        else:
            page_url = TEMPLATE_URL.format(page_num=i+1, publisher_name=name)
        response = session.get(page_url, headers=_headers)
        data = response.json() 
        list = get_books_from_results(data['search_results'], list)

    LOGGER.info('\tFinished getting all the books for %s\n\t====================\n' % (pub))
    return list


"""
Group books for each publisher by different languages.
Or
Group books in each language section of a publisher by different levels.
The parameter param could be language or level.
"""
def group_books(book_list, param):
    # sort languages alphabetically or sort levels
    sorted_books = sorted(book_list, key=lambda book: book[param])

    grouped_books = {}
    # group books by languages or by levels
    for key, item in groupby(sorted_books, lambda book: book[param]):
        grouped_books[key] = list(item)
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
        )

        channel.add_child(pubtopic)
        add_sub_topic_lang(publisher, pubtopic)


"""
Add subtopics about languages under a specific publisher topic.
"""
def add_sub_topic_lang(publisher, pubtopic):
    # Get all the books info for each publisher
    book_list = books_for_each_publisher(publisher)
    sorted_language_list = group_books(book_list, 'language')
    langs = sorted_language_list.keys()

    # Distribute books into subtopics according to languages
    for lang in langs:
        lang_id = TEMPLATE_LANGUAGE_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang)
        langsubtopic = TopicNode(
            source_id = lang_id, 
            title = lang,
        )
        pubtopic.add_child(langsubtopic)
        add_sub_topic_level(publisher, lang, langsubtopic, sorted_language_list)


"""
Add subtopics about levels of reading under a specific language subtopic.
"""
def add_sub_topic_level(publisher, lang, langsubtopic, list):
    sorted_level_list = group_books(list[lang], 'level')
    levels = sorted_level_list.keys()

    # Distribute books into subtopics according to levels
    for level in levels:
        level_id = TEMPLATE_LEVEL_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang, level=level)
        levelsubtopic = TopicNode(
            source_id = level_id, 
            title = TEMPLATE_LEVEL_TITLE.format(num=level),
        )
        langsubtopic.add_child(levelsubtopic)
        add_node_document(level, levelsubtopic, sorted_level_list)


"""
Add books under a specific level of reading.
"""
def add_node_document(level, levelsubtopic, list):
    # Add books according to level, language and publisher
    for item in list[level]:
        document_file = DocumentFile(path=item['link'])
        book = DocumentNode(
            title=item['title'], 
            source_id=str(item['source_id']), 
            author = item['author'],
            files=[document_file], 
            license=get_license(licenses.CC_BY),
            thumbnail = item.get('thumbnail'),
            description = item['description'],
        )
        levelsubtopic.add_child(book)


class PrathamBooksStoryWeaverSushiChef(SushiChef):
    # Add two additional arguments about login information.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arg_parser = argparse.ArgumentParser(parents=[self.arg_parser], description='Sushi Chef for Pratham Books\' StoryWeaver.')
        self.arg_parser.add_argument('--login_email', default='lywang07@gmail.com', help='Login email for Pratham Books\' StoryWeaver website.')
        self.arg_parser.add_argument('--login_password', default='1234567890', help='Login password for Pratham Books\' StoryWeaver website.')


    # Get the login information and log into the website with download_session.
    def pre_run(self, args, options):
        # Get login authenticity token
        result = DOWNLOAD_SESSION.get(SIGNIN_URL)
        html_doc = BeautifulSoup(result.content, 'html.parser')
        _authenticity_token = html_doc.find('input', {'name': 'authenticity_token'})['value']
        payload = {
            'authenticity_token': _authenticity_token,
            'user[email]': args['login_email'],
            'user[password]': args['login_password'],
        }
        # Login to StoryWeaver website
        DOWNLOAD_SESSION.post(SIGNIN_URL, data=payload)

        # Get the thumbnail
        thumbnail = html_doc.find('img', {'alt': 'Storyweaver beta'})['src']
        cairosvg.svg2png(url=thumbnail, scale=0.2, write_to="thumbnail.png")


    def get_channel(self, **kwargs):
        # Create a channel
        channel = ChannelNode(
            source_domain = 'storyweaver.org.in',
            source_id = 'Pratham_Books_StoryWeaver',
            title = 'Pratham Books\' StoryWeaver',
            thumbnail = 'thumbnail.png',
            description = '',
        )
        return channel


    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        # add topics and corresponding books to the channel
        add_topic_pub(channel)
        return channel


if __name__ == '__main__':

    #This code will run when the sushi chef is called from the command line.
    chef = PrathamBooksStoryWeaverSushiChef()
    chef.main()
