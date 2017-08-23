#!/usr/bin/env python

"""
Sushi Chef for Open Osmosis:
Videos from https://www.youtube.com/channel/UCNI0qOojpkhsUtaQ4_2NUhQ/playlists
Assessment items from https://open.osmosis.org/topics
"""

from collections import defaultdict
import html
import os
import re
import requests
import tempfile
import time
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import youtube_dl

from le_utils.constants import content_kinds, file_formats, languages
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver, minimize_html_css_js
from ricecooker.utils.zip import create_predictable_zip


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

#sess.mount('http://', forever_adapter)
#sess.mount('https://', forever_adapter)

ydl = youtube_dl.YoutubeDL({
    'quiet': True,
    'no_warnings': True,
    'writesubtitles': True,
    'allsubtitles': True,
})


class OpenOsmosisChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "open.osmosis.org",
        'CHANNEL_SOURCE_ID': "open-osmosis",
        'CHANNEL_TITLE': "Open Osmosis",
        'CHANNEL_THUMBNAIL': "https://open.osmosis.org/assets/images/logo/osmosis-logo-flat.png",
        'CHANNEL_DESCRIPTION': "A study tool built for tomorrow's doctors and health workers.",
    }

    def construct_channel(self, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        # create channel
        channel_info = self.channel_info
        channel = nodes.ChannelNode(
            source_domain = channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = channel_info['CHANNEL_SOURCE_ID'],
            title = channel_info['CHANNEL_TITLE'],
            thumbnail = channel_info.get('CHANNEL_THUMBNAIL'),
            description = channel_info.get('CHANNEL_DESCRIPTION'),
            language = "en",
        )

        youtube_channel_url = 'https://www.youtube.com/user/eaterbc/playlists'
        #youtube_channel_url = 'https://www.youtube.com/channel/UCNI0qOojpkhsUtaQ4_2NUhQ/playlists'

        print("Fetching YouTube channel and videos metadata --"
                " this may take 10-20+ minutes (%s)" % youtube_channel_url)
        info = ydl.extract_info(youtube_channel_url, download=False)

        for playlist in info['entries']:
            title = playlist['title']
            youtube_url = playlist['webpage_url']
            print("  Downloading playlist %s (%s)" % (title, youtube_url))
            playlist_topic = nodes.TopicNode(
                    source_id=playlist['id'], title=playlist['title'])
            channel.add_child(playlist_topic)
            for video in playlist['entries']:
                playlist_topic.add_child(fetch_video(video))

        return channel


def fetch_video(video):
    youtube_id = video['id']
    title = video['title']
    description = video['description']
    youtube_url = video['webpage_url']
    subtitle_languages = video['subtitles'].keys()

    print("    Fetching video data: %s (%s)" % (title, youtube_url))

    video_node = nodes.VideoNode(
        source_id=youtube_id,
        title=truncate_metadata(title),
        license=licenses.CC_BY_SALicense(copyright_holder='Osmosis'),
        description=description,
        derive_thumbnail=True,
        language="en",
        files=[files.YouTubeVideoFile(youtube_id=youtube_id)],
    )

    # Add subtitles in whichever languages are available.
    for language in subtitle_languages:
        video_node.add_file(files.YouTubeSubtitleFile(
            youtube_id=youtube_id, language=language))

    return video_node


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = OpenOsmosisChef()
    chef.main()
