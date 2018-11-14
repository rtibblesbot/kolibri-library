#!/usr/bin/env python
import json
import os
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin


from libpyppeteer import visit_page, get_resource_requests_from_networktab


START_URL = 'https://www.edraak.org/k12/'
CRAWLING_STAGE_OUTPUT = 'chefdata/trees/web_resource_tree.json'



# CRAWLING
################################################################################


def get_page(url, loadjs=False, networktab=False):
    """
    Download `url` (following redirects) and soupify response contents.
    Returns (final_url, page) where final_url is URL afrer following redirects.
    """
    result = visit_page(url, loadjs=loadjs, networktab=networktab)
    html = result['content']
    page = BeautifulSoup(html, "html.parser")
    return page


def get_text(element):
    """
    Extract text contents of `element`, normalizing newlines to spaces and stripping.
    """
    if element is None:
        return ''
    else:
        return element.get_text().replace('\r', '').replace('\n', ' ').strip()

def scrape_topics(url):
    """
    Get topic links from page 'https://www.edraak.org/k12/'
    """
    page = get_page(url)
    subject_name = get_text(page.find('div', class_="subject"))
    topics_div = page.find('div', class_="topics")
    topics = []
    for topic_div in topics_div.find_all('div', class_="topic"):
        topic_name = get_text(topic_div.find('div', class_="topic-name"))
        topic_link = topic_div.find('a')
        url = topic_link['href']
        thumbnail_url = topic_link.find('img')['src']
        topic = dict(
            title=topic_name,
            url=url,
            thumbnail_url=thumbnail_url,
        )
        topics.append(topic)
    return topics




def write_web_resource_tree_json(channel_dict):
    destpath = CRAWLING_STAGE_OUTPUT
    parent_dir, _ = os.path.split(destpath)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(destpath, 'w') as wrt_file:
        json.dump(channel_dict, wrt_file, indent=2, sort_keys=True)


def build_web_resource_tree(start_url):
    channel_dict = dict(
        title='Edraak Channel',
        url=start_url,
        children=[],
    )
    math_dict = dict(
        title='الرياضيات',
        title_en='math',
        children=[],
    )
    channel_dict['children'].append(math_dict)
    
    topics = scrape_topics(start_url)
    for topic in topics:
        print('GET', topic['url'])
        topic_dict = dict(
            title=topic['title'],
            url=topic['url'],
            thumbnail_url=topic['thumbnail_url'],
            children=[],
        )
        topic_dict['component_url'] = get_course_component(topic['url'])
        math_dict['children'].append(topic_dict)

    write_web_resource_tree_json(channel_dict)
    return channel_dict



# SCRAPING
################################################################################

def get_course_component(url):
    """
    Downloads the website page at `url` and watches the network tab to
    extract the `component_url` of the form `/api/component/{component_id}/`.
    """
    result = visit_page(url, loadjs=True, networktab=True)
    networktab = result['networktab']
    resource_requests = get_resource_requests_from_networktab(networktab)
    components = []
    for rr in resource_requests:
        if 'api/component' in rr['url']:
            components.append(rr['url'])
    if len(components) == 0:
        print('url=', url)
        raise ValueError('No components found!')

    elif len(components) > 1:
        print('url=', url)
        for c in components:
            print('component=', c)
        raise ValueError('More than one component found!')

    else:
        return components[0]


if __name__ == '__main__':
    url = 'https://programs.edraak.org/learn/repository/math-algebra-topics-v2/section/5a6088188c9a02049a3e69e5/'
    component_url = get_course_component(url)
    print(component_url)



# UNUSED
################################################################################


def scrape_grades(page):
    """
    Get grades from the /k12/ page.
    """
    grades_div = page.find('div', class_="grades")
    grades = grades_div.find_all('a', class_='grade')

    grade_dicts = []
    for grade in grades:
        grade_url = urljoin(url, grade['href'])
        # print(grade)
        # number
        number_div = grade.find('div', class_="grade-no")
        name_div = number_div.find('sup', class_="sup-grade")
        name_div.extract()
        grade_no = get_text(number_div)

        # name
        grade_text = get_text(grade.find('div', class_="grade-text"))

        grade_dict = dict(
            grade_url=grade_url,
            grade_no=grade_no,
            grade_text=grade_text
        )
        grade_dicts.append(grade_dict)

    return grade_dicts



