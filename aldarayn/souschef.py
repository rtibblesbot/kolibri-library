#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
import json
from le_utils.constants import licenses
from ricecooker.classes.nodes import TopicNode, #DocumentNode, VideoNode, AudioNode
# from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.chefs import SushiChef
import detail

class MyChef(SushiChef):
    # hierarchy = # open reverse.json and parse

    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'pbslearningmedia.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'dragon__pbslearningmedia',         # channel's unique id
        'CHANNEL_TITLE': 'PBS Learning Media',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'Bring Your Classroom to Life With PBS',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        category_index = TopicNode(source_id="category",
                                   title = "Categorical Index",
                                   description="")
        channel.add_child(category_index)
        return channel

def make_channel():
    mychef = MyChef()
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    mychef.run(args, options)

make_channel()
