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
import ntpath
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
import urllib.parse as urlparse
import youtube_dl


# Additional Constants
################################################################################
LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

# BASE_URL is used to identify when a resource is owned by Edsitement
BASE_URL = "http://www.readwritethink.org"

# If False then no download is made
# for debugging proporses
DOWNLOAD_VIDEOS = True

# time.sleep for debugging proporses, it helps to check log messages
TIME_SLEEP = .1

DATA_DIR = "chefdata"

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
    #url = "https://www.teachengineering.org/activities/view/gat_esr_test_activity1"
    #url = "https://www.teachengineering.org/curricularunits/view/cub_dams"
    #url = "https://www.teachengineering.org/curricularunits/view/umo_sensorswork_unit"
    url = "https://www.teachengineering.org/curricularunits/view/cub_service_unit"
    #collection_type = "Sprinkles"
    #collection_type = "MakerChallenges"
    #collection_type = "Lessons"
    #collection_type = "Activities"
    collection_type = "CurricularUnits"
    channel_tree = dict(
        source_domain="www.readwritethink.org",
        source_id='readwritethink',
        title='ReadWriteThink',
        description="""----"""[:400], #400 UPPER LIMIT characters allowed 
        thumbnail="",
        language="en",
        children=[],
        license=get_license(licenses.CC_BY, copyright_holder="ReadWriteThink").as_dict(),
    )

    try:
        subtopic_name = "test"
        collection = Collection(url, 
            title="test",
            source_id="test",
            type=collection_type,
            lang="en")
        collection.to_file(channel_tree)
    except requests.exceptions.HTTPError as e:
        LOGGER.info("Error: {}".format(e))



class ResourceBrowser(object):
    def __init__(self, resource_url):
        self.resource_url = resource_url

    def get_resource_data(self, limit_page=1):
        pass

    def build_pagination_url(self, page):
        params = {'page': page}
        url_parts = list(urlparse.urlparse(self.resource_url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts)

    def run(self, limit_page=1):
        page_number = 1
        while True:
            url = self.build_pagination_url(page_number)
            try:
                page_contents = downloader.read(url, loadjs=False)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            else:
                LOGGER.info("CRAWLING : URL {}".format(url))
                page = BeautifulSoup(page_contents, 'html.parser')
                browser = page.find("ol", class_="results")
                for a in browser.find_all(lambda tag: tag.name == "a"):
                    #dict(url=url, collection=resource["collection"],
    #                url_es=url_es,
    #                spanishVersionId=resource["spanishVersionId"],
    #                title=resource["title"], summary=resource["summary"],
    #                grade_target=resource["gradeTarget"],
    #                grade_range=resource["gradeRange"],
    #                id=resource["id"])
                    print_page = PrintPage(urljoin(BASE_URL, a["href"]))
                    yield print_page.search_printpage_url()
                page_number += 1
                if page_number > limit_page:
                    break

    #def build_resource_url(self, id_name, collection):
    #    return urljoin(BASE_URL, collection.lower()+"/view/"+id_name)


class PrintPage(object):
    def __init__(self, url):
        self.url = url

    def search_printpage_url(self):
        try:
            page_contents = downloader.read(self.url, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        page = BeautifulSoup(page_contents, 'html.parser')
        print_page = page.find(lambda tag: tag.name == "a" and tag.findParent("img", id="icon-materials"))
        print("PRINT PAGE", self.parse_js(print_page.attrs["onclick"]))

    def parse_js(self, value):
        init = value.find("/")
        end = value.find("',")
        return urljoin(BASE_URL, value[init:end])


def save_thumbnail():
    url = "https://scontent.xx.fbcdn.net/v/t1.0-1/p50x50/10492197_815509258473514_3497726003055575270_n.jpg?oh=bfcd61aebdb3d2265c31c2286290bd31&oe=5B1FACCA"
    THUMB_DATA_DIR = build_path([DATA_DIR, 'thumbnail'])
    filepath = os.path.join(THUMB_DATA_DIR, "TELogoNew.jpg")
    document = downloader.read(url, loadjs=False, session=sess)        
    with open(filepath, 'wb') as f:
        f.write(document)
        return filepath


def if_file_exists(filepath):
    file_ = Path(filepath)
    return file_.is_file()


def if_dir_exists(filepath):
    file_ = Path(filepath)
    return file_.is_dir()


def get_name_from_url(url):
    head, tail = ntpath.split(url)
    return tail or ntpath.basename(url)


def get_name_from_url_no_ext(url):
    path = get_name_from_url(url)
    path_split = path.split(".")
    if len(path_split) > 1:
        name = ".".join(path_split[:-1])
    else:
        name = path_split[0]
    return name


def build_path(levels):
    path = os.path.join(*levels)
    if not if_dir_exists(path):
        os.makedirs(path)
    return path


def remove_links(content):
    if content is not None:
        for link in content.find_all("a"):
            link.replaceWithChildren()

def remove_iframes(content):
    if content is not None:
        for iframe in content.find_all("iframe"):
            iframe.extract()


class ReadWriteThinkChef(JsonTreeChef):
    ROOT_URL = "http://{HOSTNAME}"
    HOSTNAME = "www.readwritethink.org"
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    CRAWLING_STAGE_OUTPUT_TPL = 'web_resource_tree.json'
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    LICENSE = get_license(licenses.CC_BY, copyright_holder="ReadWriteThink").as_dict()
    #THUMBNAIL = 'https://www.teachengineering.org/images/logos/v-636511398960000000/TELogoNew.png'
    THUMBNAIL = "http://www.readwritethink.org/images/rwt-243.gif"

    def __init__(self):
        build_path([ReadWriteThinkChef.TREES_DATA_DIR])
        self.thumbnail = save_thumbnail()
        super(ReadWriteThinkChef, self).__init__()

    def pre_run(self, args, options):
        self.crawl(args, options)
        #self.scrape(args, options)
        #test()

    def crawl(self, args, options):
        web_resource_tree = dict(
            kind='ReadWriteThinkResourceTree',
            title='ReadWriteThink',
            children=[]
        )
        crawling_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR,                     
                                    ReadWriteThinkChef.CRAWLING_STAGE_OUTPUT_TPL)
        curriculum_url = urljoin(ReadWriteThinkChef.ROOT_URL.format(HOSTNAME=ReadWriteThinkChef.HOSTNAME), "search/?resource_type=6")
        resource_browser = ResourceBrowser(curriculum_url)
        for data in resource_browser.run():
            print(data)
            #web_resource_tree["children"].append(data)
        #with open(crawling_stage, 'w') as f:
        #    json.dump(web_resource_tree, f, indent=2)
        #return web_resource_tree

    def scrape(self, args, options):
        crawling_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                                ReadWriteThinkChef.CRAWLING_STAGE_OUTPUT_TPL.format(lang))
        with open(crawling_stage, 'r') as f:
            web_resource_tree = json.load(f)
            assert web_resource_tree['kind'] == 'ReadWriteThinkResourceTree'
         
        channel_tree = self._build_scraping_json_tree(web_resource_tree)
        self.write_tree_to_json(channel_tree, lang)

    def write_tree_to_json(self, channel_tree, lang):
        scrape_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                                ReadWriteThinkChef.SCRAPING_STAGE_OUTPUT_TPL)
        write_tree_to_json_tree(scrape_stage, channel_tree)

    def get_json_tree_path(self, **kwargs):
        lang = kwargs.get('lang', "en")
        json_tree_path = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                    ReadWriteThinkChef.SCRAPING_STAGE_OUTPUT_TPL)
        return json_tree_path

    def _build_scraping_json_tree(self, web_resource_tree):
        LANG = 'en'
        channel_tree = dict(
            source_domain=ReadWriteThinkChef.HOSTNAME,
            source_id='readwritethink',
            title='ReadWriteThink',
            description="""Here at ReadWriteThink, our mission is to provide educators, parents, and afterschool professionals with access to the highest quality practices in reading and language arts instruction by offering the very best in free materials.."""[:400], #400 UPPER LIMIT characters allowed 
            thumbnail=ReadWriteThinkChef.THUMBNAIL,
            language=LANG,
            children=[],
            license=ReadWriteThinkChef.LICENSE,
        )
        #counter = 0
        for resource in web_resource_tree["children"]:
            collection = Collection(resource["url"],
                            source_id=resource["id"],
                            type=resource["collection"],
                            title=resource["title"],
                            lang=LANG)
            collection.to_file(channel_tree)
            #if counter == 20:
            #    break
            #counter += 1
        living_labs = LivingLabs()
        channel_tree["children"].append(living_labs.sections(channel_tree))
        return channel_tree


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = ReadWriteThinkChef()
    chef.main()
