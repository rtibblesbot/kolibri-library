#!/usr/bin/env python3

import os
import tempfile
import requests
import argparse
import uuid
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode,TopicNode, HTML5AppNode
from ricecooker.classes.files import HTMLZipFile
from le_utils.constants import licenses
from ricecooker.classes.licenses import get_license
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.config import LOGGER, DOWNLOAD_SESSION
from ricecooker.utils.html import WebDriver
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.html_writer import HTMLWriter

# Variables
BASE_API_URL = 'https://storyweaver.org.in/api/v1/'
FILTERS_URL = 'https://storyweaver.org.in/api/v1/books/filters'
SIGNIN_URL = 'https://storyweaver.org.in/users/sign_in'
BOOK_SEARCH_URL = 'https://storyweaver.org.in/api/v1/books-search'
READ_URL = 'https://storyweaver.org.in/api/v1/stories/{}/read'

# Template for HTML5 App
PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ENVIRONMENT = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(PATH, 'template')),
    trim_blocks=False)

# Cache
session = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

session.mount('https://storyweaver.org.in', basic_adapter)
session.mount(BASE_API_URL, basic_adapter)


"""
Get a list of all books in African Storybooks website.
"""
def get_AS_booklist_dict():
    with WebDriver("http://www.africanstorybook.org/", delay=20000) as driver:

        js_code = """
            var textElement = document.createElement("textarea");
            function decodeHtml(html) {
                textElement.innerHTML = html;
                return textElement.value;
            }

            // Safely decode HTML entities in title field.
            for (var i = bookItems.length - 1; i >= 0; i--) {
                bookItems[i].title = decodeHtml(bookItems[i].title);
            }

            return bookItems;
        """

        books = driver.execute_script(js_code)
        names = []
        # Create a list of book names
        for book in books:
            names.append(book['title'].lower())
        dictionary = {}
        # Create a dictionary of books with name as key
        for (name, book) in zip(names, books):
            if name in dictionary:
                dictionary[name].append(book)
            else:
                dictionary[name] = [book]
        return dictionary

def get_html5_app_zip_path(slug):
    resp = session.get(READ_URL.format(slug))
    if resp.status_code == 200:
        resp = resp.json()
    else:
        LOGGER.info('The story {} is not available.\n'.format(slug))
        return None
    content = ""
    for page in (resp['data']['pages']):
        soup = BeautifulSoup(page['html'], 'html.parser')
        if page.get('coverImage', None):
            img_src = page['coverImage']['sizes'][-1]['url']
            soup.img['src'] = img_src
        content = content + "\n" + str(soup)

    context = {
        'content': content
    }

    handle, destination = tempfile.mkstemp(suffix=".zip")
    os.close(handle)
    htmlwriter = HTMLWriter(destination)
    with htmlwriter as f:
        index_html = TEMPLATE_ENVIRONMENT.get_template('indexfile').render(context)
        f.write_index_contents(index_html)

    LOGGER.info(destination)
    return destination


"""
Get all the information about the books from the json file of each page 
for each category.
"""
def get_books_from_results(books):
    booklist = []
    # Loop through all the books for one page
    for i in range(len(books)):
        publisher = books[i]['publisher']['name']
        language = books[i]['language']
        level = books[i]['level']
        try:
            thumbnail = books[i]['coverImage']['sizes'][0]['url']
        except TypeError:
            thumbnail = None

        book_dict = {
            'slug': books[i]['slug'],
            'source_id': books[i]['id'],
            'title': books[i]['title'],
            'author': ', '.join([item['name'] for item in books[i]['authors']]),
            'description': books[i]['description'],
            'thumbnail': thumbnail,
            'language': language,
            'level': level,
            'publisher': publisher,
        }
        booklist.append(book_dict)

    return booklist


"""
Get all the information about books for every category
"""
def books_for_each_category(category):
    LOGGER.info('\tCrawling books for {}......\n'.format(category))

    # Get the json file of the page and parse it
    payload = {'page': 1, 'per_page': 24, 'categories[]': category}
    response = session.get(BOOK_SEARCH_URL, params=payload)
    data = response.json()
    total_pages = data['metadata']['totalPages']
    LOGGER.info('\tThere is(are) in total {} page(s) for {}......\n'.format(total_pages, category))

    # List of books for the first page
    booklist = get_books_from_results(data['data'])

    # get the rest of the pages' books
    for i in range(1, total_pages):
        payload['page'] = i+1
        response = session.get(BOOK_SEARCH_URL, params=payload)
        data = response.json() 
        booklist += get_books_from_results(data['data'])

    LOGGER.info('\tFinished getting all the books for {}\n\t====================\n'.format(category))
    return booklist


def download_all():
    resp = session.get(FILTERS_URL).json()
    categories = [item['name'] for item in resp['data']['category']['queryValues']]

    channel_tree = {}
    for category in categories:
        channel_tree[category] = {}
        booklist = books_for_each_category(category)

        for book in booklist:
            publisher = book['publisher']
            language = book['language']
            level = book['level']

            if publisher in channel_tree[category]:
                if language in channel_tree[category][publisher]:
                    if level in channel_tree[category][publisher][language]:
                        channel_tree[category][publisher][language][level].append(book)
                    else:      
                        channel_tree[category][publisher][language][level] = [book]
                else:
                    channel_tree[category][publisher][language] = {}
                    channel_tree[category][publisher][language][level] = [book]
            else:
                channel_tree[category][publisher] = {}
                channel_tree[category][publisher][language] = {}
                channel_tree[category][publisher][language][level] = [book]
    return channel_tree


def parse_through_tree(tree, parent_topic, as_booklist):
    for topic_name in sorted(tree):
        content = tree[topic_name]
        try:
            title = 'Level {}'.format(int(topic_name))
        except ValueError:
            title = topic_name
        current_topic = TopicNode(
            source_id = '{}_{}'.format(parent_topic.source_id, topic_name.replace(' ', '_')),
            title = title,
        )
        parent_topic.add_child(current_topic)
        if type(content) is list:
            add_node_document(content, current_topic, as_booklist)
        else:
            parse_through_tree(content, current_topic, as_booklist)


"""
Check if the story in StoryWeaver is also in African Storybooks.
"""
def check_if_story_in_AS(as_booklist, story_name):
    result = as_booklist.get(story_name.lower().rstrip())
    if result and len(result) == 1:
        return True, result[0]['id']
    else:
        return False, None 


"""
Add books under a specific level of reading.
"""
def add_node_document(booklist, level_topic, as_booklist):
    # Add books according to level, language and publisher
    for item in booklist:
        # initailize the source domain and content_id
        domain = uuid.uuid5(uuid.NAMESPACE_DNS, 'storyweaver.org.in')
        book_id = str(item['source_id'])

        """ 
        If the publisher is AS and the book is found, 
        then change the source_domain and content_id
        """
        if item['publisher'] == 'African Storybook Initiative':
            check = check_if_story_in_AS(as_booklist, item['title'])
            if check[0] == True:
                domain = uuid.uuid5(uuid.NAMESPACE_DNS,'www.africanstorybook.org')
                book_id = check[1]

        link = get_html5_app_zip_path(item['slug'])
        if link:
            html5_file = HTMLZipFile(path=link)
            book = HTML5AppNode(
                title = item['title'], 
                source_id = book_id, 
                author = item['author'],
                files = [html5_file],
                license = get_license(licenses.CC_BY, copyright_holder='Pratham Books'),
                thumbnail = item.get('thumbnail'),
                description = item['description'],
                domain_ns = domain,
            )
            level_topic.add_child(book)


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


    def get_channel(self, **kwargs):
        # Create a channel
        channel = ChannelNode(
            source_domain = 'storyweaver.org.in',
            source_id = 'Pratham_Books_StoryWeaver',
            title = 'Pratham Books\' StoryWeaver',
            description = '',
            language = 'en',
        )
        return channel


    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        # add topics and corresponding books to the channel
        channel_tree = download_all()
        as_booklist = get_AS_booklist_dict()
        for category in sorted(channel_tree):
            category_topic = TopicNode(
                source_id = category.replace(' ', '_'), 
                title = category,
            )
            channel.add_child(category_topic)
            parse_through_tree(channel_tree[category], category_topic, as_booklist)
        return channel


if __name__ == '__main__':

    #This code will run when the sushi chef is called from the command line.
    chef = PrathamBooksStoryWeaverSushiChef()
    chef.main()
