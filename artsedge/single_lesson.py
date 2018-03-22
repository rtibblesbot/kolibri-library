import requests
import re
from urllib.parse import urljoin
import add_file
import build_carousel

from bs4 import BeautifulSoup

def absolute_link(url):
    return urljoin("https://artsedge.kennedy-center.org/", url)

def handle_lesson(url="https://artsedge.kennedy-center.org/educators/lessons/grade-3-4/Exploring_Irish_Dance"):
    response = requests.get(url)
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
        lesson_label = lesson.find("label").text
        modules = lesson.find_all("module")
        for module in modules:
            module_type = module.attrs['type']
            module_text = module.find("label").text
            urls = []
            module_tags = []
            if module_type in ["gallery", "photo"]:
                module_tags.extend(module.find_all("image", recursive=False))
            for tag in ['resource', 'download', 'link', 'media']:
                module_tags.extend(module.find_all(tag, recursive=False))
            for tag in module_tags:
                src = tag.find("src", recursive=False)
                href = tag.find("href", recursive=False)
                if src:
                    #print ("  ", src.text)
                    if src.text.strip():
                        urls.append(absolute_link(src.text.strip()))
                if href:
                    #print ("  ", href.text)
                    if href.text.strip():
                        urls.append(absolute_link(href.text.strip()))
                assert not (src and href)
            if urls:
                yield (lesson_label, module_type, module_text, urls)

def create_sous(xml_string):
    
    for lesson, module, text, urls in handle_xml(xml_string):
        pass
        
        

for item in handle_xml(xml_string):
    lesson, module, text, urls = item
    if module in ["gallery", "photo"]:
        node = build_carousel.create_carousel_node(urls, title=text)
        print (node)
    # caption text doesn't need to go in    
    print (item)
    
