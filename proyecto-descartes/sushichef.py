#!/usr/bin/env python
import os
import re
import sys
import requests
import tempfile
import zipfile
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages
from bs4 import BeautifulSoup
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from collections import OrderedDict
from math import ceil
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.classes.licenses import CC_BY_NC_SALicense

sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)



# Run constants
################################################################################
CHANNEL_NAME = "Proyecto Descartes"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-proyecto-descartes-es"    # Channel's unique id
CHANNEL_DOMAIN = "proyectodescartes.org"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = "Asociación non-gubernamental que promueve la renovación y cambio metodológico en los procesos de aprendizaje y enseñanza de las Matemáticas y en otras áreas de conocimiento. Los recursos digitales interactivos generados en el Proyecto Descartes son hechos completamente por profesores, y son appropriados por todos los niveles de escuela primaria, secundaria, y bachillerato."                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################
SUBJECT_BLACKLIST = ["", "blog", "plantillas"]
BASE_URL = "http://proyectodescartes.org/descartescms/{}"
MAIN_PAGE_HREF= "/descartescms/"
AGE_RANGE = {
    "10-13 años": ["10 a 11 años", "10 a 12 años", "11 a 12 años", "12 a 13 años"],
    "13-14 años": ["13 a 14 años"],
    "14-15 años": ["14 a 15 años"],
    "15-16 años": ["15 a 16 años"],
    "16-17 años": ["16 a 17 años"],
    "17-18 años": ["17 a 18 años"],
    "18+ años": ["18 años o más"],
}


# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Proyecto Descartes channel to Kolibri Studio.
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
    # Your chef subclass can override/extend the following method:
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

        resp = sess.get("http://proyectodescartes.org/descartescms/")
        soup = BeautifulSoup(resp.content, "html.parser")
        topics = soup.find_all("a", "item")

        final_topics = self.parse_topics(topics, channel)

        for topic in final_topics:
            # No need to parse the content under the topic when link is not valid
            if "javascript:void(0);" in topic[1]:
                continue
            self.download_subject(topic[0], topic[1])

        # raise NotImplementedError("constuct_channel method not implemented yet...")
        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel

    def parse_topics(self, topics, channel):
        final_topics = []
        main_topics = []
        
        for topic in topics:
            href = topic["href"].split(MAIN_PAGE_HREF)
            subject = href[-1].split("/")[0]

            if subject in SUBJECT_BLACKLIST:
                continue
            
            # Get subject information for the topic
            subjectLink = BASE_URL.format(href[-1])
            subjectTitle = topic.text.strip()
            subject_topic = TopicNode(source_id=subjectTitle, title=subjectTitle)

            # When the topic is a subtopic of another
            if topic.parent.parent.attrs["class"][0] == "l2":
                parent = main_topics[-1]
            else:
                parent = channel
                main_topics.append(subject_topic)

            topic_tuple = (subject_topic, subjectLink)
            parent.add_child(subject_topic)
            final_topics.append(topic_tuple)

        return final_topics

    def download_subject(self, parent, link):
        print ("Processing subject: ", parent.title)
        resp = sess.get(link)
        soup = BeautifulSoup(resp.content, "html.parser")

        selected_category = soup.find("option", {"class": "level0", "selected": "selected"})["value"]

        for item in AGE_RANGE.keys():
            params = {
                "category": selected_category,
                "moduleId": "282",
                "format": "count",
            }
            for index in range(len(AGE_RANGE[item])):
                params["taga[{}]".format(index)] = AGE_RANGE[item][index]
            resp = sess.get("{}/itemlist/filter".format(link), params=params)
            count = int(resp.text.split('\n')[0])
            if count == 0:
                return

            print ("Processing topic: ", item)
            age_topic = TopicNode(source_id=item, title=item)
            parent.add_child(age_topic)
            total_pages = ceil(count/20)

            for i in range(total_pages):
                page_params = dict(params)
                self.download_content(age_topic, link, page_params, selected_category, i*20)


    def download_content(self, parent, link, params, selected_category, start):
        params["start"] = start
        params.pop("format")

        resp = sess.get("{}/itemlist/filter".format(link), params=params)
        print (resp.url)
        soup = BeautifulSoup(resp.content, "html.parser")
        for item in soup.find("tbody").find_all("a"):
            content_url = "http://proyectodescartes.org{}".format(item["href"])
            title = item.text.strip()
            source_id = item["href"].split("/")[-1]
            print (content_url)
            response = sess.get(content_url)
            page = BeautifulSoup(response.content, "html.parser")
            author_tag = page.find(string="Autoría")
            if author_tag:
                author = str(soup.find(string="Autoría").parent.parent).split("Autoría</strong>:")[-1].split("<")[0].strip()
            else:
                author = str(soup.find(string="Autores").parent.parent).split("Autores</strong>:")[-1].split("<")[0].strip()
            zip_href = page.find("a", href=re.compile(".zip"))
            if not zip_href:
                print ("The url for the Zip file does not exist in this page: ", content_url)
                continue
            zip_url = "http://proyectodescartes.org{}".format(zip_href["href"])
            filepath = "/tmp/{}".format(zip_url.split("/")[-1])
            zip_resp = sess.get(zip_url)

            if zip_resp.status_code != 200:
                print ("The url for the Zip file does not work: ", zip_url)
                continue

            if not os.path.exists(filepath):
                with open(filepath, "wb") as f:
                    f.write(zip_resp.content)

            zip_path = create_predictable_zip(filepath)

            content_node = HTML5AppNode(
                source_id=source_id,
                title=title,
                license=CC_BY_NC_SALicense(),
                language=CHANNEL_LANGUAGE,
                files=[files.HTMLZipFile(zip_path)],
                author=author,
            )

            parent.add_child(content_node)


def _read_file(path):
    with open(path, "rb") as f:
        return f.read()

def create_predictable_zip(path):
    """ create_predictable_zip: Create a zip file with predictable sort order and metadata, for MD5 consistency.
        Args:
            path (str): absolute path either to a directory to zip up, or an existing zip file to convert.
        Returns: path (str) to the output zip file
    """

    # if path is a directory, recursively enumerate all the files under the directory
    if os.path.isdir(path): 
        paths = []
        for root, directories, filenames in os.walk(path):
            paths += [os.path.join(root, filename)[len(path)+1:] for filename in filenames]
        reader = lambda x: _read_file(os.path.join(path, x))
    # otherwise, if it's a zip file, open it up and pull out the list of names
    elif os.path.isfile(path) and os.path.splitext(path)[1] == ".zip":
        inputzip = zipfile.ZipFile(path)
        paths = inputzip.namelist()
        reader = lambda x: inputzip.read(x)
    else:
        raise Exception("The `path` must either point to a directory or to a zip file.")

    # create a temporary zip file path to write the output into
    handle, zippath = tempfile.mkstemp(suffix=".zip")

    with zipfile.ZipFile(zippath, "w") as outputzip:
        # loop over the file paths in sorted order, to ensure a predictable zip
        for filepath in sorted(paths):
            write_file_to_zip_with_neutral_metadata(outputzip, filepath, reader(filepath))
    os.close(handle)
    return zippath


def write_file_to_zip_with_neutral_metadata(zfile, filename, content):
    """ write_file_to_zip_with_neutral_metadata: Write a string into an open ZipFile with predictable metadata.
        Args:
            zfile (ZipFile): open ZipFile to write the content into
            filename (str): the file path within the zip file to write into
            content (str): the content to write into the zip
        Returns: None
    """

    info = zipfile.ZipInfo(filename, date_time=(2015, 10, 21, 7, 28, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.comment = "".encode()
    info.create_system = 0
    zfile.writestr(info, content)



# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
