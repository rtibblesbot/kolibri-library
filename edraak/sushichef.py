#!/usr/bin/env python
from bs4 import BeautifulSoup
import json
import os
import requests
from urllib.parse import urljoin


from le_utils.constants import content_kinds, exercises, file_types, licenses
from le_utils.constants.languages import getlang  # see also getlang_by_name, getlang_by_alpha2
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.utils.jsontrees import write_tree_to_json_tree


from ricecooker.config import LOGGER
import logging
LOGGER.setLevel(logging.INFO)


from html2text import html2text
from libpyppeteer import visit_page, get_resource_requests_from_networktab





# KAMKALIMA CONSTANTS
################################################################################
EDRAAK_DOMAIN = 'edraak.org'
EDRAAK_CHANNEL_DESCRIPTION = """إدراك هي إحدى مبادرات مؤسسة الملكة رانيا في الأردن وهي منصة تزود المتعلمين في المراحل الأساسية والإعدادية والثانوية بدروس مصورة ملحوقة بتمارين تساعدهم في تقدمهم الأكاديمي داخل المدرسة. ومع أنّ المحتوى يتناسب مع المنهاج الوطني الأردني إلا أنه يتناسب أيضا مع كثير من المناهج الدراسية في دول المنطقة الأخرى."""
EDRAAK_LICENSE = get_license(licenses.ALL_RIGHTS_RESERVED, copyright_holder='Edraak').as_dict()




# CRAWLING
################################################################################
START_URL = 'https://www.edraak.org/k12/'
CRAWLING_STAGE_OUTPUT = 'chefdata/trees/web_resource_tree.json'

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

def get_component_url(component_id):
    return 'https://programs.edraak.org/api/component/' + component_id + '/'

def get_component(component_url):
    # print('GET', component_url)
    response = requests.get(component_url)
    component = response.json()
    return component

def get_component_from_id(component_id):
    component_url = get_component_url(component_id)
    return get_component(component_url)



# UNUSED
################################################################################


def scrape_grades(page):
    """
    Get grades from the /k12/ page.
    """
    grades_div = page.find('div', class_="grades")
    grades = grades_div.find_all('a', class_='grade')

    grade_dicts = []
    url = '?????????????????????'
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



# EXERCISES
################################################################################

def exercise_from_edraak_Exercise(exercise, parent_title=''):
    """ Parse one of these:
        {'id': '5a4c843b7dd197090857f05c',
         'program': 15,
         'parent_id': '5a4c843b7dd197090857f057',
         'title': 'التمرين',
    ?? 'deleted': False,
         'full_description': None,
         'listing_description': None,
         'visibility': 'staff_and_teachers',
         'children': [],
         'created': '2018-01-03T07:20:27.292000',
         'updated': '2018-01-08T10:38:41.246000',
         'keywords': [],
         'prerequisites': [],
         'scaffolds': [],
    ?? 'license': 'all_rights_reserved',
         'audience': [],
         'eligibility_criteria': [],
         'non_eligible_view': 'hidden',
         'gamification_points_on_completion': 0,
         'quick_access_components': [],
         'mastery_consecutive_questions_lookback': None,
         'mastery_consecutive_questions_threshold': None,
         'struggle_consecutive_questions_lookback': None,
         'struggle_consecutive_questions_threshold': None,
         '_cls': 'Component.FormActivityBase.Exercise',
         'question_set': None,
         'classification': ['Component', 'FormActivityBase', 'Exercise'],
         'component_type': 'Exercise',
         'is_eligible': True}
    """
    exercise_title = exercise['title']
    # Exercise node
    exercise_dict = dict(
        kind = content_kinds.EXERCISE,
        title = exercise_title,
        author = 'Kamkalima',
        source_id=exercise['id'],
        description='',
        language=getlang('ar').code,
        license=EDRAAK_LICENSE,
        exercise_data={
            'mastery_model': exercises.M_OF_N,
            'randomize': False,
            'm': 3,                   # By default require 3 to count as mastery
        },
        # thumbnail=
        questions=[],
    )
    question_set = exercise['question_set']
    question_set_children = question_set['children']

    # Add questions to exercise node
    questions = []
    for question in question_set_children:
        component_type = question['component_type']
        if component_type == 'MultipleChoiceQuestion':
            question_dict = question_from_edraak_MultipleChoiceQuestion(question)
            questions.append(question_dict)

        else:
            print('skipping component_type', component_type)

    exercise_dict['questions'] = questions

    # Update m in case less than 3 quesitons in the exercise
    if len(questions) < 3:
        exercise_dict['exercise_data']['m'] = len(questions)
    return exercise_dict


def question_from_edraak_MultipleChoiceQuestion(question):
    full_description = question['full_description']
    question_md = html2text(full_description, bodywidth=0)
    question_dict = dict(
        question_type=exercises.SINGLE_SELECTION,
        id=question['id'],
        question=question_md,
        correct_answer = None,
        all_answers = [],
        hints =[],
    )
    # Add answers to question
    for choice in question['choices']:
        answer_text = html2text(choice['description'], bodywidth=0)
        question_dict['all_answers'].append(answer_text)
        if choice['is_correct']:
            question_dict['correct_answer'] = answer_text

    return question_dict


# CHEF
################################################################################

class EdraakChef(JsonTreeChef):
    """
    The chef class that takes care of uploading channel to Kolibri Studio.
    We'll call its `main()` method from the command line script.
    """
    RICECOOKER_JSON_TREE = 'edraak_ricecooker_json_tree.json'

    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel.
        """
        LOGGER.info('in pre_run...')

        ricecooker_json_tree = dict(
            title='Edraak (العربيّة)',          # a humand-readbale title
            source_domain=EDRAAK_DOMAIN,       # content provider's domain
            source_id='programs',         # an alphanumeric channel ID
            description=EDRAAK_CHANNEL_DESCRIPTION,
            thumbnail='./chefdata/edraak-logo.png',   # logo created from SVG
            language=getlang('ar').code    ,          # language code of channel
            children=[],
        )
        self.add_content_nodes(ricecooker_json_tree)

        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)


    def add_content_nodes(self, channel):
        """
        Build the hierarchy of topic nodes and content nodes.
        """
        LOGGER.info('Creating channel content nodes...')
        sample_exercise_id = '5a4c843b7dd197090857f05c'
        exercise = get_component_from_id(sample_exercise_id)
        

        exercise_dict = exercise_from_edraak_Exercise(exercise, parent_title='Parent title would go here')
        
        # Add theme topic to channel
        channel['children'].append(exercise_dict)



# CLI
################################################################################

if __name__ == '__main__':
    """
    This code will run when the sushi chef scripy is called on the command line.
    """
    chef = EdraakChef()
    chef.main()


# if __name__ == '__main__':
#     url = 'https://programs.edraak.org/learn/repository/math-algebra-topics-v2/section/5a6088188c9a02049a3e69e5/'
#     component_url = get_course_component(url)
#     print(component_url)
