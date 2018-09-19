#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from collections import defaultdict, OrderedDict
import copy
import glob
from le_utils.constants import licenses, content_kinds, file_formats
import hashlib
import json
import logging
import ntpath
import os
from pathlib import Path
import re
import requests
from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.jsontrees import write_tree_to_json_tree, SUBTITLES_FILE
import time
from urllib.error import URLError
from urllib.parse import urljoin
from utils import if_dir_exists, get_name_from_url, clone_repo, build_path
from utils import if_file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
import youtube_dl


BASE_URL = "https://academy.hsoub.com/"

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "Hsoub Academy"
LICENSE = get_license(licenses.CC_BY_NC_SA, 
        copyright_holder=COPYRIGHT_HOLDER).as_dict()
AUTHOR = "Hsoub Academy"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True

sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)

# Run constants
################################################################################
CHANNEL_NAME = "Hsoub Academy"                              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-hsoub-academy"              # Channel's unique id
CHANNEL_DOMAIN = BASE_URL                                   # Who is providing the content
CHANNEL_LANGUAGE = "ar"                                     # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################

data_nav = OrderedDict([
("Lessons and Articles", "دروس ومقالات"), 
("Questions and Answers", "أسئلة وأجوبة"), 
("Books and Resources",  "كتب وملفات")
])


def browser_resources():
    page = download(BASE_URL)
    ul01 = page.find(lambda tag: tag.name == "ul" and tag.attrs.get("data-role", "") == "primaryNavBar")
    for name, name_ar in data_nav.items():
        LOGGER.info("- Category: {} {}".format(name, name_ar))
        li = ul01.find(lambda tag: tag.name == "a" and tag.text.strip() == name_ar)
        ul02 = li.findNext()
        category = Category(name_ar, name_ar)
        for a in ul02.find_all("a"):
            source_id = a.get("href", "")
            title = a.text.strip()
            category.add_topic(title, source_id)
            category.download()
            break
        yield category
        break


class Node(object):
    def __init__(self, title, source_id, lang="ar"):
        self.title = title
        self.source_id = source_id
        self.tree_nodes = OrderedDict()
        self.lang = lang
        self.description = None
        self.thumbnail = None
        self.author = None

    def add_node(self, obj):
        node = obj.to_node()
        if node is not None:
            self.tree_nodes[node["source_id"]] = node

    def to_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.source_id,
            title=self.title,
            description=self.description,
            language=self.lang,
            thumbnail=self.thumbnail,
            author=AUTHOR if self.author is None else self.author,
            license=LICENSE,
            children=list(self.tree_nodes.values())
        )
    

class Category(Node):
    def __init__(self, *args, **kwargs):
        super(Category, self).__init__(*args, **kwargs)
        self.topics = []

    def add_topic(self, title, url):
        if url != "#":
            topic = Topic(title, url)
            self.topics.append(topic)

    def download(self):
        for topic in self.topics:
            topic.download()
            self.add_node(topic)


class Topic(Node):
    def __init__(self, *args, **kwargs):
        super(Topic, self).__init__(*args, **kwargs)
        LOGGER.info("--- Topic: {} {}".format(self.title, self.source_id))

    def download(self):
        page = download(self.source_id)
        div = page.find("div", id="elCmsPageWrap")
        articles = div.find_all("article")
        for article_soup in articles:
            img = article_soup.find("img")
            title_a = article_soup.find(lambda tag: tag.name == "a" and tag.findParent("h2"))
            title = title_a.text.strip()
            source_id = title_a.get("href", "")
            article = Article(title, source_id)
            article.description = article_soup.find("section").text
            article.thumbnail = img.get("src", None)
            article.download()
            self.add_node(article)
            break


class Article(Node):
    def __init__(self, *args, **kwargs):
        super(Article, self).__init__(*args, **kwargs)
        LOGGER.info("------ Article: {}".format(self.title))

    def download(self, download=True, base_path=None):
        html_app = HTMLApp(self.title, self.source_id)
        html_app.download()
        self.add_node(html_app)
        #for url in self.urls:
        #    youtube = YouTubeResource(url, lang=self.lang)
        #    youtube.download(download, base_path)
        #    self.add_node(youtube)


class HTMLApp(object):
    def __init__(self, title, source_id, lang="ar"):
        self.title = title
        self.source_id = source_id
        self.lang = lang
        self.description = None
        self.thumbnail = None
        self.author = None
        self.filepath = None
        self.page = self.soup()

    def soup(self):
        soup = download(self.source_id)
        return soup.find("article")

    def download(self):
        print("DOWNLOAD")

    def to_node(self):
        return dict(
            kind=content_kinds.HTML5,
            source_id=self.source_id,
            title=self.title,
            description=self.description,
            thumbnail=self.thumbnail,
            author=AUTHOR if self.author is None else self.author,
            files=[dict(
                file_type=content_kinds.HTML5,
                path=self.filepath
            )],
            language=self.lang,
            license=LICENSE
        )


class YouTubeResource(object):
    def __init__(self, source_id, name=None, type_name="Youtube", lang="ar", 
            embeded=False, section_title=None):
        LOGGER.info("    + Resource Type: {}".format(type_name))
        LOGGER.info("    - URL: {}".format(source_id))
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        self.name = name
        self.section_title = section_title
        if embeded is True:
            self.source_id = YouTubeResource.transform_embed(source_id)
        else:
            self.source_id = self.clean_url(source_id)
        self.file_format = file_formats.MP4
        self.lang = lang
        self.is_valid = False

    def clean_url(self, url):
        if url[-1] == "/":
            url = url[:-1]
        return url.strip()

    @classmethod
    def is_youtube(self, url, get_channel=False):
        youtube = url.find("youtube") != -1 or url.find("youtu.be") != -1
        if get_channel is False:
            youtube = youtube and url.find("user") == -1 and url.find("/c/") == -1
        return youtube

    @classmethod
    def transform_embed(self, url):
        url = "".join(url.split("?")[:1])
        return url.replace("embed/", "watch?v=").strip()

    def playlist_links(self):
        ydl_options = {
                'no_warnings': True,
                'restrictfilenames':True,
                'continuedl': True,
                'quiet': False,
                'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='480'),
                'noplaylist': False
            }

        playlist_videos_url = []
        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.source_id, download=False)
                for entry in info["entries"]:
                    playlist_videos_url.append(entry["webpage_url"])
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('An error occured ' + str(e))
                LOGGER.info(self.source_id)
            except KeyError as e:
                LOGGER.info(str(e))
        return playlist_videos_url

    def playlist_name_links(self):
        name_url = []
        for url in self.playlist_links():
            youtube = YouTubeResource(url)
            info = youtube.get_video_info(None, False)
            name_url.append((info["title"], url))
        return name_url

    def get_video_info(self, download_to=None, subtitles=True):
        ydl_options = {
                'writesubtitles': subtitles,
                'allsubtitles': subtitles,
                'no_warnings': True,
                'restrictfilenames':True,
                'continuedl': True,
                'quiet': False,
                'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='480'),
                'outtmpl': '{}/%(id)s'.format(download_to),
                'noplaylist': True
            }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.source_id, download=(download_to is not None))
                return info
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('An error occured ' + str(e))
                LOGGER.info(self.source_id)
            except KeyError as e:
                LOGGER.info(str(e))

    def subtitles_dict(self):
        subs = []
        video_info = self.get_video_info()
        if video_info is not None:
            video_id = video_info["id"]
            if 'subtitles' in video_info:
                subtitles_info = video_info["subtitles"]
                for language in subtitles_info.keys():
                    subs.append(dict(file_type=SUBTITLES_FILE, youtube_id=video_id, language=language))
        return subs

    #youtubedl has some troubles downloading videos in youtube,
    #sometimes raises connection error
    #for that I choose pafy for downloading
    def download(self, download=True, base_path=None):
        if not "watch?" in self.source_id or "/user/" in self.source_id or\
            download is False:
            return

        download_to = build_path([base_path, 'videos'])
        for i in range(4):
            try:
                info = self.get_video_info(download_to=download_to, subtitles=False)
                if info is not None:
                    LOGGER.info("    + Video resolution: {}x{}".format(info.get("width", ""), info.get("height", "")))
                    self.filepath = os.path.join(download_to, "{}.mp4".format(info["id"]))
                    self.filename = info["title"]
                    if self.filepath is not None and os.stat(self.filepath).st_size == 0:
                        LOGGER.info("    + Empty file")
                        self.filepath = None
            except (ValueError, IOError, OSError, URLError, ConnectionResetError) as e:
                LOGGER.info(e)
                LOGGER.info("Download retry")
                time.sleep(.8)
            except (youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError, OSError) as e:
                LOGGER.info("     + An error ocurred, may be the video is not available.")
                return
            except OSError:
                return
            else:
                return

    def to_node(self):
        if self.filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
            files += self.subtitles_dict()
            node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.source_id,
                title=self.name if self.name is not None else self.filename,
                description='',
                author=AUTHOR,
                files=files,
                language=self.lang,
                license=LICENSE
            )
            return node


def download(source_id):
    tries = 0
    while tries < 4:
        try:
            document = downloader.read(source_id, loadjs=False, session=sess)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))
        else:
            return BeautifulSoup(document, 'html5lib') #html5lib
        tries += 1
    return False



# The chef subclass
################################################################################
class HsoubAcademyChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    THUMBNAIL = ""

    def __init__(self):
        build_path([HsoubAcademyChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(HsoubAcademyChef.TREES_DATA_DIR, 
                                HsoubAcademyChef.SCRAPING_STAGE_OUTPUT_TPL)
        super(HsoubAcademyChef, self).__init__()

    def pre_run(self, args, options):
        channel_tree = self.scrape(args, options)
        #clean_leafs_nodes_plus(channel_tree)
        self.write_tree_to_json(channel_tree)

    def scrape(self, args, options):
        download_video = options.get('--download-video', "1")

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        global channel_tree
        channel_tree = dict(
                source_domain=HsoubAcademyChef.HOSTNAME,
                source_id=BASE_URL,
                title=CHANNEL_NAME,
                description="""Hsoub Academy provides online courses in the area of computer science and digital literacy for adult learners and IT emerging professionals. Those courses include video lessons and articles on what is trending in the coding and entrepreneurship world today.."""
[:400], #400 UPPER LIMIT characters allowed 
                thumbnail="",
                author=AUTHOR,
                language=CHANNEL_LANGUAGE,
                children=[],
                license=LICENSE,
            )

        base_path = [DATA_DIR] + ["Hsoub Academy"]
        base_path = build_path(base_path)
        for category in browser_resources():
            channel_tree["children"].append(category.to_node())
        
        return channel_tree

    def write_tree_to_json(self, channel_tree):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)


# CLI
################################################################################
if __name__ == '__main__':
    chef = HsoubAcademyChef()
    chef.main()
