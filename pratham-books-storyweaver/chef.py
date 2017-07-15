#!/usr/bin/env python

import requests
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


BASE_URL = "https://storyweaver.org.in"
SIGNIN_URL = "https://storyweaver.org.in/users/sign_in"
SEARCH_URL = "https://storyweaver.org.in/search"
TEMPLATE_URL = "https://storyweaver.org.in/search?page={page_num}\u0026search%5Bpublishers%5D%5B%5D={publisher_name}"
TEMPLATE_LANGUAGE_NODE_ID = "{publisher}_{language}"
TEMPLATE_LEVEL_NODE_ID = "{publisher}_{language}_{level}"
TEMPLATE_LEVEL_TITLE = "Level {num}"


session = requests.Session()


# Get login csrf token
result = DOWNLOAD_SESSION.get(SIGNIN_URL)
tree = html.fromstring(result.text)
authenticity_token = list(set(tree.xpath("//input[@name='authenticity_token']/@value")))[0]

headers = {
    'X-CSRF-Token': 'ySOG84hNCKNit9G7arli4bSFzH00BeS9vVnRNnBY+hA=',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest'
}
payload = {
    'authenticity_token': authenticity_token,
    'user[email]': 'lywang07@gmail.com',
    'user[password]': '1234567890',
}

# Login to StoryWeaver website
DOWNLOAD_SESSION.post(SIGNIN_URL, data=payload)

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
    response = session.get(pub_first_page_url, headers=headers)
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
            response = session.get(page_url, headers=headers)
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


class PrathamBooksStoryWeaverSushiChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """

    # 1. PROVIDE CHANNEL INFO  (replace <placeholders> with your own values)
    ############################################################################
    channel_info = {    #
        'CHANNEL_SOURCE_DOMAIN': 'storyweaver.org.in',       # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'pratham_books_storyweaver',                   # channel's unique id
        'CHANNEL_TITLE': 'Pratham Books\' StoryWeaver',
        # 'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to image file
        # 'CHANNEL_DESCRIPTION': '''Welcome to StoryWeaver from Pratham Books, 
        #                         a whole new world of children’s stories, where 
        #                         all barriers fall away. It is a platform that 
        #                         hosts stories in languages from all across India 
        #                         and beyond. So that every child can have an endless 
        #                         stream of stories in her mother tongue to read and enjoy''',
    }
    
    # 2. CONSTRUCT CHANNEL
    ############################################################################
    def construct_channel(self, *args, **kwargs):
        """
        This method is reponsible for creating a `ChannelNode` object from the info
        in `channel_info` and populating it with TopicNode and ContentNode children.
        """
        # Create channel
        ########################################################################
        channel_info = self.channel_info
        channel = ChannelNode(
            source_domain = channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = channel_info['CHANNEL_SOURCE_ID'],
            title = channel_info['CHANNEL_TITLE'],
            thumbnail = channel_info.get('CHANNEL_THUMBNAIL'),
            description = channel_info.get('CHANNEL_DESCRIPTION'),
        )

        # Get all the publishers and loop through them
        all_pubs = get_all_publishers()
        for publisher in all_pubs:
            if publisher == 'storyweaver':
                pub_title = 'StoryWeaver Community'
            else:
                pub_title = publisher

            # Add a topic for each publisher
            exampletopic = TopicNode(source_id=publisher.replace(" ", "_"), title=pub_title)

            channel.add_child(exampletopic)

            # Get all the books info for each
            book_list = books_for_each_publisher(publisher)
            sorted_language_list = group_books_by_language(book_list)
            langs = sorted_language_list.keys()

            # Distribute books into subtopics according to languages
            for lang in langs:
                lang_id = TEMPLATE_LANGUAGE_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang)
                langsubtopic = TopicNode(source_id=lang_id, title=lang)
                exampletopic.add_child(langsubtopic)
                sorted_level_list = group_books_by_level(sorted_language_list[lang])
                levels = sorted_level_list.keys()

                # Distribute books into subtopics according to levels
                for level in levels:
                    level_id = TEMPLATE_LEVEL_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang, level=level)
                    levelsubtopic = TopicNode(source_id=level_id, title=TEMPLATE_LEVEL_TITLE.format(num=level))
                    langsubtopic.add_child(levelsubtopic)

                    for item in sorted_level_list[level]:
                        document_file = DocumentFile(path=item['link'])
                        examplepdf = DocumentNode(
                            title=item['title'], 
                            source_id=str(item['source_id']), 
                            author = item['author'],
                            files=[document_file], 
                            license=get_license(licenses.CC_BY),
                            thumbnail = item.get('thumbnail'),
                            description = item['description'],
                        )
                        levelsubtopic.add_child(examplepdf)

        return channel


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = PrathamBooksStoryWeaverSushiChef()
    chef.main()
