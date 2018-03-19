#!/usr/bin/env python

from bs4 import BeautifulSoup
from bs4 import Tag
from collections import OrderedDict, defaultdict
import copy
from http import client
import gettext
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
#from utils import save_thumbnail, if_file_exists, load_tree
#from utils import if_dir_exists, get_name_from_url, get_name_from_url_no_ext
from utils import build_path, remove_links, remove_iframes, check_shorter_url
#from utils import get_level_map
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
DOWNLOAD_VIDEOS = True

# time.sleep for debugging proporses, it helps to check log messages
TIME_SLEEP = .8

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "TESSIndia"

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
        #resource.to_file()
        #node = resource.to_node(channel_tree)
        #channel_tree["children"].append(node)
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
        self.get_resources()

    def get_resources(self):
        try:
            page_contents = downloader.read(self.source_id, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            page = BeautifulSoup(page_contents, 'html.parser')
            for material in page.findAll("div", class_=["node-learning-material"]):
                resource = material.find(lambda tag: tag.name == "a" and tag.findParent("h2"))
                if resource is not None:
                    print(resource["href"], resource.text)
                else:
                    print(material.find("h2").text)


class TESSIndiaChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    CRAWLING_STAGE_OUTPUT_TPL = 'web_resource_tree.json'
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    LICENSE = get_license(licenses.CC_BY, copyright_holder=COPYRIGHT_HOLDER).as_dict()
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
        #self.scrape(args, options)
        test()

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
        from collections import Counter
        LANG = 'en'
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
                try:
                    page_contents = downloader.read(resource, loadjs=False)
                except requests.exceptions.HTTPError as e:
                    LOGGER.info("Error: {}".format(e))
                else:
                    LOGGER.info("+ {}".format(resource))
                    page = BeautifulSoup(page_contents, 'html.parser')
                    autor = page.find("div", class_="article-byline")
                    copyright = autor.find("em")
                    copyright = copyright.text.strip()
                    LOGGER.info("   - Copyright: {}".format(copyright))
                    copyrights.append(copyright)
                    time.sleep(TIME_SLEEP)
            counter += 1
        ct = Counter(copyrights)
        print(ct)
        return channel_tree


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = TESSIndiaChef()
    chef.main()
