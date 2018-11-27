#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
import json
from le_utils.constants import licenses
from ricecooker.classes.nodes import TopicNode #DocumentNode, VideoNode, AudioNode
# from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.chefs import SushiChef
import detail
import arabic
import csvstructure

class BothChef(SushiChef):
    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        for row in channel_index:
            print (row)
            exit()


        category_index = TopicNode(source_id="category",
                                   title = "Categorical Index",
                                   description="")
        channel.add_child(category_index)
        return channel

class AdultChef(BothChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'aldarayn.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'aldarayn_adult',         # channel's unique id
        'CHANNEL_TITLE': arabic.TITLE_ADULT,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.CHANNEL_DESC,  # (optional) description of the channel (optional)
    }

    channel_index = csvstructure.adult_structure()


class K12Chef(BothChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'aldarayn.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'aldarayn_k12',         # channel's unique id
        'CHANNEL_TITLE': arabic.TITLE_K12,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.CHANNEL_DESC,  # (optional) description of the channel (optional)
    }

    channel_index = csvstructure.k12_structure()

def make_channel():
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    adult_chef = AdultChef()
    adult_chef.run(args, options)
    #k12_chef = K12Chef()
    #k12_chef.run(args, options)

make_channel()
