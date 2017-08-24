#!/usr/bin/env python

"""
Sushi Chef for Open Osmosis:
Videos from https://www.youtube.com/channel/UCNI0qOojpkhsUtaQ4_2NUhQ/playlists
Assessment items from https://open.osmosis.org/topics
"""

from collections import defaultdict
import html
import os
import pycountry
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
        'CHANNEL_THUMBNAIL': "https://d3cdo0emj8d2qc.cloudfront.net/assets/f78c3f1d2be258bd84c85cb1f342e9f7343c798b.png",
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

        youtube_channel_url = 'https://www.youtube.com/channel/UCNI0qOojpkhsUtaQ4_2NUhQ/playlists'

        print("Fetching YouTube channel and videos metadata --"
                " this may take a few minutes (%s)" % youtube_channel_url)
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


# TODO(davidhu): Remove this when
# https://github.com/learningequality/le-utils/pull/28 lands
_LANGUAGE_NAME_LOOKUP = {l.name: l for l in languages.LANGUAGELIST}


# TODO(davidhu): Remove this when
# https://github.com/learningequality/le-utils/pull/28 lands
def getlang_patched(language):
    """A patched version of languages.getlang that tries to fallback to
    a closest match if not found."""
    if languages.getlang(language):
        return language

    # Try matching on the prefix: e.g. zh-Hans --> zh
    first_part = language.split('-')[0]
    if languages.getlang(first_part):
        return first_part

    # See if pycountry can find this language and if so, match by language name
    # to resolve other inconsistencies.  e.g. YouTube might use "zu" while
    # le_utils uses "zul".
    pyc_lang = pycountry.languages.get(alpha_2=first_part)
    if pyc_lang:
        return _LANGUAGE_NAME_LOOKUP.get(pyc_lang.name)

    return None


# TODO(davidhu): Remove this when
# https://github.com/learningequality/le-utils/pull/28 lands
class LanguagePatchedYouTubeSubtitleFile(files.YouTubeSubtitleFile):
    """Patches ricecooker's YouTubeSubtitleFile to account for inconsistencies
    between YouTube's language codes and those in `le-utils`:

    https://github.com/learningequality/le-utils/issues/23

    TODO(davidhu): This is a temporary fix and the code here should properly be
    patched in `le-utils.constants.languages.getlang` and a small change to
    `ricecooker.classes.files.YouTubeSubtitleFile`.
    """

    def __init__(self, youtube_id, youtube_language, **kwargs):
        self.youtube_language = youtube_language
        language = getlang_patched(youtube_language)
        super(LanguagePatchedYouTubeSubtitleFile, self).__init__(
                youtube_id=youtube_id, language=language, **kwargs)

    def download_subtitle(self):
        settings = {
            'skip_download': True,
            'writesubtitles': True,
            'subtitleslangs': [self.youtube_language],
            'subtitlesformat': "best[ext={}]".format(file_formats.VTT),
            'quiet': True,
            'no_warnings': True
        }
        download_ext = ".{lang}.{ext}".format(lang=self.youtube_language, ext=file_formats.VTT)
        return files.download_from_web(self.youtube_url, settings,
                file_format=file_formats.VTT, download_ext=download_ext)


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
        license=licenses.CC_BY_SALicense(
            copyright_holder='Open Osmosis (open.osmosis.org)'),
        description=truncate_description(description),
        derive_thumbnail=True,
        language="en",
        files=[files.YouTubeVideoFile(youtube_id=youtube_id)],
    )

    # Add subtitles in whichever languages are available.
    for language in subtitle_languages:
        video_node.add_file(LanguagePatchedYouTubeSubtitleFile(
            youtube_id=youtube_id, youtube_language=language))

    return video_node


DESCRIPTION_RE = re.compile('Subscribe - .*$')

def truncate_description(description):
    first_line = description.splitlines()[0]
    return DESCRIPTION_RE.sub('', first_line)


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
