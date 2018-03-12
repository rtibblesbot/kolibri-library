#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
from le_utils.constants import licenses
from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.chefs import SushiChef
import logging
import json 
from collections import OrderedDict
from index_lessons import crawl_lesson_index
from single_lesson import get_lesson
from urllib.parse import urljoin

raw_lessons = crawl_lesson_index()
lessons = OrderedDict([('Elementary', [x for x in raw_lessons if x.grade == "K-4"]),
                       ('Middle',     [x for x in raw_lessons if x.grade == "5-8"]),
                       ('High',       [x for x in raw_lessons if x.grade == "9-12"])])

LOGGER = logging.getLogger()


class PBSChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'artsedge.kennedy-center.org/', # who is providing the content (e.g. learningequality.org)
        'CHnANNEL_SOURCE_ID': 'artsedge',         # channel's unique id
        'CHANNEL_TITLE': 'ArtsEdge',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'Connect. Create.',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        
        def video_node(video, subtitle, data):
            if subtitle:
                files = [video, subtitle]
            else:
                files = [video]
            return VideoNode(source_id=data['link'],
                             title=data['link'],
                             license=licenses.CC_BY_NC_SA, 
                             copyright_holder="JFK Center for the Performing Arts",
                             files=files,
                             )            
            
        # create channel
        _id = 0
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        data = {}
        
        for item in lessons:
            topic = TopicNode("__"+item, item, "Resources for {} school students".format(item.lower()))
            channel.add_child(topic)
            for lesson in lessons[item]:
                lesson_node = TopicNode("__{}".format(_id), lesson.title, "")
                _id = _id + 1
                topic.add_child(lesson_node)
                print (lesson)
                for item in get_lesson(urljoin("https://artsedge.kennedy-center.org/", lesson.link)):
                    lesson_node.add_child(item)
        return channel
    
def download_videos(jsonfile):
    with open(jsonfile) as f:
        database = [json.loads(line) for line in f.readlines()]
        
    i = 0
    for item in database:
        if item['category'] in ["Video"]: # ("Document", "Audio", "Image", "Video"):
            yield detail.get_individual_page(item)
            i=i+1
            if i == 4:
                print ("Artificial quit")
                break
        
def make_channel():
    mychef = PBSChef()
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': False, 'verbose': True}
    options = {}
    mychef.run(args, options)

make_channel()
