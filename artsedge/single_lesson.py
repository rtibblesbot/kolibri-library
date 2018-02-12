import requests
import re

from bs4 import BeautifulSoup

def handle_lesson(url):
    response = requests.get("https://artsedge.kennedy-center.org/educators/lessons/grade-3-4/Exploring_Irish_Dance")
    soup = BeautifulSoup(response.content, "html5lib")

    pattern = " dataSrc: '([^']*)',"
    xml_url = "https://artsedge.kennedy-center.org" + re.search(pattern, response.text).group(1)
    xml_response = requests.get(xml_url)
    handle_xml(xml_response.content)

    

with open("carousel.xml") as f:
    xml_string = f.read()
    
def handle_xml(xml_string):
    
    """
    lesson: has a tag 'label' like OVERVIEW, APPLY, ASSESS
    contains
        module: with attrib 'type' [website/video/text/photo/overview/interactive/gallery/audio]
        [1 interactive; a dozen or so of video/text/photo/audio/gallery]
                -- 
                which has its own labels, Character Map, etc.
                
                photo: <image><src>(url) ... has credits
                website: <link><href>(url)
                video: <download><href> or <resource><href>
                ???: <resource>
                
                image | resource | download mutually exclusive
                media, (details + call to action), link optional and unique
                
                image: src
                download, link: label, href
                media: image, more critically src, chapters, subtitles, etc. empty....
                
                tabs: rare (~6 total, appear to be image captions) IGNORE.
    
    """
    # proper XML handling requires 'lxml' to be installed [pip install lxml]
    
    soup = BeautifulSoup(xml_string, "xml")
    lessons = soup.find_all("lesson")
    for lesson in lessons:
        modules = lesson.find_all("module")
        for module in modules:
            print (module.attrs['type'])
            module_tags = []
            for tag in ['image', 'resource', 'download', 'link', 'media']:
                module_tags.extend(module.find_all(tag, recursive=False))
            for tag in module_tags:
                src = tag.find("src", recursive=False)
                href = tag.find("href", recursive=False)
                if src:
                    print ("  ", src.text)
                if href:
                    print ("  ", href.text)
                assert not (src and href)
                    
    
handle_xml(xml_string)