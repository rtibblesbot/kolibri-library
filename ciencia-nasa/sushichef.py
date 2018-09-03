#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from collections import defaultdict, OrderedDict
import copy
from git import Repo
import glob
from le_utils.constants import licenses, content_kinds, file_formats
import hashlib
import json
import logging
import markdown2
import ntpath
import os
from pathlib import Path
import re
import requests
from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.jsontrees import write_tree_to_json_tree, SUBTITLES_FILE
from ricecooker.utils.zip import create_predictable_zip
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.parse import urlparse, parse_qs 
from utils import if_dir_exists, get_name_from_url, clone_repo, build_path
from utils import if_file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
from utils import link_to_text, remove_scripts
import youtube_dl


BASE_URL = "https://ciencia.nasa.gov/"

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "NASA"
LICENSE = get_license(licenses.CC_BY, 
        copyright_holder=COPYRIGHT_HOLDER).as_dict()
AUTHOR = "NASA"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True
DOWNLOAD_FILES = True

sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)

# Run constants
################################################################################
CHANNEL_NAME = "Ciencia NASA"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-ciencia-nasa-es"    # Channel's unique id
CHANNEL_DOMAIN = "https://ciencia.nasa.gov/"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################

TOPICS = {"Ciencia Especial": "ciencias-espaciales", 
        "Ciencia Terrestre": "ciencias-de-la-tierra", 
        "Ciencia Fisica": "ciencias-f%C3%ADsicas", 
        "Miscelanea": "m%C3%A1s-all%C3%A1-de-la-coheter%C3%ADa"}


class Browser:
    def __init__(self, url):
        self.url = url

    def run(self, from_i=1, to_i=None):
        for title, topic_page_name in sorted(TOPICS.items(), key=lambda x: x[0]):
            url = urljoin(self.url, topic_page_name)
            topic = Topic(title, url)
            topic.articles()
            yield topic.to_node()
            break


class Topic(object):
    def __init__(self, title, url):
        self.source_id = url
        self.title = title
        #self.urls = Browser(self.source_id).run()
        self.lang = CHANNEL_LANGUAGE
        self.tree_nodes = OrderedDict()
        #self.thumbnails_links = {}
        self.soup = self.to_soup()
        self.description = self.get_description()
        LOGGER.info("- " + self.title)

    def get_description(self):
        base = self.soup.find("article")
        if base is not None:
            p = base.find(lambda tag: tag.name == "p" and tag.findParent("div", class_="field__item even"))
            return p.text
            
    def to_soup(self):
        document = download(self.source_id)
        if document is not None:
            return BeautifulSoup(document, 'html5lib') #html5lib

    def articles(self):
        page = 0
        articles = [1,2]
        while len(articles) > 1:
            articles = TopicPage(self, page=0).articles()
            page += 1
            break

    def to_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.title,
            title=self.title,
            description=self.description,
            language=self.lang,
            author="",
            license=LICENSE,
            children=list(self.tree_nodes.values())
        )

class TopicPage(object):
    def __init__(self, topic, page=0):
        self.source_id = topic.source_id+"?page=".format(page)
        self.soup = self.to_soup()
        self.topic = topic
        
    def to_soup(self):
        document = download(self.source_id)
        if document is not None:
            return BeautifulSoup(document, 'html5lib') #html5lib

    def articles(self):
        for article in self.soup.find_all("div", class_="views-row"):
            title = article.find("div", class_="views-field-title")
            print(title.text)
            print(article.find("img").get("src"))
            print(urljoin(BASE_URL, title.find("a").get("href")))
            break


def thumbnails_links(soup, tag, class_):
    if soup is not None:
        courses_list = soup.find_all(tag, class_=class_)
        thumnails = {}
        for course_li in courses_list:
            link = course_li.find("a").get("href")
            img = course_li.find("img")
            if img is not None:
                thumnails[link] = img["src"]
        return thumnails


def save_thumbnail(url, title):
    import imghdr
    from io import BytesIO
    try:
        r = requests.get(url)
    except:
        return None
    else:
        img_buffer = BytesIO(r.content)
        img_ext = imghdr.what(img_buffer)
        if img_ext != "gif":
            filename = "{}.{}".format(title, img_ext)
            base_dir = build_path([DATA_DIR, "thumbnails"])
            filepath = os.path.join(base_dir, filename)
            with open(filepath, "wb") as f:
                f.write(img_buffer.read())
            return filepath



class Article(object):
    def __init__(self, title, url):
        self.title = title.replace("/", "_")
        self.source_id = url
        self.soup = self.to_soup()
        self.lang = CHANNEL_LANGUAGE
        self.filepath = None
        self.video_nodes = None
        self.pdf_nodes = None
        self.author = self.get_author()
        LOGGER.info("--------- " + self.title)        

    def get_author(self):
        tag_a = self.soup.find(lambda tag: tag.name == "a" and tag.findParent("li", "mt-author-information"))
        if tag_a is not None:
            return tag_a.text

    def to_local_images(self, content):
        images_urls = {}
        for img in content.findAll("img"):
            try:
                img_src = img["src"]
            except KeyError:
                continue
            else:
                if img_src.startswith("/"):
                    img_src = urljoin(BASE_URL, img_src)
                filename = get_name_from_url(img_src)
                if img_src not in images_urls and img_src:
                    img["src"] = filename
                    images_urls[img_src] = filename
        return images_urls

    def build_video_nodes(self, base_path, content):
        videos_url = self.get_videos_urls(content)
        base_path = build_path([DATA_DIR, "videos"])
        video_nodes = []
        for video_url in videos_url:
            if YouTubeResource.is_youtube(video_url):
                video = YouTubeResource(video_url, lang=self.lang)
                video.download(download=DOWNLOAD_VIDEOS, base_path=base_path)
                node = video.to_node()
                if node is not None:
                    video_nodes.append(node)
        return video_nodes

    def get_videos_urls(self, content):
        urls = set([])
        video_urls = content.find_all(lambda tag: tag.name == "a" and tag.attrs.get("href", "").find("youtube") != -1 or tag.attrs.get("href", "").find("youtu.be") != -1 or tag.text.lower() == "youtube")

        for video_url in video_urls:
            urls.add(video_url.get("href", ""))

        for iframe in content.find_all("iframe"):
            url = iframe["src"]
            if YouTubeResource.is_youtube(url):
                urls.add(YouTubeResource.transform_embed(url))

        return urls

    def get_pdfs_urls(self, content):
        urls = set([])
        pdf_urls = content.findAll(lambda tag: tag.name == "a" and tag.attrs.get("href", "").endswith(".pdf"))
        for pdf_url in pdf_urls:
            urls.add(pdf_url.get("href", ""))
        return urls

    def write_images(self, filepath, images):
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            for img_src, img_filename in images.items():
                try:
                    if img_src.startswith("data:image/"):
                        pass
                    else:
                        zipper.write_url(img_src, img_filename, directory="")
                except requests.exceptions.HTTPError:
                    pass
        
    def build_pdfs_nodes(self, base_path, content):
        pdfs_urls = self.get_pdfs_urls(content)
        base_path = build_path([base_path, 'pdfs'])
        pdf_nodes = []
        for pdf_url in pdfs_urls:
            pdf_file = File(pdf_url, lang=self.lang, name=self.title)
            pdf_file.download(download=DOWNLOAD_FILES, base_path=base_path)
            node = pdf_file.to_node()
            if node is not None:
                pdf_nodes.append(node)
        return pdf_nodes

    def to_file(self, base_path):
        self.filepath = "{path}/{name}.zip".format(path=base_path, name=self.title)
        self.video_nodes = self.build_video_nodes(base_path, self.body())
        self.pdf_nodes = self.build_pdfs_nodes(base_path, self.body())
        body = self.clean(self.body())
        images = self.to_local_images(body)
        self.write_index(self.filepath, '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format(body))
        self.write_images(self.filepath, images)
        self.write_css_js(self.filepath)

    def write_css_js(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scripts.js", content, directory="js/")

    def body(self):
        return self.soup.find("div", class_="pane-node-body")        

    def clean(self, content):
        link_to_text(content)
        remove_links(content)
        remove_iframes(content)
        remove_scripts(content)
        return content

    def to_soup(self):
        document = download(self.source_id)
        if document is not None:
            return BeautifulSoup(document, 'html.parser')

    def write_index(self, filepath, content):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def topic_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.source_id,
            title=self.title,
            description="",
            language=self.lang,
            author="",
            license=LICENSE,
            thumbnail=None,
            children=[]
        )

    def html_node(self):
        return dict(
            kind=content_kinds.HTML5,
            source_id=self.source_id,
            title=self.title,
            description="",
            thumbnail=None,
            author=self.author,
            files=[dict(
                file_type=content_kinds.HTML5,
                path=self.filepath
            )],
            language=self.lang,
            license=LICENSE)

    def add_to_node(self, node, nodes):
        for node_ in nodes:
            if node_ is not None:
                node["children"].append(node_)

    def to_node(self):
        if len(self.video_nodes) > 0 or len(self.pdf_nodes) > 0:
            node = self.topic_node()
            node["children"].append(self.html_node())
            self.add_to_node(node, self.video_nodes)
            self.add_to_node(node, self.pdf_nodes)
        else:
            node = self.html_node()
        return node


class QueryPage:
    def __init__(self, soup):
        self.soup = soup
        self.get_id()

    def get_id(self):
        query_param = self.soup.find("div", class_="mt-guide-tabs-container")
        if query_param is not None:
            self.page_id = query_param.attrs.get("data-page-id", "")
            query_param = self.soup.find("li", class_="mt-guide-tab")
            self.guid = query_param.attrs.get("data-guid", "")
        else:
            self.page_id = None
            self.guid = None

    def body(self):
        if self.page_id is not None and self.guid is not None:
            url = "{}@api/deki/pages/=Template%253AMindTouch%252FIDF3%252FViews%252FTopic_hierarchy/contents?dream.out.format=json&origin=mt-web&pageid={}&draft=false&guid={}".format(BASE_URL, self.page_id, self.guid)
            json = requests.get(url).json()
            return BeautifulSoup(json["body"], 'html.parser')


class YouTubeResource(object):
    def __init__(self, source_id, name=None, type_name="Youtube", lang="en", 
            embeded=False, section_title=None, description=None):
        LOGGER.info("     + Resource Type: {}".format(type_name))
        LOGGER.info("     - URL: {}".format(source_id))
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        if embeded is True:
            self.source_id = YouTubeResource.transform_embed(source_id)
        else:
            self.source_id = self.clean_url(source_id)
        
        self.name = name
        self.section_title = self.get_name(section_title)
        self.description = description
        self.file_format = file_formats.MP4
        self.lang = lang
        self.is_valid = False

    def clean_url(self, url):
        if url[-1] == "/":
            url = url[:-1]
        return url.strip()

    def get_name(self, name):
        if name is None:
            name = self.source_id.split("/")[-1]
            name = name.split("?")[0]
            return " ".join(name.split("_")).title()
        else:
            return name

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
                'noplaylist': False
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
                LOGGER.info("Subtitles: {}".format(",".join(subtitles_info.keys())))
                for language in subtitles_info.keys():
                    subs.append(dict(file_type=SUBTITLES_FILE, youtube_id=video_id, language=language))
        return subs

    def download(self, download=True, base_path=None):
        download_to = build_path([base_path])
        for i in range(4):
            try:
                info = self.get_video_info(download_to=download_to, subtitles=False)
                if info is not None:
                    LOGGER.info("    + Video resolution: {}x{}".format(info.get("width", ""), info.get("height", "")))
                    if self.description is None:
                        self.description = info.get("description", None)
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
                LOGGER.info("    + An error ocurred, may be the video is not available.")
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
                description=self.description,
                author=None,
                files=files,
                language=self.lang,
                license=LICENSE
            )
            return node



class File(object):
    def __init__(self, source_id, lang="en", name=None):
        self.filename = get_name_from_url(source_id)
        self.source_id = urljoin(BASE_URL, source_id) if source_id.startswith("/") else source_id
        self.filepath = None
        self.lang = lang
        self.name = "{}_{}".format(name, self.filename)

    def download(self, download=True, base_path=None):
        try:
            if download is False:
                return
            response = sess.get(self.source_id)
            content_type = response.headers.get('content-type')
            if 'application/pdf' in content_type:
                self.filepath = os.path.join(base_path, self.filename)
                with open(self.filepath, 'wb') as f:
                    for chunk in response.iter_content(10000):
                        f.write(chunk)
                LOGGER.info("    - Get file: {}, node name: {}".format(self.filename, self.name))
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        except requests.exceptions.ReadTimeout as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))

    def to_node(self):
        if self.filepath is not None:
            node = dict(
                kind=content_kinds.DOCUMENT,
                source_id=self.source_id,
                title=self.name,
                description='',
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=LICENSE)
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
            return document
        tries += 1
    return False


def get_index_range(only_pages):
    if only_pages is None:
            from_i = 0
            to_i = None
    else:
        index = only_pages.split(":")
        if len(index) == 2:
            if index[0] == "":
                from_i = 0
                to_i = int(index[1])
            elif index[1] == "":
                from_i = int(index[0])
                to_i = None
            else:
                index = map(int, index)
                from_i, to_i = index
        elif len(index) == 1:
            from_i = int(index[0])
            to_i = from_i + 1
    return from_i, to_i


# The chef subclass
################################################################################
class CienciaNasaChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    THUMBNAIL = ""

    def __init__(self):
        build_path([CienciaNasaChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(CienciaNasaChef.TREES_DATA_DIR, 
                                CienciaNasaChef.SCRAPING_STAGE_OUTPUT_TPL)
        super(CienciaNasaChef, self).__init__()

    def pre_run(self, args, options):
        self.download_css_js()
        self.write_tree_to_json(self.scrape(args, options))

    def download_css_js(self):
        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/css/styles.css")
        with open("chefdata/styles.css", "wb") as f:
            f.write(r.content)

        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/js/scripts.js")
        with open("chefdata/scripts.js", "wb") as f:
            f.write(r.content)

    def scrape(self, args, options):
        only_pages = options.get('--only-pages', None)
        only_videos = options.get('--only-videos', None)
        download_video = options.get('--download-video', "1")

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        global channel_tree
        channel_tree = dict(
                source_domain=CienciaNasaChef.HOSTNAME,
                source_id=BASE_URL,
                title=CHANNEL_NAME,
                description="""Exploración de las actividades de ciencia de NASA con blogs, videos, y artículos cortos adecuados por todas las edades. Este recurso incluye contenidos sobre la ciencia espacial, la ciencia terrestre, la ciencia física, y más.
"""
[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=None,
                author=AUTHOR,
                language=CHANNEL_LANGUAGE,
                children=[],
                license=LICENSE,
            )

        #p_from_i, p_to_i = get_index_range(only_pages)
        #v_from_i, v_to_i = get_index_range(only_videos)
        #browser = Browser(BASE_URL)
        #links = browser.run(p_from_i, p_to_i)
        #collections = LinkCollection(links)
        #for collection_node in collections.to_node():
        #    if collection_node is not None:
        #        channel_tree["children"].append(collection_node)
        #base_path = build_path([DATA_DIR, "test"])
        #article = Article("Siga al Sol", "https://ciencia.nasa.gov/siga-al-sol")
        #article.to_file(base_path)
        #print(article.to_node())
        for node in Browser(BASE_URL).run():
            print(node)
        return channel_tree

    def write_tree_to_json(self, channel_tree):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)


# CLI
################################################################################
if __name__ == '__main__':
    chef = CienciaNasaChef()
    chef.main()
