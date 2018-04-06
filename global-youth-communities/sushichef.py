#!/usr/bin/env python
import os
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import licenses

""" Additional imports """
###########################################################

# from bs4 import BeautifulSoup
import json
from PyPDF2 import PdfFileWriter, PdfFileReader
from utils import downloader
import io

# Run constants
################################################################################
CHANNEL_NAME = "Global Youth Communities"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-global-youth-communities-en"    # Channel's unique id
CHANNEL_DOMAIN = "globalcommunities.org/yslc"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = None
                        # "Started in the West Bank and Gaza, \
                        # this toolkit is designed to support the \
                        # facilitation of Local Youth Councils, groups \
                        # of young leaders from ages 15-20 who can organize \
                        # to facilitate self-governance in their communities. \
                        # Around the world, Youth Local Councils are helping \
                        # youth build a better future and advance the stability \
                        # of their communities by promoting democratic and good \
                        # governance practices, holding their elected local \
                        # officials accountable and ensuring transparent \
                        # government practices."             # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################

BASE_URL = "https://www.globalcommunities.org/yslc"
JSON_FILE = "page_structure.json"
CHANNEL_LICENSE = licenses.PUBLIC_DOMAIN
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])


# Create download directory if it doesn't already exist
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)


# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Global Youth Communities channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }
    # Your chef subclass can ovverdie/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in during upload_channel (currently None)
          - kwargs: extra argumens and options not handled by `uploadchannel`.
            For example, add the command line option   lang="fr"  and the string
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        topics = read_source(JSON_FILE)
        for topic in topics:
            book_title = topic['book_title']
            source_id = book_title.replace(" ", "_")
            url = topic['path_or_url']
            topic_node = nodes.TopicNode(source_id=source_id, title=book_title)
            channel.add_child(topic_node)
            topic_pdf = download_pdf(url)

            for chapter in topic['chapters']:
                pdf = split_pdf(chapter=chapter, pdf=topic_pdf)
                title = chapter['title']
                pdf_path = "{}/{}-{}.pdf".format(DOWNLOAD_DIRECTORY, book_title, title)
                pdf_file = files.DocumentFile(pdf_path)
                write_pdf(pdf_path, pdf)
                pdf_node = nodes.DocumentNode(
                    source_id="{} {}".format(book_title, title),
                    title=title,
                    files=[pdf_file],
                    license=CHANNEL_LICENSE
                )
                topic_node.add_child(pdf_node)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction
        return channel

def download_pdf(url):
    page_contents = downloader.read("{url}".format(url=url))
    pdf_content = io.BytesIO(page_contents)
    reader = PdfFileReader(pdf_content)
    return reader

def read_source(json_file):
    with open(json_file) as json_data:
        return json.load(json_data)

def split_pdf(chapter, pdf):
    writer = PdfFileWriter()
    for page in range(chapter['page_start']-1, chapter['page_end']):
        writer.addPage(pdf.getPage(page))
    return writer

def write_pdf(pdf_path, pdf):
    with open(pdf_path, 'wb') as outfile:
        pdf.write(outfile)

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
