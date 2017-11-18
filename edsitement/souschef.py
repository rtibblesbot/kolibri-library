#!/usr/bin/env python
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

# Additional Constants
################################################################################

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

BASE_URL = "http://edsitement.neh.gov"


# Main Scraping Method
################################################################################
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
        Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
        Returns: None
    """
    
    LESSONS_PLANS_URL = urllib.parse.urljoin(BASE_URL, "lesson-plans")
    page_contents = downloader.read(LESSONS_PLANS_URL)
    LOGGER.info("Scrapping: " + LESSONS_PLANS_URL)
    page = BeautifulSoup(page_contents, 'html.parser')

    for lesson_plan_url, levels in lesson_plans(lesson_plans_subject(page)):
        subtopic_name = lesson_plan_url.split("/")[-1]
        page_contents = downloader.read(lesson_plan_url, loadjs=False)
        page = BeautifulSoup(page_contents, 'html5lib')
        lesson_plan = LessonPlan(page, 
            lesson_filename="/tmp/lesson-"+subtopic_name+".zip",
            resources_filename="/tmp/resources-"+subtopic_name+".zip")
        lesson_plan.source = lesson_plan_url
        lesson_plan.to_file(PATH, levels)
        print(levels)


# Helper Methods
################################################################################
def lesson_plans_subject(page):
    lessons_nodes = [25, 21, 22, 23, 18319, 18373, 25041, 31471]
    for node in lessons_nodes:
        page_h3 = page.find("h3", id="node-"+str(node))
        resource_a = page_h3.find("a", href=True)
        subtopic_url = urllib.parse.urljoin(BASE_URL, resource_a["href"].strip())
        yield subtopic_url, ["Lesson Plans or For Teachers"]

def lesson_plans(lesson_plans_subject):
    for lesson_url, levels in itertools.islice(lesson_plans_subject, 0, 4):
        page_contents = downloader.read(lesson_url)
        page = BeautifulSoup(page_contents, 'html.parser')
        sub_lessons = page.find_all("div", class_="lesson-plan-link")
        title = page.find("h2", class_="subject-area").text
        LOGGER.info("Subject Title:"+title)
        LOGGER.info("Subject url:"+lesson_url)
        for sub_lesson in itertools.islice(sub_lessons, 0, 2):
            resource_a = sub_lesson.find("a", href=True)
            resource_url = resource_a["href"].strip()
            time.sleep(.8)
            yield urllib.parse.urljoin(BASE_URL, resource_url), levels + [title]


class Menu(object):
    def __init__(self, page, filename=None, id_=None):
        self.body = page.find("div", id=id_)
        self.menu = OrderedDict()
        self.filename = filename
        self.menu_titles(self.body.find_all("h4"))

    def write(self, content):
        with html_writer.HTMLWriter(self.filename) as zipper:
            zipper.write_index_contents(content)

    def to_file(self):
        self.write("<html><body><ul>"+self.to_html()+"</ul></body></html>")

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
            '<li><a href="{filename}">{text}</a></li>'.format(**e) for e in self.menu.values())


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
            zipper.write_contents(filename, content)

    def to_file(self, filename):
        if self.body is not None and filename is not None:
            if self.title:
                self.write(filename, "<html><body>"+self.title+""+self.get_content()+"<body></html>")
            else:
                self.write(filename, "<html><body>"+self.get_content()+"<body></html>")


class Introduction(LessonSection):
    def __init__(self, page, filename=None):
        super(Introduction, self).__init__(page, filename=filename, 
            id_="sect-introduction", menu_name="introduction")

    def get_content(self):
        content = self.body.find("div", class_="text").findChildren("p")
        return "".join([str(p) for p in content])


class GuidingQuestions(LessonSection):
    def __init__(self, page, filename=None):
        super(GuidingQuestions, self).__init__(page, filename=filename, 
            id_="sect-questions", menu_name="guiding_questions")

    def get_content(self):
        content = self.body.find("div", class_="text").findChildren("ul")
        return "".join([str(p) for p in content])


class LearningObjetives(LessonSection):
    def __init__(self, page, filename=None):
        super(LearningObjetives, self).__init__(page, filename=filename, 
            id_="sect-objectives", menu_name="learning_objectives")

    def get_content(self):
        content = self.body.find("div", class_="text").findChildren("ul")
        return "".join([str(p) for p in content])


class PreparationInstructions(LessonSection):
    def __init__(self, page, filename=None):
        super(PreparationInstructions, self).__init__(page, filename=filename, 
            id_="sect-preparation", menu_name="preparation_instructions")

    def get_content(self):
        content = self.body.find("div", class_="text").findChildren("ul")
        return "".join([str(p) for p in content])


class LessonActivities(LessonSection):
    def __init__(self, page, filename=None):
        super(LessonActivities, self).__init__(page, filename=filename, 
            id_="sect-activities", menu_name="lesson_activities")

    def get_content(self):
        content = self.body.find("div", class_="text")
        return "".join([str(p) for p in content])


class Assessment(LessonSection):
    def __init__(self, page, filename=None):
        super(Assessment, self).__init__(page, filename=filename, 
            id_="sect-assessment", menu_name="assessment")

    def get_content(self):
        content = self.body.find("div", class_="text")
        return "".join([str(p) for p in content])


class TheBasics(LessonSection):
    def __init__(self, page, filename=None):
        super(TheBasics, self).__init__(page, filename=filename, 
            id_="sect-thebasics", menu_name="the_basics")

    def get_content(self):
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
        credits = "".join(map(str, resource_img.findChildren("p")))
        return credits

    def get_pdfs(self):
        resource_links = self.body.find_all("a")
        for link in resource_links:
            if link["href"].endswith(".pdf"):
                name = self.get_name_file(link["href"])
                yield name, urllib.parse.urljoin(BASE_URL, link["href"])

    def student_resources(self):
        resources = self.body.find("dd", id="student-resources")
        if resources is not None:
            for link in resources.find_all("a"):
                yield link["href"]

    def get_name_file(self, img_url):
        from urllib.parse import urlparse
        import os
        return os.path.basename(urlparse(img_url).path)

    def write_img(self, img_url, filename):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            path = zipper.write_url(img_url, filename)

    def write_index(self, content):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:   
            zipper.write_index_contents(content)

    def write(self, content, img_url, filename):
        self.write_index(content)
        self.write_img(img_url, filename)      

    def to_file(self):
        img_url = self.get_img_url()
        filename = self.get_name_file(img_url)
        img_tag = "<img src='{}'>...".format(filename)
        html = "<html><body>{}{}</body></html>".format(img_tag, self.get_credits())
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
            PreparationInstructions,
            LessonActivities,
            Assessment,
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
            "license": "CC BY 4.0", 
            "copyright_holder": "National Endowment for the Humanities", 
            "author": "", 
            "source_id": self.source}

        levels.append(self.title)
        PATH.set(*levels)
        writer.add_file(str(PATH), "THE LESSON", self.menu.filename, **metadata_dict)
        writer.add_folder(str(PATH), "RESOURCES", **metadata_dict)
        PATH.set(*(levels+["RESOURCES"]))
        for name, pdf_url in self.resources.get_pdfs():
            writer.add_file(str(PATH), name.replace(".pdf", ""), pdf_url, **metadata_dict)
        writer.add_file(str(PATH), "MEDIA", self.resources.filename, **metadata_dict)
        #resource.student_resources() external web page
        PATH.go_to_parent_folder()
        PATH.go_to_parent_folder()

    def rm(self):
        pass
        #os.remove(pathname)


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
