#!/usr/bin/env python

import requests
import json
from lxml import html
from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode, AudioNode
from ricecooker.classes.files import DocumentFile, VideoFile, AudioFile
from le_utils.constants import licenses
from ricecooker.classes.licenses import get_license
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter

# BASE_URL = "https://storyweaver.org.in"
# SEARCH_URL = "https://storyweaver.org.in/search"
# TEMPLATE_URL = "https://storyweaver.org.in/search?page={page_num}\u0026search%5Bpublishers%5D%5B%5D={publisher_name}"

# session = requests.Session()

# def get_all_publishers():
#     # Get the search page
#     resp = session.get(SEARCH_URL)
#     search_doc = BeautifulSoup(resp.content, 'html.parser')

#     # Get a list of all the publishers
#     publishers_lis = books.find('ul', {'id': 'StoryPublishers'}).find_all('li')
#     publishers = []
#     for li in publishers_lis:
#         publishers.append(li.find('label').text.strip())

#     # Remove the first item "All" from publishers
#     publishers.pop(0)
#     return publishers

# def books_for_each_publisher(publisher):
#     # Change the comma in the name string into %2C
#     publisher = publisher.replace(",", "%2C")
#     # Parse the name of the publisher to put into url
#     list = publisher.split()
#     name = ""
#     for i in range(len(list)-1):
#         name = name + list[i] + "+"
#     name = name + list[-1]

#     # Get the first page of the publisher
#     pub_first_page_url = TEMPLATE_URL.format(page_num="1", publisher_name=name)
#     # Header
#     headers = {
#         'X-CSRF-Token': 'ySOG84hNCKNit9G7arli4bSFzH00BeS9vVnRNnBY+hA=',
#         'Accept': 'application/json, text/javascript, */*; q=0.01',
#         'X-Requested-With': 'XMLHttpRequest'
#     }

#     response = session.get(pub_first_page_url, headers=headers)
#     data = response.json()
#     search_results = data['search_results']
#     link_list = []
#     for i in range(len(search_results)):
#         download_link = BASE_URL + search_results[i]['links'][0]['download']['low_res_pdf']
#         link_list.append(download_link)
#     return link_list

class TestSushiChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """

    # 1. PROVIDE CHANNEL INFO  (replace <placeholders> with your own values)
    ############################################################################
    channel_info = {    #
        'CHANNEL_SOURCE_DOMAIN': 'learningequality.org',       # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'test_test_test',                   # channel's unique id
        'CHANNEL_TITLE': 'test',
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
        exampletopic = TopicNode(source_id="storyweaver_publisher_World_ Konkani_Centre", title="World Konkani Centre")

        # Now we are adding 'Example Topic' to our channel
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

        # list = books_for_each_publisher("World Konkani Centre")
        # for item in list:
        #     document_file = DocumentFile(path=item)
        #     book = DocumentNode(title="book"+item, source_id="pdf"+item, files=[document_file], license=get_license(licenses.CC_BY))
        # # Content
        # You can add pdfs, videos, and audio files to your channel
        ########################################################################
        # let's create a document file called 'Example PDF'
        document_file = DocumentFile(path="http://www.pdf995.com/samples/pdf.pdf")
        examplepdf = DocumentNode(title="Example PDF", source_id="example-pdf", files=[document_file], license=get_license(licenses.CC_BY_SA))
        # # TODO: Create your pdf file here (use any url to a .pdf file)
        # my_document_file = DocumentFile(path="/Users/lingyiwang/Documents/Learning Equality/sushi-chef/Homework1.pdf")
        # mypdf = DocumentNode(title="My PDF", source_id="my-pdf", files=[my_document_file], license=get_license(licenses.CC_BY_SA))

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
            #exampletopic.add_child(book) # Adding 'Example PDF' to your channel
        # exampletopic.add_child(examplevideo) # Adding 'Example Video' to 'Example Topic'
        # examplesubtopic.add_child(exampleaudio) # Adding 'Example Audio' to 'Example Subtopic'

        # TODO: Add your pdf file to your channel
        channel.add_child(examplepdf)
        # TODO: Add your video file to your topic
        # TODO: Add your audio file to your subtopic

        # the `construct_channel` method returns a ChannelNode that will be
        # processed by the ricecooker framework
        return channel


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = TestSushiChef()
    chef.main()
    
    # publishers = get_all_publishers()
    # list = get_publisher_url(publishers)
    # print(get_publisher_page(list[0]))

    # print(books_for_each_publisher("World Konkani Centre")['search_results'][0]['links'][0]['download']['epub'])
