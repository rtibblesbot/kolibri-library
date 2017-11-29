#!/usr/bin/env python
"""
Edsitement is organized as follow:
- There is two top levels set of topics, Lesson Plans and Student Resources
- Each topic has lessons and resources
- Finally, each lesson or resource has contents like images, videos, pdfs and html5 files.
"""

import os
import sys
from ricecooker.utils import data_writer, path_builder, downloader, html_writer
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages



# Run Constants
################################################################################

CHANNEL_NAME = "EDSITEment"              # Name of channel
CHANNEL_SOURCE_ID = "edsitement-testing" # Channel's unique id    # change to just 'edsitement' for prod
CHANNEL_DOMAIN = "edsitement.neh.gov"         # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
PATH = path_builder.PathBuilder(channel_name=CHANNEL_NAME)  # Keeps track of path to write to csv
WRITE_TO_PATH = "{}{}{}.zip".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, CHANNEL_NAME) # Where to generate zip file

# Additional imports
###########################################################
import logging
from bs4 import BeautifulSoup
import urllib.parse
import time
from collections import OrderedDict
import itertools
import requests

# Additional Constants
################################################################################

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

BASE_URL = "http://edsitement.neh.gov"
STUDENT_RESOURCE_TOPIC_INIT = 0#0
STUDENT_RESOURCE_TOPIC_END = 1 #MAX 4 TOPICS OR NONE
STUDENT_RESOURCE_INIT = 0
STUDENT_RESOURCE_END = 1

LESSON_PLANS_TOPIC_INIT = 0
LESSON_PLANS_TOPIC_END = 1
LESSON_PLANS_INIT = 0
LESSON_PLANS_END = 1

DOWNLOAD_VIDEOS = False

# Main Scraping Method
################################################################################
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
        Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
        Returns: None
    """
    scrap_lesson_plans()
    #scrap_student_resources()


# Helper Methods
################################################################################
def scrap_lesson_plans():
        LESSONS_PLANS_URL = urllib.parse.urljoin(BASE_URL, "lesson-plans")
        for lesson_plan_url, levels in lesson_plans(lesson_plans_subject(LESSONS_PLANS_URL)):
            subtopic_name = lesson_plan_url.split("/")[-1]
            page_contents = downloader.read(lesson_plan_url, loadjs=False)
            page = BeautifulSoup(page_contents, 'html5lib')
            lesson_plan = LessonPlan(page, 
                lesson_filename="/tmp/lesson-"+subtopic_name+".zip",
                resources_filename="/tmp/resources-"+subtopic_name+".zip")
            lesson_plan.source = lesson_plan_url
            lesson_plan.to_file(PATH, levels)


def scrap_student_resources():
    STUDENT_RESOURCES_URL = urllib.parse.urljoin(BASE_URL, "student-resources/")
    subject_ids = [25, 21, 22, 23]
    levels = ["Student Resources"]
    for subject in subject_ids[STUDENT_RESOURCE_TOPIC_INIT:STUDENT_RESOURCE_TOPIC_END]:
        params_url = "all?grade=All&subject={}&type=All".format(subject)
        page_url = urllib.parse.urljoin(STUDENT_RESOURCES_URL, params_url)
        LOGGER.info("Scrapping: " + page_url)
        page_contents = downloader.read(page_url)
        page = BeautifulSoup(page_contents, 'html.parser')
        resource_links = page.find_all(lambda tag: tag.name == "a" and tag.findParent("h3"))
        for link in resource_links[STUDENT_RESOURCE_INIT:STUDENT_RESOURCE_END]:
            time.sleep(.8)
            if link["href"].rfind("/student-resource/") != -1:
                student_resource_url = urllib.parse.urljoin(BASE_URL, link["href"])
                try:
                    page_contents = downloader.read(student_resource_url)
                except requests.exceptions.HTTPError as e:
                    LOGGER.info("Error: {}".format(e))
                page = BeautifulSoup(page_contents, 'html.parser')
                topic_name = student_resource_url.split("/")[-1]
                student_resource = StudentResourceIndex(page, 
                    filename="/tmp/student-resource-"+topic_name+".zip",
                    levels=levels)
                student_resource.to_file()


def lesson_plans_subject(page_url):
    page_contents = downloader.read(page_url)
    LOGGER.info("Scrapping: " + page_url)
    page = BeautifulSoup(page_contents, 'html.parser')
    subject_ids = [25, 21, 22, 23]#, 18319, 18373, 25041, 31471]
    for node in subject_ids:
        page_h3 = page.find("h3", id="node-"+str(node))
        resource_a = page_h3.find("a", href=True)
        subtopic_url = urllib.parse.urljoin(BASE_URL, resource_a["href"].strip())
        yield subtopic_url, ["Lesson Plans or For Teachers"]


def lesson_plans(lesson_plans_subject):
    for lesson_url, levels in itertools.islice(lesson_plans_subject, LESSON_PLANS_TOPIC_INIT, LESSON_PLANS_TOPIC_END): #MAX NUMBER OF SUBJECTS
        page_contents = downloader.read(lesson_url)
        page = BeautifulSoup(page_contents, 'html.parser')
        sub_lessons = page.find_all("div", class_="lesson-plan-link")
        title = page.find("h2", class_="subject-area").text
        LOGGER.info("- Subject:"+title)
        LOGGER.info("- [url]:"+lesson_url)
        for sub_lesson in itertools.islice(sub_lessons, LESSON_PLANS_INIT, LESSON_PLANS_END): #MAX NUMBER OF LESSONS
            resource_a = sub_lesson.find("a", href=True)
            resource_url = resource_a["href"].strip()
            time.sleep(.8)
            yield urllib.parse.urljoin(BASE_URL, resource_url), levels + [title]


def get_name_file(url):
        from urllib.parse import urlparse
        import os
        return os.path.basename(urlparse(url).path)


def get_name_file_no_ext(url):
    path = get_name_file(url)
    return ".".join(path.split(".")[:-1])


def remove_links(content):
    for link in content.find_all("a"):
        link.replaceWithChildren()


class Menu(object):
    def __init__(self, page, filename=None, id_=None):
        self.body = page.find("div", id=id_)
        self.menu = OrderedDict()
        self.filename = filename
        self.menu_titles(self.body.find_all("h4"))

    def write(self, content):
        with html_writer.HTMLWriter(self.filename, "w") as zipper:
            zipper.write_index_contents(content)

    def to_file(self):
        self.write('<html><body><meta charset="UTF-8"></head><ul>'+self.to_html()+'</ul></body></html>')

    def menu_titles(self, titles):
        for title in titles:
            self.add(title.text)

    def get(self, name):
        try:
            return self.menu[name]["filename"]
        except KeyError:
            return None
    
    def add(self, title):
        name = title.lower().replace(" ", "_")
        self.menu[name] = {
            "filename": "{}.html".format(name),
            "text": title
        }

    def to_html(self):
        return "".join(
            '<li><a href="files/{filename}">{text}</a></li>'.format(**e) for e in self.menu.values())


class LessonSection(object):
    def __init__(self, page, filename=None, id_=None, menu_name=None):
        LOGGER.debug(id_)
        self.body = page.find("div", id=id_)
        if self.body is not None:
            self.title = self.clean_title(self.body.find("h4"))
        self.filename = filename
        self.menu_name = menu_name

    def clean_title(self, title):
        if title is not None:
            title = str(title)
        return title

    def get_content(self):
        pass

    def write(self, filename, content):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_contents(filename, content, directory="files")

    def to_file(self, filename):
        if self.body is not None and filename is not None:
            content = self.get_content()
            if self.title:
                content = self.title+""+content
                
            self.write(filename, '<html><head><meta charset="UTF-8"></head><body>{}<body></html>'.format(
                content
            ))


class Introduction(LessonSection):
    def __init__(self, page, filename=None):
        super(Introduction, self).__init__(page, filename=filename, 
            id_="sect-introduction", menu_name="introduction")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        content = content.findChildren("p")
        return "".join([str(p) for p in content])


class GuidingQuestions(LessonSection):
    def __init__(self, page, filename=None):
        super(GuidingQuestions, self).__init__(page, filename=filename, 
            id_="sect-questions", menu_name="guiding_questions")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        content = content.findChildren("ul")
        return "".join([str(p) for p in content])


class LearningObjetives(LessonSection):
    def __init__(self, page, filename=None):
        super(LearningObjetives, self).__init__(page, filename=filename, 
            id_="sect-objectives", menu_name="learning_objectives")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        content = content.findChildren("ul")
        return "".join([str(p) for p in content])


class Background(LessonSection):
    def __init__(self, page, filename=None):
        super(Background, self).__init__(page, filename=filename, 
            id_="sect-background", menu_name="background")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        content = content.findChildren("p")
        return "".join([str(p) for p in content])


class PreparationInstructions(LessonSection):
    def __init__(self, page, filename=None):
        super(PreparationInstructions, self).__init__(page, filename=filename, 
            id_="sect-preparation", menu_name="preparation_instructions")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        content = content.findChildren("ul")
        return "".join([str(p) for p in content])


class LessonActivities(LessonSection):
    def __init__(self, page, filename=None):
        super(LessonActivities, self).__init__(page, filename=filename, 
            id_="sect-activities", menu_name="lesson_activities")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        return "".join([str(p) for p in content])


class Assessment(LessonSection):
    def __init__(self, page, filename=None):
        super(Assessment, self).__init__(page, filename=filename, 
            id_="sect-assessment", menu_name="assessment")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        return "".join([str(p) for p in content])


class ExtendingTheLesson(LessonSection):
    def __init__(self, page, filename=None):
        super(ExtendingTheLesson, self).__init__(page, filename=filename, 
            id_="sect-extending", menu_name="extending_the_lesson")

    def get_content(self):
        content = self.body.find("div", class_="text")
        remove_links(content)
        return "".join([str(p) for p in content])


class TheBasics(LessonSection):
    def __init__(self, page, filename=None):
        super(TheBasics, self).__init__(page, filename=filename, 
            id_="sect-thebasics", menu_name="the_basics")

    def get_content(self):
        remove_links(self.body)
        return str(self.body)


class Resources(object):
    def __init__(self, page, filename=None):
        self.body = page.find("div", id="sect-resources")
        self.filename = filename

    def get_img_url(self):
        resource_img = self.body.find("li", class_="lesson-image")
        img_tag = resource_img.find("img")
        return img_tag["src"]

    def get_credits(self):
        resource_img = self.body.find("li", class_="lesson-image")
        remove_links(resource_img)
        credits = "".join(map(str, resource_img.findChildren("p")))
        return credits

    def get_pdfs(self):
        resource_links = self.body.find_all("a")
        for link in resource_links:
            if link["href"].endswith(".pdf"):
                name = get_name_file(link["href"])
                yield name, urllib.parse.urljoin(BASE_URL, link["href"])

    def student_resources(self):
        resources = self.body.find("dd", id="student-resources")
        if resources is not None:
            for link in resources.find_all("a"):
                yield link["href"]

    def write_img(self, img_url, filename):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            path = zipper.write_url(img_url, filename)

    def write_index(self, content):
        with html_writer.HTMLWriter(self.filename, "w") as zipper:   
            zipper.write_index_contents(content)

    def write(self, content, img_url, filename):
        self.write_index(content)
        self.write_img(img_url, filename)      

    def to_file(self):
        img_url = self.get_img_url()
        filename = get_name_file(img_url)
        img_tag = "<img src='{}'>...".format(filename)
        html = '<html><head><meta charset="UTF-8"></head><body>{}{}</body></html>'.format(
            img_tag, self.get_credits())
        self.write(html, img_url, filename)


class LessonPlan(object):
    def __init__(self, page, lesson_filename=None, resources_filename=None):
        self.page = page
        self.title = self.clean_title(self.page.find("div", id="description"))
        self.menu = Menu(self.page, filename=lesson_filename, id_="sect-thelesson")
        self.menu.add("The Basics")
        self.sections = [
            Introduction,
            GuidingQuestions,
            LearningObjetives,
            Background,
            PreparationInstructions,
            LessonActivities,
            Assessment,
            ExtendingTheLesson,
            TheBasics
        ]
        self.resources = Resources(self.page, filename=resources_filename)
        self.source = None

    def clean_title(self, title):
        import re
        if title is not None:
            title = title.text.strip()
            title = re.sub("\n|\t", " ", title)
            title = re.sub(" +", " ", title)
        return title

    def to_file(self, PATH, levels):
        LOGGER.info(" + Lesson:"+ self.title)
        self.menu.to_file()
        for Section in self.sections:
            section = Section(self.page, filename=self.menu.filename)
            section.to_file(self.menu.get(section.menu_name))
        self.resources.to_file()
        metadata_dict = {"description": "", 
            "language": "en", 
            "license": licenses.CC_BY, 
            "copyright_holder": "National Endowment for the Humanities", 
            "author": "", 
            "source_id": self.source}

        levels.append(self.title)
        PATH.set(*levels)
        writer.add_file(str(PATH), "THE LESSON", self.menu.filename, **metadata_dict)
        writer.add_folder(str(PATH), "RESOURCES", **metadata_dict)
        PATH.set(*(levels+["RESOURCES"]))
        for name, pdf_url in self.resources.get_pdfs():
            meta = metadata_dict.copy()
            meta["source_id"] = pdf_url
            writer.add_file(str(PATH), name.replace(".pdf", ""), pdf_url, **meta)
        writer.add_file(str(PATH), "MEDIA", self.resources.filename, **metadata_dict)
        #resource.student_resources() external web page
        PATH.go_to_parent_folder()
        PATH.go_to_parent_folder()

    def rm(self):
        pass
        #os.remove(pathname)


class StudentResourceIndex(object):
    def __init__(self, page, filename=None, levels=None):
        self.body = page
        self.filename = filename
        self.title = None
        self.levels = levels

    def get_img_url(self):
        resource_img = self.body.find("div", class_="image")
        if resource_img is not None:
            img_tag = resource_img.find("img")
            if img_tag is not None:
                return img_tag["src"]

    def get_credits(self):
        credits = self.body.find("div", class_="caption")
        credits_elems = credits.find_all("div")
        type_ = credits_elems[0]
        LOGGER.info(type_.text)
        source = credits_elems[1]
        return "<div>{}</div><div>{}</div>".format(type_, source.text)

    def get_viewmore(self):
        view_more = self.body.find(lambda tag: tag.name == "a" and\
                                    tag.findParent("div", class_="more"))
        return view_more["href"]

    def get_content(self):
        content = self.body.find("div", id="description")
        self.title = content.find("h2")
        created = content.find("div", class_="created")
        self.description = content.find("p")
        return "".join(map(str, [self.title, created, self.description]))

    #def write_img(self, img_url, filename):
    #    with html_writer.HTMLWriter(self.filename, "a") as zipper:
    #        path = zipper.write_url(img_url, filename)

    #def write_index(self, content):
    #    with html_writer.HTMLWriter(self.filename, "w") as zipper:   
    #        zipper.write_index_contents(content)

    def write(self, content, img_url, filename):
        self.write_index(content)
        if img_url is not None:
            self.write_img(img_url, filename)      

    def to_file(self):
        img_url = self.get_img_url()
        #if img_url is not None:
        #    filename_img = get_name_file(img_url)
        #    img_tag = "<img src='{}'>...".format(filename_img)
        #else:
        #    img_tag = ""
        #    filename_img = ""

        content = self.get_content()
        #html = "<html><body>{}{}{}</body></html>".format(content, img_tag, self.get_credits())
        #self.write(html, img_url, filename_img)
        resource_checker = ResourceChecker(self.get_viewmore())
        resource = resource_checker.check()
        description = "" if self.description is None else self.description.text
        levels = self.levels + [self.title.text]
        metadata_dict = resource.to_file(description, self.filename)
        if metadata_dict is not None:
            PATH.set(*levels)
            if img_url is not None:
                metadata_dict["thumbnail"] = str(PATH)+"/RESOURCES/"+get_name_file_no_ext(img_url)
            writer.add_file(str(PATH), "THE LESSON", self.filename, **metadata_dict)
            if resource.resources_files is not None:
                writer.add_folder(str(PATH), "RESOURCES", **metadata_dict)
                PATH.set(*(levels+["RESOURCES"]))
                if img_url is not None:
                    writer.add_file(str(PATH), get_name_file_no_ext(img_url), img_url, **metadata_dict)
                for file_src, file_metadata in resource.resources_files:
                    try:
                        meta = file_metadata if len(file_metadata) > 0 else metadata_dict
                        writer.add_file(str(PATH), get_name_file_no_ext(file_src), file_src, **meta)
                    except requests.exceptions.HTTPError as e:
                        LOGGER.info("Error: {}".format(e))
                PATH.go_to_parent_folder()
            PATH.go_to_parent_folder()


class ResourceChecker(object):
    def __init__(self, resource_url):
        LOGGER.info("Resource url:"+resource_url)
        self.resource_url = resource_url

    def has_file(self):
        files = [(self.resource_url.endswith(filetype), filetype) 
                for filetype in ["pdf", "mp4", "mp3", "swf", "jpg"]]
        file_ = list(filter(lambda x: x[0], files))
        if len(file_) > 0:
            return file_[0][1]
        else:
            return None

    def check(self):
        file_ = self.has_file()
        #edsitement has resources on 208.254.21.241 but is not reachable
        if self.resource_url.find(BASE_URL) != -1 and file_ is None:
            return WebPageSource(self.resource_url)
        elif self.resource_url.find(BASE_URL) != -1 and file_ is not None and\
            file_ != "swf" and file_ != "jpg":
            return FileSource(self.resource_url)
        elif self.resource_url.find(BASE_URL) != -1 and file_ == "jpg":
            return ImageSource(self.resource_url)
        elif self.resource_url.find("interactives.mped.org") != -1:
            return ResourceType("interactives") #response error
        elif file_ == "swf":
            return ResourceType("flash")
        elif self.resource_url.find("youtu.be") != -1 or self.resource_url.find("youtube.com") != -1:
            return YouTubeResource(self.resource_url)
        else:
            return ResourceType("unknown")


class ResourceType(object):
    def __init__(self, type_name=None):
        LOGGER.info("Resource Type: "+type_name)
        self.type_name = type_name
        self.resources_files = None

    def to_file(self, description, filename):
        pass

    def add_resources_files(self, src, metadata, local=False):
        if self.resources_files is None:
            self.resources_files  = []
        if local is True:
            self.resources_files.append((src, metadata))
        else:
            self.resources_files.append((urllib.parse.urljoin(BASE_URL, src), metadata))


class FileSource(ResourceType):
    def __init__(self, resource_url, type_name="File"):
        super(FileSource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def to_file(self, description, filename):
        metadata_dict = {"description": description, 
            "language": "en", 
            "license": licenses.CC_BY, 
            "copyright_holder": "National Endowment for the Humanities", 
            "author": "", 
            "source_id": self.resource_url}
        self.resources_files = [self.resource_url]
        return metadata_dict


class ImageSource(ResourceType):
    def __init__(self, resource_url, type_name="Image"):
        super(ImageSource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def write(self, content, filepath, img_filename):
        self.write_index(content, filepath)
        self.write_img(self.resource_url, filepath, img_filename)

    def write_index(self, content, filepath):
        with html_writer.HTMLWriter(filepath, "w") as zipper: 
            zipper.write_index_contents(content)

    def write_img(self, img_url, filepath, img_filename):
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            path = zipper.write_url(img_url, img_filename)

    def to_file(self, description, filepath):
        metadata_dict = {"description": description, 
            "language": "en", 
            "license": licenses.CC_BY, 
            "copyright_holder": "National Endowment for the Humanities", 
            "author": "", 
            "source_id": self.resource_url}
        img_filename = get_name_file(self.resource_url)
        img_tag = "<img src='{}'>...".format(img_filename)
        html = "<html><body>{}</body></html>".format(img_tag)
        self.write(html, filepath, img_filename)
        return metadata_dict


class WebPageSource(ResourceType):
    def __init__(self, resource_url, type_name="Web Page"):
        super(WebPageSource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def write(self, content, filepath):
        self.write_index(content, filepath)

    def write_index(self, content, filepath):
        with html_writer.HTMLWriter(filepath, "w") as zipper:   
            zipper.write_index_contents(content)

    def to_file(self, description, filepath):
        metadata_dict = {"description": description, 
            "language": "en", 
            "license": licenses.CC_BY, 
            "copyright_holder": "National Endowment for the Humanities", 
            "author": "", 
            "source_id": self.resource_url}
        try:
            page_contents = downloader.read(self.resource_url)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
            return None
        else:        
            page = BeautifulSoup(page_contents, 'html.parser')
            content = page.find("div", id="content")
            files = self.remove_external_links(content)
            images = self.find_local_images(content)
            for file_ in files:
                metadata_files = metadata_dict.copy()
                metadata_files["source_id"] = file_
                self.add_resources_files(file_, metadata_files)
            #for img in images:
            #    self.add_resources_files(img)
            self.write('<html><body><head><meta charset="UTF-8"></head>'+\
                        str(content)+'</body><html>', filepath)
            return metadata_dict

    def remove_external_links(self, content):
        files = []
        for link in content.find_all("a"):
            href = link.get("href", "")
            if href.find(BASE_URL) != -1 or href.startswith("#") or\
                href.startswith("/") or href == "":
                if href.endswith("pdf"):
                    files.append(href)
            link.replaceWithChildren()
        return files

    def find_local_images(self, content):
        images = []
        for img_tag in content.find_all("img"):
            src = img_tag.get("src", "")
            if src.startswith("/") or src.find(BASE_URL) != -1:
                images.append(src)
            img_tag.replaceWithChildren()
        return images


class YouTubeResource(ResourceType):
    def __init__(self, resource_url, type_name="Youtube"):
        super(YouTubeResource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def process_file(self, url, download=False):
        import youtube_dl
        from ricecooker.classes.files import download_from_web, config

        ydl_options = {
            #'outtmpl': '%(title)s-%(id)s.%(ext)s',
            #'format': 'bestaudio/best',
            'no_warnings': True,
            'continuedl': True,
            'restrictfilenames':True,
            'quiet': False,
        }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(url, download=False)
                if info["license"] == "Standard YouTube License" and download is True:
                    filename = download_from_web(url, ydl_options, ext=".{}".format(file_formats.MP4))
                    filepath = config.get_storage_path(filename)
                    self.add_resources_files(filepath, {}, local=True)
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,         
                    youtube_dl.utils.ExtractorError) as e:
                print('error_occured ' + str(e))

    def to_file(self, description, filename):
        metadata_dict = {"description": description, 
            "language": "en", 
            "license": licenses.CC_BY, 
            "copyright_holder": "National Endowment for the Humanities", 
            "author": "", 
            "source_id": self.resource_url}
        self.process_file(self.resource_url, download=DOWNLOAD_VIDEOS)
        return metadata_dict


# CLI: This code will run when the sous chef is called from the command line
################################################################################
if __name__ == '__main__':

    # Open a writer to generate files
    with data_writer.DataWriter(write_to_path=WRITE_TO_PATH) as writer:

        # Write channel details to spreadsheet
        thumbnail = writer.add_file(str(PATH), "Channel Thumbnail", CHANNEL_THUMBNAIL, write_data=False)
        writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION, thumbnail=thumbnail)

        # Scrape source content
        scrape_source(writer)

        sys.stdout.write("\n\nDONE: Zip created at {}\n".format(writer.write_to_path))
