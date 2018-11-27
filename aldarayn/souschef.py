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
from collections import namedtuple

Row = namedtuple("Row", csvstructure.PYTHON_FIELDNAMES)

def dragon_construct_channel(self, **kwargs):
    channel = self.get_channel(**kwargs)
    cats = {}

    for raw_row in self.channel_index:
        row = Row(*raw_row)
        topic_tree = [row.L1, row.L2, row.L3, row.L4]
        topic_tree = tuple(x for x in topic_tree if x)  # remove Nones
        for i in range(1,5):
            partial_tree = topic_tree[:i]
            leaf = partial_tree[-1]
            if partial_tree not in cats:
                cats[partial_tree] = TopicNode(source_id=repr(partial_tree),
                                               title=leaf,
                                               description="")
        print (":)")
        exit()

    category_index = TopicNode(source_id="category",
                               title = "Categorical Index",
                               description="")
    channel.add_child(category_index)
    return channel

class AdultChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'aldarayn.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'aldarayn_adult',         # channel's unique id
        'CHANNEL_TITLE': arabic.TITLE_ADULT,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.CHANNEL_DESC,  # (optional) description of the channel (optional)
    }

    channel_index = csvstructure.adult_structure()
    construct_channel = dragon_construct_channel


class K12Chef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'aldarayn.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'aldarayn_k12',         # channel's unique id
        'CHANNEL_TITLE': arabic.TITLE_K12,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.CHANNEL_DESC,  # (optional) description of the channel (optional)
    }

    channel_index = csvstructure.k12_structure()
    construct_channel = dragon_construct_channel

def make_channel():
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    adult_chef = AdultChef()
    adult_chef.run(args, options)
    #k12_chef = K12Chef()
    #k12_chef.run(args, options)

make_channel()
