#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from utils import data_writer, path_builder # , downloader -- we no longer use downloader due to session issues
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages
import requests
from ricecooker.classes.nodes import TopicNode
from ricecooker.chefs import SushiChef

""" Additional imports """
###########################################################
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import ricecooker

""" Run Constants"""
###########################################################

CHANNEL_NAME = "Illustrative Mathematics"		# Name of channel
CHANNEL_SOURCE_ID = "openupresources"			# Channel's unique id
# TODO: what is CHANNEL_DOMAIN?
CHANNEL_DOMAIN = "content@learningequality.org"		# Who is providing the content
CHANNEL_LANGUAGE = "en"					# Language of channel
CHANNEL_DESCRIPTION = "Grade 6-8 Math: A problem-based core program that sparks unparalleled levels of student engagement."  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
PATH = path_builder.PathBuilder(channel_name=CHANNEL_NAME)  # Keeps track of path to write to csv
WRITE_TO_PATH = "{}{}{}.zip".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, CHANNEL_NAME) # Where to generate zip file
USERNAME = "Set Environment Variable 'USERNAME' first"      # or just change this if you're not running on the command line...
PASSWORD = "Set Environment Variable 'PASSWORD' first"      # or just change this if you're not running on the command line...
session = requests.Session()                            # I wanted to use downloader.DOWNLOAD_SESSION, but that doesn't work...

""" Additional Constants """
###########################################################

# only add keys we actively care about
"""METADATA_KEYS = ['content_id', 'author', 'lang_id', 'license', 'copyright_holder']
LICENSE_LOOKUP = {"CC BY-NC-SA": licenses.CC_BY_NC_SA,
                  "CC BY-NC": licenses.CC_BY_NC,
                  "CC BY": licenses.CC_BY,
                  "Public Domain": licenses.PUBLIC_DOMAIN
                  }	
""" # TODO - remove if unused
# Set up logging tools
LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

# License to be used for content under channel
CHANNEL_LICENSE = licenses.CC_BY_NC_SA  

""" Main Scraping Method """
###########################################################
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
    Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
    Returns: None
    """
    def login():
        # Handle Login
        sign_in_url = "https://auth.openupresources.org/users/sign_in"
    
        # get sign-in page
        bs = BeautifulSoup(session.get(sign_in_url).text, 'html.parser')
        form = bs.find("form")
        inputs = form.find_all("input")
    
        data = {}
        # what we actually care about here is the auth-token.
        for i in inputs:
            data[i.attrs['name']] = i.attrs.get('value')
            data['user[email]'] = USERNAME
        data['user[password'] = PASSWORD
    
        posted_response = session.post(sign_in_url, data=data)
        assert "Signed in successfully" in posted_response.text
            
        # this step is apparently absolutely critical -- click the big button on the success page!
        session.get("https://auth.openupresources.org/register/materials")
    
        # check it's all OK.
        test_response = session.get("https://im.openupresources.org/7/teachers/5.html")
    
        assert "sign up as an educator" not in test_response.text
        assert "Rational Number" in test_response.text

    login()
    print ("Login successful")
    
    
    BASE_URL = 'https://im.openupresources.org/{year}/{target}'
    BASE_URLS = []
    for target in ['teachers', 'students', 'families']:
        for year in [6, 7, 8]:
            BASE_URLS.append(BASE_URL.format(year=year, target=target))
            
    units = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    
    """6/teachers/1.html -- has description of this topic; has drop down list of lessons within it 
    6/teachers/1/1.html -- Is a lesson plan.
    6/teachers/1/assessments/unit_assessments.html -- broken
    6/teachers/1/practice_problems.html -- practice problems for all lessons w/solutons
    6/teachers/1/downloads.html -- 7x links to pdfs/zips of pdfs
    6/teachers/1/family_materials.html -- same as family? (YES) topicwide
    6/teachers/teacher_course_guide.html -- single page per year
    
    6/families/1.html -- same as teachers / family materials
    
    6/students/1/1.html -- is student resources.
    6/students/1/practice_problems.html - nothing complex
    6/students/glossary.html - nothing complex
    6/students/1/my_reflections.html - nothing complex    """
            
    for url in BASE_URLS:
        pass
    
""" Main Class """

class OpenUpChef(ricecooker.chefs.SushiChef):
    """channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'im.openupresources.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'im_openupresources',         # channel's unique id
        'CHANNEL_TITLE': 'Illustrative Mathematics',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'Grade 6-8 Math: A problem-based core program that sparks unparalleled levels of student engagement.',  # (optional) description of the channel (optional)
    }"""
    
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'example.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'dragon_example',         # channel's unique id
        'CHANNEL_TITLE': 'Dragon Test',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
    }
        
    def construct_channel(self, **kwargs):
        # create channel
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        potato_topic = nodes.TopicNode(source_id="<potatos_id>", title="Potatoes!")
        channel.add_child(potato_topic)
        return channel    
    
    #def run(): # args, options
    #    pass
    
    #def main():
    #    pass
    
def make_channel():
    mychef = OpenUpChef()
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    mychef.run(args, options)
    
make_channel()
exit()
    
    

""" Helper Methods """
###########################################################

def old_read_source(url):
    """ Read page source as beautiful soup """
    html = session.get(url).text
    return BeautifulSoup(html, 'html.parser')

def old_handle_page_and_subpages(url, parent_path):
    """Create CSV and ZIP for this URL and its descendants.
    parent_path is the name of the path in the ZIP file for this URL.
    Returns nothing."""

    metadata, content, children = handle_page(url)

    # should we only do this if we have children? Not sure...
    LOGGER.info("Adding folder {}:{} ({})".format(parent_path, metadata.get('content_id'), metadata['title']))

    if not metadata.get('content_id'):
        print ("No content_id for url")

    if True:
        writer.add_folder(path = parent_path,
                          title = metadata['title'],
                                  source_id = metadata.get('content_id'),
                                  language = metadata.get('lang_id'),
                                  description = metadata.get('description'),
                                  )	

    for content_item in content:
        writer.add_file(path = parent_path,
                        title = metadata['title'],
                                download_url = content_item,
                                author = metadata.get('author'),
                                source_id = metadata.get('content_id'),
                                description = metadata.get('description'), 
                                language = metadata.get('lang_id'),
                                license=LICENSE_LOOKUP[metadata['license']],
                                copyright_holder = metadata['copyright_holder'])

    for child in children: # recurse
        LOGGER.debug("Processing {}".format(child['url']))
        child_path = '/'.join([parent_path.rstrip('/'),child['machine_name'].rstrip('/')])
        handle_page_and_subpages(child['url'], child_path)


def old_handle_page(url):
    """
    Takes a url and returns a list of three things:
        * metadata: a dictionary of strings (see METADATA_KEYS)
        * content: a list of URLs to content (e.g. video files)
        * children: a dictionary of the 'name' and fully-qualified 'url' of sub-resources, along with a short 'machine_name'

    Perhaps this should be three separate functions, instead.
    """
    def absolute_url(url_fragment):
        """Takes a URL fragment, and returns a full URL"""
        return urljoin(url, url_fragment)

    def no_brackets(text):
        """Gets rid of one set of bracketted text (like this)"""
        lbracket = text.index("(")
        rbracket = text.index(")")
        if lbracket == -1 or rbracket == -1: return text
        if lbracket > rbracket: return text
        return (text[:lbracket] + text[rbracket+1:]).rstrip()

    page = read_source(url)
    maincontent = page.find('div', {'class': 'maincontent'}) 

    children = []
    children_bs = maincontent.find_all('li', {'class': lambda x: x.endswith('-kind')})  # topic-kind, audio-kind, etc.
    for child in children_bs:
        child_url=child.find('a')['href']
        children.append({ "url": absolute_url(child_url),
                          "machine_name": child_url,
                                  "name": no_brackets(child.get_text().strip()) })

    metadata = {}
    metadata_bs = maincontent.find('ul', {'class': 'metadata'})
    for key in METADATA_KEYS:
        item = metadata_bs.find("li", {'class': key})
        try:
            value = item.find("span", {'class': 'keyvalue'})
        except:
            LOGGER.debug("No {} found for {}".format(key, url))
            continue

        metadata[key] = value.get_text().strip()

    metadata['title'] = maincontent.find("h3").get_text().strip()
    metadata['description'] = maincontent.find("p", {'class': 'descr'}).get_text().strip()

    content = []
    tags_with_src = maincontent.find_all("", {'src': lambda x: x}) # there is a src tag
    for tag in tags_with_src:
        content.append(absolute_url(tag['src']))

    return (metadata, content, children)


""" This code will run when the sous chef is called from the command line. """
if __name__ == '__main__':
    
    print ("__main__")
    PASSWORD = os.environ['PASSWORD']
    USERNAME = os.environ['USERNAME']
    KOLIBRI_TOKEN = os.environ['KOLIBRI_STUDIO_TOKEN']   # token=KOLIBRI_TOKEN in call to upload channel
    
    # Open a writer to generate files
    with data_writer.DataWriter(write_to_path=WRITE_TO_PATH) as writer:

        # Write channel details to spreadsheet
        thumbnail = writer.add_file(str(PATH), "Channel Thumbnail", CHANNEL_THUMBNAIL, write_data=False)
        writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION, thumbnail=thumbnail)

        # Scrape source content
        scrape_source(writer)

        sys.stdout.write("\n\nDONE: Zip created at {}\n".format(writer.write_to_path))
