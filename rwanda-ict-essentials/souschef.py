#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from utils import data_writer, path_builder, downloader
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages


# Additional imports 
###########################################################
from utils.downloader import read
from bs4 import BeautifulSoup
import re

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
BASE_URL = "https://ict-essentials-for-teachers.moodlecloud.com/"

# Main Scraping Method 
###########################################################
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
        Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
        Returns: None
    """
    content = read(BASE_URL) 

    soup = BeautifulSoup(content, 'html.parser')
    units = get_units_from_site(soup)
    for u in units:
       print(u['name'])  
       parse_unit(u['name'], u['link'])
    # TODO: Replace line with scraping code
    raise NotImplementedError("Scraping method not implemented")


def get_units_from_site(page):
    """ 
      Get all the unit names and links from the main page
    """
    units = []
    for div in page.find_all("div", class_= "coursename"):
        link = div.find("a", text = re.compile("Unit"))
        if link:
            units.append({ 'name': link.get_text(), 'link': link.get('href')})
    return units

def parse_unit(name, link):
    content = read(link) 
    page = BeautifulSoup(content, 'html.parser')
    sections = page.find_all('li', id = re.compile('section-')) 
    for section in sections:
        print(section.get('id'))
    return 0

# Helper Methods 
###########################################################


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
