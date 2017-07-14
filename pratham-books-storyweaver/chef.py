#!/usr/bin/env python

import requests
import os
from lxml import html
from bs4 import BeautifulSoup
from itertools import groupby

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode, AudioNode
from ricecooker.classes.files import DocumentFile, HTMLZipFile
from le_utils.constants import licenses
from ricecooker.classes.licenses import get_license
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file

BASE_URL = "https://storyweaver.org.in"
SIGNIN_URL = "https://storyweaver.org.in/users/sign_in"
SEARCH_URL = "https://storyweaver.org.in/search"
TEMPLATE_URL = "https://storyweaver.org.in/search?page={page_num}\u0026search%5Bpublishers%5D%5B%5D={publisher_name}"
TEMPLATE_NAME = "Book-{id}"
TEMPLATE_LANGUAGE_NODE_ID = "{publisher}_{language}"
TEMPLATE_LEVEL_NODE_ID = "{publisher}_{language}_{level}"
TEMPLATE_LEVEL_TITLE = "Level {num}"

session = requests.Session()


# Get login csrf token
result = session.get(SIGNIN_URL)
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
session.post(SIGNIN_URL, data=payload)

def get_all_publishers():
    # Get the search page
    resp = session.get(SEARCH_URL)
    search_doc = BeautifulSoup(resp.content, 'html.parser')

    # Get a list of all the publishers
    publishers_lis = books.find('ul', {'id': 'StoryPublishers'}).find_all('li')
    publishers = []
    for li in publishers_lis:
        publishers.append(li.find('label').text.strip())

    # Remove the first item "All" from publishers
    publishers.pop(0)
    return publishers

def books_for_each_publisher(publisher):
    # Change the comma in the name string into %2C
    publisher = publisher.replace(",", "%2C")
    # Parse the name of the publisher to put into url
    list = publisher.split()
    name = ""
    for i in range(len(list)-1):
        name = name + list[i] + "+"
    name = name + list[-1]

    # Get the first page of the publisher
    pub_first_page_url = TEMPLATE_URL.format(page_num="1", publisher_name=name)

    response = session.get(pub_first_page_url, data=payload, headers=headers)
    data = response.json()
    search_results = data['search_results']
    list = []
    for i in range(len(search_results)):
        download_link = BASE_URL + search_results[i]['links'][0]['download']['low_res_pdf']
        book_dict = {
            'link': download_link,
            'source_id': search_results[i]['id'],
            'title': search_results[i]['title'],
            'author': ', '.join(search_results[i]['authors']),
            'description': search_results[i]['synopsis'],
            'thumbnail': search_results[i]['image_url'],
            'language': search_results[i]['language'],
            'level': search_results[i]['reading_level']
        }
        list.append(book_dict)
    return list

def group_books_by_language(book_list):
    # sort languages alphabetically
    sorted_books = sorted(book_list, key=lambda book: book['language'])

    grouped_books = {}
    # group books by languages
    for lang, item in groupby(sorted_books, lambda book: book['language']):
        grouped_books[lang] = list(item)
    return grouped_books

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
        # 'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) description of the channel (optional)
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

        # Create topics to add to your channel
        ########################################################################
        # Here we are creating a topic named 'Example Topic'
        publisher = "The Rosetta Foundation"
        exampletopic = TopicNode(source_id=publisher.replace(" ", "_"), title=publisher)

        channel.add_child(exampletopic)

        # You can also add subtopics to topics
        # Here we are creating a subtopic named 'Example Subtopic'
        # examplesubtopic = TopicNode(source_id="topic-1a", title="Example Subtopic")
        # # TODO: Create your subtopic here
        # mysubsubtopic = TopicNode(source_id="my-1a", title="My Subtopic 1a")

        # Now we are adding 'Example Subtopic' to our 'Example Topic'
        # exampletopic.add_child(examplesubtopic)
        # # TODO: Add your subtopic to your topic here
        # mytopic.add_child(mysubsubtopic)

        book_list = books_for_each_publisher(publisher)
        sorted_language_list = group_books_by_language(book_list)
        langs = sorted_language_list.keys()
        for lang in langs:
            lang_id = TEMPLATE_LANGUAGE_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang)
            langsubtopic = TopicNode(source_id=lang_id, title=lang)
            exampletopic.add_child(langsubtopic)
            sorted_level_list = group_books_by_level(sorted_language_list[lang])
            levels = sorted_level_list.keys()
            for level in levels:
                level_id = TEMPLATE_LEVEL_NODE_ID.format(publisher=publisher.replace(" ", "_"), language=lang, level=level)
                levelsubtopic = TopicNode(source_id=level_id, title=TEMPLATE_LEVEL_TITLE.format(num=level))
                langsubtopic.add_child(levelsubtopic)
                for item in sorted_level_list[level]:
                    r = session.get(item['link'], stream=True)
                    name = TEMPLATE_NAME.format(id=item['source_id'])
                    with open(name, 'wb') as f:
                        f.write(r.content)
                        document_file = DocumentFile(path=name)
                        examplepdf = DocumentNode(
                            title=item['title'], 
                            source_id=str(item['source_id']), 
                            author = item['author'],
                            files=[document_file], 
                            license=get_license(licenses.CC_BY),
                            thumbnail = item['thumbnail'],
                            description = item['description']
                        )
                        levelsubtopic.add_child(examplepdf)
                        

        ########################################################################
        
        # # We are also going to add a video file called 'Example Video'
        # video_file = VideoFile(path="https://ia600209.us.archive.org/27/items/RiceChef/Rice Chef.mp4")
        # fancy_license = get_license(licenses.SPECIAL_PERMISSIONS, description='Special license for ricecooker fans only.', copyright_holder='The chef video makers')
        # examplevideo = VideoNode(title="Example Video", source_id="example-video", files=[video_file], license=fancy_license)
        # # TODO: Create your video file here (use any url to a .mp4 file)

        # # Finally, we are creating an audio file called 'Example Audio'
        # audio_file = AudioFile(path="https://ia802508.us.archive.org/5/items/testmp3testfile/mpthreetest.mp3")
        # exampleaudio = AudioNode(title="Example Audio", source_id="example-audio", files=[audio_file], license=get_license(licenses.CC_BY_SA))
        # # TODO: Create your audio file here (use any url to a .mp3 file)

        # Now that we have our files, let's add them to our channel
        # exampletopic.add_child(book) # Adding 'Example PDF' to your channel
        # exampletopic.add_child(examplevideo) # Adding 'Example Video' to 'Example Topic'
        # examplesubtopic.add_child(exampleaudio) # Adding 'Example Audio' to 'Example Subtopic'

        # the `construct_channel` method returns a ChannelNode that will be
        # processed by the ricecooker framework
        return channel


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = PrathamBooksStoryWeaverSushiChef()
    chef.main()
    # book_list = books_for_each_publisher("World Konkani Centre")
    # group_books = group_books_by_language(book_list)
    # print (group_books)
    # print (group_books.keys())
    # print (book_list)
    # print(groupby(book_list))
