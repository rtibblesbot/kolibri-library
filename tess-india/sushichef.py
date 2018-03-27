#!/usr/bin/env python

from bs4 import BeautifulSoup
from bs4 import Tag
from collections import OrderedDict, defaultdict
import copy
from http import client
import gettext
import hashlib
import json
from le_utils.constants import licenses, content_kinds, file_formats
import logging
import os
import pafy
from pathlib import Path
import re
import requests
from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.jsontrees import write_tree_to_json_tree, SUBTITLES_FILE
import sys
import time
from urllib.error import URLError
from urllib.parse import urljoin, urlencode
from utils import save_thumbnail, if_file_exists, load_tree
from utils import if_dir_exists, get_name_from_url, get_name_from_url_no_ext
from utils import build_path, remove_links, remove_iframes, check_shorter_url
from utils import get_level_map, get_node_from_channel
import urllib.parse as urlparse
import youtube_dl


# Additional Constants
################################################################################
LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

# BASE_URL is used to identify when a resource is owned by Edsitement
BASE_URL = "http://www.tess-india.edu.in/learning-materials"

# If False then no download is made
# for debugging proporses
DOWNLOAD_VIDEOS = False

# time.sleep for debugging proporses, it helps to check log messages
TIME_SLEEP = .8

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "The Open University"

#Curricular units with its lessons
CURRICULAR_UNITS_MAP = defaultdict(OrderedDict)
#Lessons related with curricular units
LESSONS_CURRICULAR_MAP = defaultdict(set)
# webcache
###############################################################
sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)

# Main Scraping Method
################################################################################

def test():
    """
    Test individual resources
    """
    url = "http://www.tess-india.edu.in/learning-materials?course_tid=136&subject_tid=181&educational_level_tid=221"
    channel_tree = dict(
        source_domain=TESSIndiaChef.HOSTNAME,
        source_id='tessindia',
        title='TESSIndia',
        description="""TESS-India is led by The Open University and Save The Children India, funded by UK Aid it is a multilingual teacher professional development programme whose aim is to support India’s national educational policy by enhancing the classroom practice of primary and secondary school teachers through the provision of freely available, adaptable Open Educational Resources (OER)."""[:400], #400 UPPER LIMIT characters allowed 
        thumbnail=None,
        language="en",
        children=[],
        license=TESSIndiaChef.LICENSE,
    )
    try:
        resource = Resource(source_id=url,
            lang="en",
            state="All India - English",
            subject="English",
            level="Elementary")
        resource.scrape()
        resource.to_tree(channel_tree)
    except requests.exceptions.HTTPError as e:
        LOGGER.info("Error: {}".format(e))
    return channel_tree


class ResourceBrowser(object):
    def __init__(self, resource_url):
        self.resource_url = resource_url

    def build_url(self, course_tid=None, subject_tid=None, educational_level_tid=None):
        if educational_level_tid is not None:
            params = dict(course_tid=course_tid, subject_tid=subject_tid, 
                        educational_level_tid=educational_level_tid)
        else:
            params = dict(course_tid=course_tid, subject_tid=subject_tid)
        url_parts = list(urlparse.urlparse(self.resource_url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts)

    def get_total_items(self, text):
        string = re.search(r"\d+\-\d+ of \d+", text).group()
        return int(string.split("of")[-1].strip())

    def run(self, limit_page=1, page_number=1):
        total_items = None
        counter = 0
        try:
            page_contents = downloader.read(self.resource_url, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            page = BeautifulSoup(page_contents, 'html.parser')
            states = page.find("div", class_=["lm-filter-course"])
            states_tree = self.get_state_lang(states)
            subjects = page.find("div", class_=["lm-filter-subject"])
            subjects_tree = self.get_subjects(subjects)
            levels = page.find("div", class_=["lm-filter-level"])
            levels_tree = self.get_levels(levels)
            pages_params = self.build_page_params(states_tree, subjects_tree, levels_tree)
            for page_params in pages_params:
                url = self.build_url(page_params["course_tid"], 
                    page_params["subject_tid"], 
                    page_params.get("educational_level_tid", None))
                yield dict(url=url,
                    subject_name=page_params["subject_name"],
                    state_lang=page_params["state_lang"],
                    level_name=page_params.get("level_name", None))
                LOGGER.info("CRAWLING : URL {}".format(url))
                time.sleep(TIME_SLEEP)

    def get_state_lang(self, items):
        tree = {}
        for state_data in items.findAll("button"):
            tree[state_data["data-tid"]] = state_data.text.strip()
        return tree

    def get_subjects(self, items):
        tree = {}
        for subject_data in items.findAll("button"):
            if subject_data["data-course"] == "all":
                continue
            tree.setdefault(subject_data["data-course"], {})
            tree[subject_data["data-course"]][subject_data["data-tid"]] = (subject_data.text.strip(), bool(int(subject_data.get("data-hide-level", "0"))))
        return tree

    def get_levels(self, items):
        tree = {}
        for subject_data in items.findAll("button"):
            tree.setdefault(subject_data["data-course"], {})
            tree[subject_data["data-course"]][subject_data["data-tid"]] = subject_data.text.strip()
        return tree

    def build_page_params(self, states, subjects, levels):
        pages = []#course_tid, subject_tid, educational_level_tid
        for course_tid in subjects:
            for subjects_tid in subjects[course_tid]:
                subject_name = subjects[course_tid][subjects_tid][0]
                not_has_levels = subjects[course_tid][subjects_tid][1]
                info = {"course_tid": course_tid, "subject_tid": subjects_tid,
                    "state_lang": states[course_tid], "subject_name": subject_name}
                if not_has_levels is False:
                    for level_tid in levels[course_tid]:
                        info_tmp = info.copy()
                        info_tmp["educational_level_tid"] = level_tid
                        info_tmp["level_name"] = levels[course_tid][level_tid]
                        pages.append(info_tmp)
                else:        
                    pages.append(info)
        return pages


class Resource(object):
    def __init__(self, source_id,  lang="en", state=None, subject=None, level=None):
        self.source_id = source_id
        self.lang = lang
        self.state = state
        self.subject = subject
        self.level = level
        self.nodes = []

    def scrape(self):
        page = download(self.source_id)
        for material in page.findAll("div", class_=["node-learning-material"]):
            resource = material.find(lambda tag: tag.name == "a" and tag.findParent("h2"))
            if resource is not None:
                lesson_name = resource.text
                lesson_url = resource["href"]
            else:
                lesson_name = material.find("h2").text
                lesson_url = material.attrs.get("about", "")
            extra_resources = material.findAll(lambda tag: tag.name == "a" and \
                tag.findParent("div", class_=["lmat-download"]))
            extra_resources_urls = set([])
            for extra_resource in extra_resources:
                extra_resources_urls.add(extra_resource["href"])
            lesson = Lesson(name=lesson_name, key_resource_id=lesson_url,
                extra_resources=extra_resources_urls, path=[self.state, self.subject, self.level])
            lesson.download()
            self.nodes.append(lesson.to_node())

    def empty_state_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.state,
            title=self.state,
            description="",
            license=None,
            children=[]
        )

    def empty_subject_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.subject,
            title=self.subject,
            description="",
            license=None,
            children=[]
        )

    def empty_level_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.level,
            title=self.level,
            description="",
            license=None,
            children=[]
        )

    def build_tree(self, nodes, subtree=None, tree_level=0):
        if tree_level == 0:
            if subtree is None:
                root = self.empty_state_node()
            else:
                root = subtree
            subject = self.empty_subject_node()
            if self.level is not None:
                level = self.empty_level_node()
                level["children"].extend(nodes)
                subject["children"].append(level)
            else:
                subject["children"].extend(nodes)
            root["children"].append(subject)
            return root
        elif tree_level == 1:
            subject = subtree
            if self.level is not None:
                level = self.empty_level_node()
                level["children"].extend(nodes)
                subject["children"].append(level)
            else:
                subject["children"].extend(nodes)
        elif tree_level == 2:
            level = subtree
            level["children"].extend(nodes)

    def get_tree_level(self, channel_tree):
        subtree = get_level_map(channel_tree, [self.state, self.subject, self.level])
        level = 2
        if subtree is None:
            subtree = get_level_map(channel_tree, [self.state, self.subject])
            level -= 1
            if subtree is None:
                subtree = get_level_map(channel_tree, [self.state])
                level -= 1
        return subtree, level

    def to_tree(self, channel_tree):
        subtree, tree_level = self.get_tree_level(channel_tree)
        root = self.build_tree(self.nodes, subtree, tree_level=tree_level)
        if subtree is None and root is not None:
            channel_tree["children"].append(root)
                

class Lesson(object):
    def __init__(self, name=None, key_resource_id=None, extra_resources=None, path=None):
        self.key_resource_id = urljoin(BASE_URL, key_resource_id.strip())
        self.filename = hashlib.sha1(name.encode("utf-8")).hexdigest()
        self.title = name if len(name) < 80 else name[:80]
        self.path_levels = path
        self.file = None
        self.video = None
        LOGGER.info("Collecting: {}".format(self.key_resource_id))
        LOGGER.info("   - Name: {}".format(self.title))
        self.html = HTMLLesson(source_id=self.key_resource_id, name=self.title)
        if self.path_levels[-1] is None:
            self.base_path = build_path([DATA_DIR] + self.path_levels[:-1] + [self.filename])
        else:
            self.base_path = build_path([DATA_DIR] + self.path_levels + [self.filename])
        if extra_resources is not None:
            LOGGER.info("   - Extra resources: {}".format(len(extra_resources)))
            self.set_extra_resources(extra_resources)

    def set_extra_resources(self, extra_resources):
        for resource in extra_resources:
            LOGGER.info("   - Resource: {}".format(resource))
            if resource.endswith(".pdf"):
                self.file = File(resource)
            elif resource.endswith(".doc") or resource.endswith(".docx"):
                pass
            else:
                resource = urljoin(BASE_URL, resource.strip())
                if resource != self.key_resource_id:
                    self.video = HTMLLesson(source_id=resource, name=self.title + " - Videos")

    def download(self):
        self.html.scrape(self.base_path, name="index")
        if self.file:
            self.file.download(self.base_path)
        if self.video:
            self.video.scrape(self.base_path, name="video")

    def to_node(self):
        topic_node = dict(
            kind=content_kinds.TOPIC,
            source_id=self.key_resource_id,
            title=self.title,
            description="",
            license=None,
            children=[]
        )

        topic_node["children"].extend(self.html.to_nodes())
        if self.file is not None:
            file_node = self.file.to_node()
            topic_node["children"].append(file_node)

        if self.video is not None:
            videos_nodes = self.video.to_nodes()
            topic_node["children"].extend(videos_nodes)
        
        return topic_node
        

class File(object):
    def __init__(self, source_id, lang="en", lincese=""):
        self.filename = get_name_from_url(source_id)
        self.source_id = urljoin(BASE_URL, source_id) if source_id.startswith("/") else source_id
        self.filepath = None
        self.lang = lang
        self.license = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def download(self, base_path):
        PDFS_DATA_DIR = build_path([base_path, 'pdfs'])
        try:
            response = sess.get(self.source_id)
            content_type = response.headers.get('content-type')
            #response = downloader.read(self.source_id)
            if 'application/pdf' in content_type:
                self.filepath = os.path.join(PDFS_DATA_DIR, self.filename)
                with open(self.filepath, 'wb') as f:
                    for chunk in response.iter_content(10000):
                        f.write(chunk)
                LOGGER.info("   - Get file: {}".format(self.filename))
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))

    def to_node(self):
        if self.filepath is not None:
            node = dict(
                kind=content_kinds.DOCUMENT,
                source_id=self.source_id,
                title=self.filename,
                description='',
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=self.license)
            return node


class HTMLLesson(object):
    def __init__(self, source_id=None, name=None):
        self.source_id = source_id
        self.filepath = None
        self.name = name
        self.menu = Menu()
        self.license = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def sections_to_menu(self):
        page = download(self.source_id)
        if page:
            content = page.find("main", class_="content-main")
            ul = content.find(lambda tag: tag.name == "ul" and tag.findParent("div", class_="content"))
            self.menu.index_content = ul
            href = None
            for link in content.findAll("a"):
                href = link.get("href", "")
                links_class = link.get("class", [])
                if href:# and "active" not in links_class:
                    self.menu.add_item(title=link.text, url=urljoin(self.source_id, href))

    def scrape(self, base_path, name="htmlapp"):
        self.filepath = "{path}/{name}.zip".format(path=base_path, name=name)
        self.sections_to_menu()
        self.menu.to_file(self.filepath, base_path)

    def to_nodes(self):
        menu_node = self.menu.to_nodes()
        if len(self.menu.items) > 0:
            node = dict(
                kind=content_kinds.HTML5,
                source_id=self.source_id,
                title=self.name,
                description="",
                thumbnail=None,
                author="",
                files=[dict(
                    file_type=content_kinds.HTML5,
                    path=self.filepath
                )],
                language="en",
                license=self.license)
            return [node] + menu_node
        else:
            return []


class Menu(object):
    def __init__(self):
        self.items = OrderedDict()
        self.index_content = None
        self.images = {}
        self.pdfs_url = set([])
        self.nodes = []

    def build_index(self, directory="files/"):
        items = iter(self.items.values())
        if self.index_content is not None:
            for ul in self.index_content:
                if hasattr(ul, 'findAll'):
                    for a in ul.findAll("a"):
                        item = next(items)
                        a["href"] = "{}{}".format(directory, item["filename"])
                else:
                    return
            return str(self.index_content)

    def add_item(self, title=None, url=None):
        filename = self.item_to_filename(title)
        if url not in self.items:
            content = self.get_sections_content(url)
            self.items[url] = {"title": title, "filename": filename, "content": content}

    def clean_content(self, content):
        content.find("div", class_="addthis").decompose()
        obj_tags = content.find_all("div", class_="oucontent-media")#oucontent-embedtemplate")
        if obj_tags is not None:
            for obj_tag in obj_tags:
                obj_tag.decompose()
        if content is not None:
            for link in content.find_all("a"):
                if "active" not in link.attrs.get("class", []):
                    link.replaceWithChildren()

    def pager(self, content, index):
        ul = content.find("ul", class_="pager")
        first_page = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-first"))
        last_page = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-last"))
        previous = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-previous"))
        next = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-next"))
        if first_page is not None:
            first_page["href"] = "../index.html"
        items = list(self.items.values())
        if last_page is not None:
            last_page["href"] = items[-1]["filename"]
        if previous is not None:
            if index > 0:
                previous["href"] = items[index - 1]["filename"]
            else:
                previous["href"] = first_page["href"]
        if next is not None:
            if index < len(items) - 1:
                next["href"] = items[index + 1]["filename"]
            else:
                next["href"] = last_page["href"]

    def get_sections_content(self, url):
        page = download(url)
        content = page.find("section", class_="main-content")
        return content

    def get_images(self, content):
        for img in content.findAll("img"):
            if img["src"].startswith("/"):
                img_src = urljoin(BASE_URL, img["src"])
            else:
                img_src = img["src"]
            filename = get_name_from_url(img_src)
            if img_src not in self.images and img_src:
                img["src"] = filename
                self.images[img_src] = filename

    def write_pdfs(self, base_path, content):
        for tag_a in content.findAll(lambda tag: tag.name == "a" and tag.attrs.get("href", "").endswith(".pdf")):
            pdf_url = tag_a.get("href", "")
            if pdf_url not in self.pdfs_url and pdf_url:
                self.pdfs_url.add(pdf_url)
                pdf_file = File(pdf_url)
                pdf_file.download(base_path)
                node = pdf_file.to_node()
                if node is not None:
                    self.nodes.append(node)

    def write_video(self, base_path, content):
        videos = content.find_all(lambda tag: tag.name == "a" and tag.attrs.get("href", "").find("youtube") != -1 or tag.attrs.get("href", "").find("youtu.be") != -1 or tag.text.lower() == "youtube")
        VIDEOS_DATA_DIR = build_path([base_path, 'videos'])
        for video in videos:
            youtube = YouTubeResource(video.get("href", ""))
            node = get_node_from_channel(youtube.resource_url, channel_tree)
            if node is None:
                youtube.to_file(filepath=VIDEOS_DATA_DIR)
                node = youtube.node
            else:
                print("############# VIDEO CACHED ###############")

            if node is not None:
                if video.parent.name == 'li':
                    video.parent.replace_with("Video name: " + node["title"])
                self.nodes.append(node)

    def write_index(self, filepath, content):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def write_contents(self, filepath_index, filename, content, directory="files"):
        with html_writer.HTMLWriter(filepath_index, "a") as zipper:
            content = '<html><head><meta charset="UTF-8"></head><body>{}</body></html>'.format(
                content)
            zipper.write_contents(filename, content, directory=directory)
    
    def write_images(self, filepath, content):
        self.get_images(content)
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            for img_src, img_filename in self.images.items():
                zipper.write_url(img_src, img_filename, directory="files")

    def item_to_filename(self, name):
        name = "_".join(name.lower().split(" "))
        hash_name = hashlib.sha1(name.encode("utf-8")).hexdigest()
        return "{}.html".format(hash_name)

    def to_file(self, filepath, base_path):
        index_content = self.build_index()
        if index_content is not None:
            self.write_index(filepath, '<html><head><meta charset="UTF-8"></head><body>'+\
                index_content+'</body></html>')
            for i, item in enumerate(self.items.values()):
                self.write_images(filepath, item["content"])
                file_nodes = self.write_pdfs(base_path, item["content"])
                video_nodes = self.write_video(base_path, item["content"])
                self.pager(item["content"], i)
                self.clean_content(item["content"])
                self.write_contents(filepath, item["filename"], str(item["content"]))

    def to_nodes(self):
        return self.nodes


class ResourceType(object):
    """
        Base class for File, WebPage, Video, Audio resources
    """
    def __init__(self, type_name=None):
        LOGGER.info("Resource Type: "+type_name)
        self.type_name = type_name
        self.node = None

    def to_file(self, filepath=None):
        pass


class YouTubeResource(ResourceType):
    def __init__(self, resource_url, type_name="Youtube", lang="en"):
        super(YouTubeResource, self).__init__(type_name=type_name)
        self.resource_url = self.clean_url(resource_url)
        self.file_format = file_formats.MP4
        self.lang = lang

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

    def get_video_info(self):
        ydl_options = {
                'writesubtitles': True,
                'allsubtitles': True,
                'no_warnings': True,
                'restrictfilenames':True,
                'continuedl': True,
                'quiet': False,
                'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='720')
            }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.resource_url, download=False)
                return info
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('An error occured ' + str(e))
                LOGGER.info(self.resource_url)
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

    def process_file(self, download=False, filepath=None):
        if download is True:
            video_filepath = self.video_download(download_to=filepath)
        else:
            video_filepath = ""#None

        if video_filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=video_filepath)]
            files += self.subtitles_dict()

            self.node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.resource_url,
                title=get_name_from_url_no_ext(video_filepath),
                description='',
                files=files,
                language=self.lang,
                license=get_license(licenses.CC_BY, copyright_holder=COPYRIGHT_HOLDER).as_dict())

    #youtubedl has some troubles downloading videos in youtube,
    #sometimes raises connection error
    #for that I choose pafy for downloading
    def video_download(self, download_to="/tmp/"):
        for try_number in range(10):
            try:
                video = pafy.new(self.resource_url)
                best = video.getbest(preftype="mp4")
                video_filepath = best.download(filepath=download_to)
            except (ValueError, IOError, OSError, URLError, ConnectionResetError) as e:
                LOGGER.info(e)
                LOGGER.info("Download retry:"+str(try_number))
                time.sleep(.8)
            except (youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError, OSError) as e:
                LOGGER.info("An error ocurred, may be the video is not available.")
                return
            else:
                return video_filepath

    def to_file(self, filepath=None):
        self.process_file(download=DOWNLOAD_VIDEOS, filepath=filepath)


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
            return BeautifulSoup(document, 'html.parser') #html5lib
        tries += 1
    return False


class TESSIndiaChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    CRAWLING_STAGE_OUTPUT_TPL = 'web_resource_tree.json'
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()
    THUMBNAIL = ""

    def __init__(self):
        build_path([TESSIndiaChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(TESSIndiaChef.TREES_DATA_DIR, 
                                TESSIndiaChef.SCRAPING_STAGE_OUTPUT_TPL)
        self.crawling_stage = os.path.join(TESSIndiaChef.TREES_DATA_DIR, 
                                TESSIndiaChef.CRAWLING_STAGE_OUTPUT_TPL)
        #self.thumbnail = save_thumbnail()
        super(TESSIndiaChef, self).__init__()

    def pre_run(self, args, options):
        #self.crawl(args, options)
        self.scrape(args, options)

    def crawl(self, args, options):
        web_resource_tree = dict(
            kind='TESSIndiaResourceTree',
            title='TESSIndia',
            children=[]
        )
        crawling_stage = os.path.join(TESSIndiaChef.TREES_DATA_DIR,                     
                                    TESSIndiaChef.CRAWLING_STAGE_OUTPUT_TPL)
        resource_browser = ResourceBrowser(BASE_URL)
        for data in resource_browser.run(limit_page=None, page_number=1):
            web_resource_tree["children"].append(data)
        with open(crawling_stage, 'w') as f:
            json.dump(web_resource_tree, f, indent=2)
        return web_resource_tree

    def scrape(self, args, options):
        cache_tree = options.get('cache_tree', '1')
        
        with open(self.crawling_stage, 'r') as f:
            web_resource_tree = json.load(f)
            assert web_resource_tree['kind'] == 'TESSIndiaResourceTree'
         
        #channel_tree = test()
        channel_tree = self._build_scraping_json_tree(cache_tree, web_resource_tree)
        self.write_tree_to_json(channel_tree, "en")

    def write_tree_to_json(self, channel_tree, lang):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)

    def _build_scraping_json_tree(self, cache_tree, web_resource_tree):
        LANG = 'en'
        global channel_tree
        channel_tree = dict(
                source_domain=TESSIndiaChef.HOSTNAME,
                source_id='tessindia',
                title='TESSIndia',
                description="""TESS-India is led by The Open University and Save The Children India, funded by UK Aid it is a multilingual teacher professional development programme whose aim is to support India’s national educational policy by enhancing the classroom practice of primary and secondary school teachers through the provision of freely available, adaptable Open Educational Resources (OER)."""[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=None,
                language=LANG,
                children=[],
                license=TESSIndiaChef.LICENSE,
            )
        counter = 0
        types = set([])
        total_size = len(web_resource_tree["children"])
        copyrights = []
        for resource in web_resource_tree["children"]:
            if 0 <= counter <= total_size:
                LOGGER.info("{} of {}".format(counter, total_size))
                resource = Resource(source_id=resource["url"],
                    lang="en",
                    state=resource["state_lang"],
                    subject=resource["subject_name"],
                    level=resource["level_name"])
                resource.scrape()
                resource.to_tree(channel_tree)
            counter += 1
        return channel_tree


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = TESSIndiaChef()
    chef.main()
