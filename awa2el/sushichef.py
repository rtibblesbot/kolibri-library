#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.classes.licenses import SpecialPermissionsLicense
from ricecooker.chefs import SushiChef
import logging
import video

assert "--compressed" in sys.argv, sys.argv

LOGGER = logging.getLogger()
LICENCE = SpecialPermissionsLicense("Career Girls", "For use on Kolibri")


class ArtsEdgeChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'www.nashmi.net', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'nashmi',         # channel's unique id
        'CHANNEL_TITLE': 'Nashmi',
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        #'CHANNEL_DESCRIPTION': '',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):

        def video_node(video, title):
            files = [VideoFile(video.decode('utf-8'))]
            return VideoNode(source_id=video.decode('utf-8'),
                             title=title,
                             license=LICENCE,
                             copyright_holder="nashmi.net",
                             files=files,
                             )
        def get_node(path):
            if len(path) > 1:
                parent = get_node(path[:-1])
            else:
                parent = channel
            
            if path not in nodes:
                nodes[path] = TopicNode(source_id="topic"+path[-1],
                                        title=path[-1])
                parent.add_child(nodes[path])
            return nodes[path]
            
        nodes = {}
        channel = self.get_channel(**kwargs)
        for path, video_urls in video.videos():
            node = get_node(path)
            for i, video_url in enumerate(video_urls):
                node.add_child(video_node(video_url, "Video "+str(i+1)))
            
        return channel # outdent if not debug
            
            
            
        # create channel
        # create a topic and add it to channel
        
        
        

if __name__ == '__main__':
    """
    Set the environment var `CONTENT_CURATION_TOKEN` (or `KOLIBRI_STUDIO_TOKEN`)
    to your Kolibri Studio token, then call this script using:
        python souschef.py  -v --reset
    """
    mychef = ArtsEdgeChef()
    if 'KOLIBRI_STUDIO_TOKEN' in os.environ:
        os.environ['CONTENT_CURATION_TOKEN'] = os.environ['KOLIBRI_STUDIO_TOKEN']
    mychef.main()
