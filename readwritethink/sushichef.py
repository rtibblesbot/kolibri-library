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
    #url = "http://www.readwritethink.org/resources/resource-print.html?id=410"
    url = "http://www.readwritethink.org/resources/resource-print.html?id=1121"
    collection_type = "Lesson Plan"
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
            source_id="test",
            type=collection_type,
            obj_id="410")
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
                    url = urljoin(BASE_URL, a["href"])
                    print_page = PrintPage()
                    print_page.search_printpage_url(url)
                    print_page.get_type()
                    yield dict(url=print_page.url, 
                        collection=print_page.type,
                        id=print_page.resource_id)

                page_number += 1
                if page_number > limit_page:
                    break


class PrintPage(object):
    def __init__(self):
        self.url = None
        self.type = None
        self.resource_id = None

    def search_printpage_url(self, url):
        try:
            page_contents = downloader.read(url, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        page = BeautifulSoup(page_contents, 'html.parser')
        print_page = page.find(lambda tag: tag.name == "a" and tag.findParent("img", id="icon-materials"))
        self.url = self.parse_js(print_page.attrs["onclick"])
        self.resource_id = self.url.split("id=")[-1]

    def get_type(self):
        try:
            page_contents = downloader.read(self.url, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        page = BeautifulSoup(page_contents, 'html.parser')
        h3 = page.find("h3", class_="pad3b")
        self.type = h3.text

    def parse_js(self, value):
        init = value.find("/")
        end = value.find("',")
        return urljoin(BASE_URL, value[init:end]).strip()


class Collection(object):
    def __init__(self, url, source_id, type, subjects_area=None, obj_id=None):
        self.page = self.download_page(url)
        if self.page is not False:
            self.title = self.clean_title(self.page.find("h1"))
            if self.title is None:
                self.title = title
            #self.contribution_by = None
            self.source_id = source_id
            self.resource_url = url
            self.type = type
            self.license = None
            self.lang = "en"
            #self.subjects_area = subjects_area
            self.obj_id = obj_id
            
            #if self.type == "MakerChallenges":
            #    self.curriculum_type = MakerChallenge()
            if self.type == "Lesson Plan":
                #p = self.page.find("p", id="footer-l")
                #print(p.text, p.text.find("©"))
                #print(self.title)
                #print("LESSON")
                self.curriculum_type = LessonPlan()
            #elif self.type == "Activities":
            #    self.curriculum_type = Activity()
            #elif self.type == "CurricularUnits":
            #    self.curriculum_type = CurricularUnit()
            #elif self.type == "Sprinkles":
            #    self.curriculum_type = Sprinkle()

    def download_page(self, url):
        tries = 0
        while tries < 4:
            try:
                document = downloader.read(url, loadjs=False, session=sess)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            except requests.exceptions.ConnectionError:
                ### this is a weird error, may be it's raised when teachengineering's webpage
                ### is slow to respond requested resources
                LOGGER.info("Connection error, the resource will be scraped in 5s...")
                time.sleep(3)
            else:
                return BeautifulSoup(document, 'html.parser') #html5lib
            tries += 1
        return False

    def clean_title(self, title):
        if title is not None:
            text = title.text.replace("\t", " ")
            return text.strip()

    def drop_null_sections(self, menu):
        sections = OrderedDict()
        for section in self.curriculum_type.render(self, menu_filename=menu.filepath):#self.curriculum_type.render(menu.filepath):
            #if section.body is None:
            #    menu.remove(section.id)
            #else:
            sections[section.__class__.__name__] = section
        return sections

    ##activities, lessons, etc
    def topic_info(self):
        return dict(
                kind=content_kinds.TOPIC,
                source_id=self.type,
                title=self.type,
                description="",
                license=self.license,
                children=[]
            )

    def empty_info(self, url):
        return dict(
                kind=content_kinds.TOPIC,
                source_id=url,
                title="TMP",
                thumbnail=None,
                description="",
                license=get_license(licenses.CC_BY, copyright_holder="X").as_dict(),
                children=[]
            )

    def get_thumbnail(self, sections):
        thumbnail_img = None
        for section in sections:
            if section.id == "summary" or section.id == "intro":
                if section.img_url is not None:
                    ext = section.img_url.split(".")[-1]
                    if ext in ['jpg', 'jpeg', 'png']:
                        thumbnail_img = section.img_url #section summary or introduction
                break
        return thumbnail_img

    def get_subjects_area(self):
        if self.subjects_area is None:
            copy_page = copy.copy(self.page)
            ql = QuickLook(copy_page)
            return ql.get_subject_area()
        else:
            return self.subjects_area

    def to_file(self, channel_tree):
        from collections import namedtuple
        LOGGER.info(" + [{}]: {}".format(self.type, self.title))
        LOGGER.info("   - URL: {}".format(self.resource_url))
        copy_page = copy.copy(self.page)
        base_path = build_path([DATA_DIR, self.type, self.obj_id])
        filepath = "{path}/{title}.zip".format(path=base_path, 
            title=self.title)
        Menu = namedtuple('Menu', ['filepath'])
        menu = Menu(filepath=filepath)
        #menu = None
        #menu = Menu(self.page, filepath=filepath, id_="CurriculumNav", 
        #    exclude_titles=["attachments", "comments"], 
        #    include_titles=[("quick", "Quick Look")],
        #    lang=self.lang)
        #menu.add("info", "Info")

        sections = self.drop_null_sections(menu)
        collection_info = sections["QuickLook"].info()
        collection_info["description"] = sections["OverView"].overview
        license = get_license(licenses.CC_BY, copyright_holder=sections["Copyright"].copyright).as_dict()
        collection_info["license"] = license
        pdfs_info = sections["PrintContainer"].build_pdfs_info(base_path, license)
        sections["PrintContainer"].clean_page()
        sections["PrintContainer"].to_file()
        print(pdfs_info)
        #print(collection_info)
        #build the menu index
        #menu.to_file()
        #set section's html files to the menu
        #for section in sections:
        #    menu_filename = menu.set_section(section)
        #    menu_index = menu.to_html(directory="", active_li=menu_filename)
        #    section.to_file(menu_filename, menu_index=menu_index)

        return
        menu.check()
        menu.license = self.license

        #check for pdfs and videos on all page
        all_sections = CollectionSection(copy_page, resource_url=self.resource_url, lang=self.lang)
        pdfs_info = all_sections.build_pdfs_info(base_path, self.license)
        videos_info = all_sections.build_videos_info(base_path, self.license)

        for subject_area in subjects_area:
            subject_area_topic_node = get_level_map(channel_tree, [subject_area])
            if subject_area_topic_node is None:
                subject_area_topic_node = dict(
                    kind=content_kinds.TOPIC,
                    source_id=subject_area,
                    title=_(subject_area),
                    description="",
                    license=self.license,
                    children=[]
                )
                channel_tree["children"].append(subject_area_topic_node)

            topic_node = get_level_map(channel_tree, [subject_area, self.type])
            thumbnail_img = self.get_thumbnail(sections)
            curriculum_info = self.info(thumbnail_img) #curricular name
            description = self.description()
            curriculum_info["children"].append(menu.info(thumbnail_img, self.title, description))
            if pdfs_info is not None:
                curriculum_info["children"] += pdfs_info
            if videos_info is not None:
                curriculum_info["children"] += videos_info
            if topic_node is None:
                topic_node = self.topic_info() #topic name
                subject_area_topic_node["children"].append(topic_node)

            topic_node["children"].append(curriculum_info)
            if self.type == "CurricularUnits":       
                #build a template for the curriculums
                for url, index in CURRICULAR_UNITS_MAP[self.resource_url].items():
                    #search for lessons
                    node = get_node_from_channel(url, channel_tree, exclude="CurricularUnits")
                    if node is None:
                        curriculum_info["children"].append(self.empty_info(url))
                    else:
                        curriculum_info["children"].append(node)
        
        if self.type != "CurricularUnits":
            curriculars_unit_url = LESSONS_CURRICULAR_MAP.get(self.resource_url, [])
            for curricular_unit_url in curriculars_unit_url:
                #search for curricular units
                curricular_nodes = get_multiple_node_from_channel(curricular_unit_url, 
                    channel_tree, max_level=2)
                if curricular_nodes:
                    for curricular_node in curricular_nodes:
                        for i, children in enumerate(curricular_node["children"]):
                            if children["source_id"] == self.resource_url:
                                curricular_node["children"][i] = curriculum_info
                                break


class CurriculumType(object):
    def render(self, collection, menu_filename):
        for meta_section in self.sections:
            Section = meta_section["class"]
            if isinstance(Section, list):
                section = sum([subsection(collection, filename=menu_filename, 
                                menu_name=meta_section["menu_name"])
                                for subsection in Section])
                section.id = meta_section["id"] 
            else:
                section = Section(collection, filename=menu_filename, id_=meta_section["id"], 
                                menu_name=meta_section["menu_name"])
            yield section


class LessonPlan(CurriculumType):
    def __init__(self, *args, **kwargs):
        self.sections = [
            {"id": "quick", "class": QuickLook, "menu_name": "quick_look"},
            {"id": "overview", "class": OverView, "menu_name": "overview"},
            {"id": "print-container", "class": PrintContainer, "menu_name": "body"},
            {"id": "info", "class": Copyright, "menu_name": "info"},
        ]


class CollectionSection(object):
    def __init__(self,  collection, filename=None, id_=None, menu_name=None):
        LOGGER.debug(id_)
        self.id = id_
        self.collection = collection
        self.filename = filename
        self.menu_name = menu_name
        self.img_url = None
        self.lang = "en"

    def __add__(self, o):
        if isinstance(self.body, Tag) and isinstance(o.body, Tag):
            parent = Tag(name="div")
            parent.insert(0, self.body)
            parent.insert(1, o.body)
            self.body = parent
        elif self.body is None and isinstance(o.body, Tag):
            self.body = o.body
        else:
            LOGGER.info("Null sections: {} and {}".format(
                self.__class__.__name__, o.__class__.__name__))

        return self

    def __radd__(self, o):
        return self

    def clean_title(self, title):
        if title is not None:
            title = str(title)
        return title

    def get_content(self):
        remove_iframes(self.body)
        remove_links(self.body)
        return "".join([str(p) for p in self.body])

    def get_pdfs(self):
        urls = {}
        if self.body is not None:
            resource_links = self.body.find_all("a", href=re.compile("\.pdf$"))
            for link in resource_links:
                if link["href"].endswith(".pdf") and link["href"] not in urls:
                    filename = get_name_from_url(link["href"])
                    urls[link["href"]] = (filename, link.text, urljoin(BASE_URL, link["href"]))
            return urls.values()

    def build_pdfs_info(self, path, license=None):
        pdfs_urls = self.get_pdfs()
        if len(pdfs_urls) == 0:
            return

        PDFS_DATA_DIR = build_path([path, 'pdfs'])
        files_list = []
        for filename, name, pdf_url in pdfs_urls:
            try:
                response = downloader.read(pdf_url)
                pdf_filepath = os.path.join(PDFS_DATA_DIR, filename)
                with open(pdf_filepath, 'wb') as f:
                    f.write(response)
                files = dict(
                    kind=content_kinds.DOCUMENT,
                    source_id=pdf_url,
                    title=name,
                    description='',
                    files=[dict(
                        file_type=content_kinds.DOCUMENT,
                        path=pdf_filepath
                    )],
                    language=self.lang,
                    license=license)
                files_list.append(files)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))

        return files_list

    def get_domain_links(self):
        return set([link.get("href", "") for link in self.body.find_all("a") if link.get("href", "").startswith("/")])

    def images_ref_to_local(self, images_ref, prefix=""):
        images = []
        for img in images_ref:
            if img["src"].startswith("/"):
                img_src = urljoin(BASE_URL, img["src"])
            else:
                img_src = img["src"]
            filename = get_name_from_url(img_src)
            img["src"] = prefix + filename
            images.append((img_src, filename))
        return images

    def get_imgs(self, prefix=""):
        images = self.images_ref_to_local(self.body.find_all("img"), prefix=prefix)
        if len(images) > 0:
            self.img_url = images[-1][0]
        return images

    def get_imgs_into_links(self, prefix=""):
        def check_link(tag):
            allowed_ext = ['jpg', 'jpeg', 'png', 'gif']
            img_ext = tag.attrs.get("href", "").split(".")[-1]
            return tag.name  == "a" and img_ext in allowed_ext
        return [a.get("href", None) for a in self.body.find_all(check_link)]

    def get_videos_urls(self):
        urls = set([])
        for iframe in self.body.find_all("iframe"):
            url = iframe["src"]
            if YouTubeResource.is_youtube(url):
                urls.add(YouTubeResource.transform_embed(url))
            iframe.extract()

        queue = self.body.find_all("a", href=re.compile("^http"))
        max_tries = 3
        num_tries = 0
        while queue:
            try:
                a = queue.pop(0)
                ### some links who are youtube resources have shorted thier ulrs
                ### with session.head we can expand it
                if check_shorter_url(a["href"]):
                    resp = sess.head(a["href"], allow_redirects=True)
                    url = resp.url
                else:
                    url = a["href"]
                if YouTubeResource.is_youtube(url, get_channel=False):
                    urls.add(url.strip())
            except requests.exceptions.MissingSchema:
                pass
            except requests.exceptions.TooManyRedirects:
                LOGGER.info("Too many redirections, skip resource: {}".format(a["href"]))
            except requests.exceptions.ConnectionError:
                ### this is a weird error, perhaps it's raised when teachengineering's webpage
                ### is slow to respond requested resources
                LOGGER.info(a["href"])
                num_tries += 1
                LOGGER.info("Connection error, the resource will be scraped in 3s... num try {}".format(num_tries))
                if num_tries < max_tries:
                    queue.insert(0, a)
                else:
                    LOGGER.info("Connection error, give up.")
                time.sleep(3)
            except KeyError:
                pass
            else:
                num_tries = 0
        return urls

    def build_videos_info(self, path, license=None):
        videos_urls = self.get_videos_urls()
        if len(videos_urls) == 0:
            return

        VIDEOS_DATA_DIR = build_path([path, 'videos'])
        videos_list = []

        for i, url in enumerate(videos_urls):
            resource = YouTubeResource(url, lang=self.lang)
            resource.to_file(filepath=VIDEOS_DATA_DIR)
            if resource.resource_file is not None:
                videos_list.append(resource.resource_file)
        return videos_list

    def write(self, filename, content):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_contents(filename, content, directory="files")

    def write_img(self, url, filename):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_url(url, filename, directory="files")

    def to_file(self, filename, menu_index=None):
        if self.body is not None and filename is not None:
            images = self.get_imgs()
            content = self.get_content()

            if menu_index is not None:
                html = '<html><head><meta charset="UTF-8"></head><body>{}{}</body></html>'.format(
                    menu_index, content)
            else:
                html = '<html><head><meta charset="UTF-8"></head><body>{}</body></html>'.format(
                    content)

            self.write(filename, html)
            for img_src, img_filename in images:
                self.write_img(img_src, img_filename)


class QuickLook(CollectionSection):
    def __init__(self, collection, filename=None, id_="quick", menu_name="quick_look"):
        super(QuickLook, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        img_src = self.get_thumbnail()
        filename = get_name_from_url(img_src)
        self.thumbnail = save_thumbnail(img_src, filename)
        self.plan_info = self.get_plan_info()
    
    def get_thumbnail(self):
        div = self.collection.page.find("div", class_="box-fade")
        img = div.find(lambda tag: tag.name == "img" and tag.findParent("p"))
        if img["src"].startswith("/"):
            return urljoin(BASE_URL, img["src"])
        else:
            return img["src"]

    def get_plan_info(self):
        table = self.collection.page.find("table", class_="plan-info")
        rows = table.find_all("td")
        data = {}
        for row_name, row_value in zip(rows[::2], rows[1::2]):
            key = row_name.text.strip().lower()
            if key == "publisher":
                a = row_value.find("a")
                data[key] = {"url": a["href"], "title": a["title"]}
            else:
                data[key] = row_value.text
        return data

    def info(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.collection.source_id,
            title=self.collection.title,
            thumbnail=self.thumbnail,
            description="",
            author=self.plan_info.get("lesson author", ""),
            license="",
            children=[]
        )


class OverView(CollectionSection):
    def __init__(self, collection, filename=None, id_="overview", menu_name="overview"):
        super(OverView, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_overview()

    def get_overview(self):
        self.overview = self.collection.page.find(lambda tag: tag.name == "h3" and\
            tag.findChildren(lambda tag: tag.name == "a" and tag.attrs.get("name", "") == "overview"))
        self.overview = self.overview.findNext("p").text


class Copyright(CollectionSection):
    def __init__(self, collection, filename=None, id_="copyright", menu_name="copyright"):
        super(Copyright, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_copyright_info()

    def get_copyright_info(self):
        p = self.collection.page.find("p", id="footer-l").text
        index = p.find("©")
        if index != -1:
            self.copyright = p[index:].strip().replace("\n", "").replace("\t", "")
            LOGGER.info("   - COPYRIGHT INFO:" + self.copyright)
        else:
            self.copyright = ""


class PrintContainer(CollectionSection):
    def __init__(self, collection, filename=None, id_="print-container", menu_name="body"):
        super(PrintContainer, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.body = self.collection.page
        self.filepath = filename

    def clean_page(self):
        self.body.find("p", id="page-url").decompose()
        self.body.find("div", class_="table-tabs-back").decompose()
        self.body.find("span", class_="print-page-button").decompose()
        self.body.find("div", id="email-share-print").decompose()
        for p in self.body.find_all(lambda tag: tag.name == "p" and\
            "txt-right" in tag.attrs.get("class", []) and tag.findChildren("img")):
            p.decompose()

        comments = self.body.find(lambda tag: tag.name == "h3" and tag.text == "Comments")
        for section in comments.find_all_next():
            if section.name == "div" and section.attrs.get("id", "") == "footer":
                break
            section.decompose()
        comments.decompose()

        remove_links(self.body)

    def write(self, content):
        with html_writer.HTMLWriter(self.filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def to_file(self):
        if self.body is not None:
            images = self.get_imgs(prefix="files/")
            html = '<html><head><meta charset="UTF-8"></head><body>{}</body></html>'.format(
                self.body)
            self.write(html)
            for img_src, img_filename in images:
                self.write_img(img_src, img_filename)


def save_thumbnail(url, save_as):
    THUMB_DATA_DIR = build_path([DATA_DIR, 'thumbnail'])
    filepath = os.path.join(THUMB_DATA_DIR, save_as)
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
    params_index = tail.find("&")
    if params_index != -1:
        tail = tail[:params_index]
    basename = ntpath.basename(url)
    params_b_index = basename.find("&")
    if params_b_index != -1:
        basename = basename[:params_b_index]
    return tail or basename


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
        #self.thumbnail = save_thumbnail()
        super(ReadWriteThinkChef, self).__init__()

    def pre_run(self, args, options):
        #self.crawl(args, options)
        self.scrape(args, options)
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
            web_resource_tree["children"].append(data)
        with open(crawling_stage, 'w') as f:
            json.dump(web_resource_tree, f, indent=2)
        return web_resource_tree

    def scrape(self, args, options):
        crawling_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                                ReadWriteThinkChef.CRAWLING_STAGE_OUTPUT_TPL)
        with open(crawling_stage, 'r') as f:
            web_resource_tree = json.load(f)
            assert web_resource_tree['kind'] == 'ReadWriteThinkResourceTree'
         
        test()
        #channel_tree = self._build_scraping_json_tree(web_resource_tree)
        #self.write_tree_to_json(channel_tree, lang)

    def write_tree_to_json(self, channel_tree, lang):
        scrape_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                                ReadWriteThinkChef.SCRAPING_STAGE_OUTPUT_TPL)
        write_tree_to_json_tree(scrape_stage, channel_tree)

    #def get_json_tree_path(self, **kwargs):
    #    lang = kwargs.get('lang', "en")
    #    json_tree_path = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
    #                ReadWriteThinkChef.SCRAPING_STAGE_OUTPUT_TPL)
    #    return json_tree_path

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
                            source_id=resource["url"],
                            type=resource["collection"],
                            obj_id=resource["id"])
            collection.to_file(channel_tree)
            break
            #if counter == 20:
            #    break
            #counter += 1
        return channel_tree


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = ReadWriteThinkChef()
    chef.main()
