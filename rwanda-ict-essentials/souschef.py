#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports

from selenium import webdriver
from utils import data_writer, path_builder, downloader, slugify
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages

# Additional imports 
###########################################################
from utils.downloader import read
from utils.html import HTMLWriter
from bs4 import BeautifulSoup
import re

from utils.slugify import slugify
import youtube_dl

# Run Constants
###########################################################

CHANNEL_NAME = "RME ICT Essentials for Teachers"              # Name of channel
CHANNEL_SOURCE_ID = "rme-ict-essentials"      # Channel's unique id
CHANNEL_DOMAIN = "content@learningequality.org"					# Who is providing the content
CHANNEL_LANGUAGE = "en"		# Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
PATH = path_builder.PathBuilder(channel_name=CHANNEL_NAME)  # Keeps track of path to write to csv
WRITE_TO_PATH = "{}{}{}.zip".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, CHANNEL_NAME) # Where to generate zip file


# Additional Constants 
###########################################################
BASE_URL = "http://elearning.reb.rw/course/index.php?categoryid=14"

chromedriver = "/Users/thot/Downloads/chromedriver"
os.environ["webdriver.chrome.driver"] = chromedriver
driver = webdriver.Chrome(chromedriver)

UNIT_BLACKLIST = [ "Unit 00 - Orientation" ]
# Main Scraping Method 
###########################################################
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
        Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
        Returns: None
    """
    content = read(BASE_URL, loadjs = True, driver = driver ) 

    soup = BeautifulSoup(content, 'html.parser')
    units = [unit for unit in get_units_from_site(soup) if not blacklisted_unit(unit['name'])]
    for u in units:
        print(u['name']) 
        #parse_unit(writer, u['name'], u['link'])
    # TODO: Replace line with scraping code
    raise NotImplementedError("Scraping method not implemented")

# Helper Methods 
###########################################################

# Unit-related functions
##########################

def get_units_from_site(page):
    """ 
      Get all the unit names and links from the main page
    """
    units = []
    for div in page.find("div", id="region-main").find_all("div", class_= "coursename"):
        link = div.find("a", text = re.compile("Unit"))
        if link:
            units.append({ 'name': link.get_text(), 'link': link.get('href')})
    return units

def parse_unit(writer, name, link):
    """ 
      Parse the elements inside a unit
      Extract sections, and each section would be an independent HTML5App
    """
    content = read(link, loadjs = True, driver = driver)
    page = BeautifulSoup(content, 'html.parser')
    PATH.open_folder(folder_name(name))

    sections = page.find_all('li', id = re.compile('section-')) 
    writer.add_folder(str(PATH), name, "", "TODO: Generate Description")
    for section in sections:
        print(extract_title(section))
        section_type = clasify_block(section) 
        if section_type == 'html':
            add_html5app(writer, section)
        elif section_type == 'video': 
            add_video(writer, section)
    PATH.go_to_parent_folder()
    return 0

def blacklisted_unit(unit_title):
    for blacklisted in UNIT_BLACKLIST:
        if re.search(blacklisted, unit_title):
            return True 
    return False 

# Generating HTML5 app
##########################

def add_video(writer, section):
     title = extract_title(section)
     video = section.find("iframe", src=re.compile("youtube"))
     video_filename = download_video(video.get('src'))
     if video_filename:
         writer.add_file(str(PATH), title, str("./") + str(video_filename), license="TODO", copyright_holder = "TODO")

def add_html5app(writer, section):
     title = extract_title(section)
     filename = generate_html5app_from_section(section)
     print_modules(section)
     writer.add_file(str(PATH), html5app_filename(title), html5app_path_from_title(title), license="TODO", copyright_holder = "TODO")
     os.remove(html5app_path_from_title(title))


def generate_html5app_from_section(section):
    title = extract_title(section)
    print("\t" + str(title) + " (" + section.get('id') + ")")
    filename = html5app_path_from_title(title)
    with HTMLWriter(filename) as html5zip:
        content = section.encode_contents
        html5zip.write_index_contents("<html><head></head><body>{}</body></html>".format(content))   
    return filename 

def extract_title(section):
    page_title = section.find("h3", class_="sectionname")
    title = "no title"
    if page_title:
        title = page_title.get_text()
    return title 


def html5app_filename(title):
    return "{}.zip".format(slugify(title))

def html5app_path_from_title(title):
    return "./{}".format(html5app_filename)

def folder_name(unit_name):
    """ 
    Extract folder name from full unit name

    Example:
    Unit 01 - Example unit

    returns:
    Unit 01 
    """
    return re.search('(.+?) - .*', unit_name).group(1)

def print_modules(section):
    img = section.find("img", src=re.compile("[Cc]lock"))
    if img:
        print(get_recommended_time(img)) 
    return 0 

def clasify_block(module):
    module_type = "html"
    video = module.find("iframe", src=re.compile("youtube"))
    if video:
        module_type = "video"
    return module_type

def real_title(title):
    filename = title.get("src").split("/")[-1]
    return IMG_LOOKUP[filename]

def get_recommended_time(title):
    if title.parent.get_text():
        return title.parent.get_text().strip
    else:
        return title.parent.parent.get_text().strip

def is_valid_title(title):
    """
    is_valid_title is true if the name of the image contains Unit or Section on it 
    but not contains Quote 
    or Method1 or Method2 
    (because they are extra images on the section)
    """
    pattern1 = re.compile("Unit|Section", re.IGNORECASE)
    pattern2 = re.compile("^.*Quote.*$", re.IGNORECASE)
    pattern3 = re.compile("^.*Method[1|2].*$", re.IGNORECASE)
    filename = title.get("src").split("/")[-1]
    return (pattern1.match(filename) and (not pattern2.match(filename) and (not pattern3.match(filename))))

def download_video(url):
    print(url)
    ydl_options = {
            'outtmpl': '%(title)s-%(id)s.%(ext)s',
            'continuedl': True,
            # 'quiet' : True,
            'restrictfilenames':True, 
            }
    video_filename = ""
    with youtube_dl.YoutubeDL(ydl_options) as ydl:
        try:
            ydl.add_default_info_extractors()
            info = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info)
        except (youtube_dl.utils.DownloadError,youtube_dl.utils.ContentTooShortError,youtube_dl.utils.ExtractorError) as e:
            return "" 
    return video_filename 



""" This code will run when the sous chef is called from the command line. """
if __name__ == '__main__':

    # Open a writer to generate files
    with data_writer.DataWriter(write_to_path=WRITE_TO_PATH) as writer:

        # Write channel details to spreadsheet
        thumbnail = writer.add_file(str(PATH), "Channel Thumbnail", CHANNEL_THUMBNAIL, write_data=False)
        writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION, thumbnail=thumbnail)

        # Scrape source content
        scrape_source(writer)

        sys.stdout.write("\n\nDONE: Zip created at {}\n".format(writer.write_to_path))

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
