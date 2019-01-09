#!/usr/bin/env python
import os
import requests

from le_utils.constants import content_kinds, exercises, licenses
from le_utils.constants.languages import getlang  # see also getlang_by_name, getlang_by_alpha2
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.utils.jsontrees import write_tree_to_json_tree

from ricecooker.config import LOGGER
import logging
LOGGER.setLevel(logging.INFO)


# KAMKALIMA CONSTANTS
################################################################################
KAMKALIMA_DOMAIN = 'https://kamkalima.com'
KAMKALIMA_CHANNEL_DESCRIPTION = """منصّة تعليم معزّزة بالتكنولوجيا تمنح المعلّمين قدرات خارقة والتّلاميذ تميّزًا في اللّغة العربيّة."""
KAMKALIMA_LICENSE = get_license(licenses.CC_BY_NC_ND, copyright_holder='Kamkalima').as_dict()

# KAMKALIMA API
################################################################################
API_AUDIOS_ENDPOINT = KAMKALIMA_DOMAIN + '/api/v0/audios'
API_TEXTS_ENDPOINT = KAMKALIMA_DOMAIN + '/api/v0/texts'
TOKEN_PATH = 'credentials/api_token.txt'
KAMKALIMA_API_TOKEN = None
if os.path.exists('credentials/api_token.txt'):
    with open(TOKEN_PATH,'r') as api_token_file:
        KAMKALIMA_API_TOKEN = api_token_file.read().strip()
else:
    raise ValueError('Could not find API Token in ' + TOKEN_PATH)

def append_token(api_endpoint):
    return api_endpoint + '?api_token=' + KAMKALIMA_API_TOKEN



# API EXTRACT FUNCTIONS
################################################################################

def get_all_texts():
    """
    Get the texts items from all pages through the API.
    """
    all_texts_items = []
    texts_url = append_token(API_TEXTS_ENDPOINT)
    while True:
        resp = requests.get(texts_url)
        texts_data = resp.json()
        items = texts_data['items']
        all_texts_items.extend(items)
        if 'next_page_url' in texts_data and KAMKALIMA_DOMAIN in texts_data['next_page_url']:
            texts_url = texts_data['next_page_url']
        else:
            print('Reached end of texts results')
            break
    return all_texts_items


def get_all_audios():
    """
    Get the audios items from all pages through the API.
    """
    all_audios_items = []
    audios_url = append_token(API_AUDIOS_ENDPOINT)
    while True:
        resp = requests.get(audios_url)
        audios_data = resp.json()
        items = audios_data['items']
        all_audios_items.extend(items)
        if 'next_page_url' in audios_data and KAMKALIMA_DOMAIN in audios_data['next_page_url']:
            audios_url = audios_data['next_page_url']
        else:
            print('Reached end of audios results')
            break
    return all_audios_items


# TRANSFORM FUNCTIONS
################################################################################

EXERCISE_CATEGORY_LOOKUP = {
    'grammar': 'قواعد',
    'vocabulary': 'مفردات اللغه',
    'comprehension': 'استيعاب',
    'listening': 'استماع',
}
EXERCISE_AR = 'ممارسه الرياضه'  # Maybe add this to each catrogy??


def exercise_from_kamkalima_questions_list(item_id, category, exercise_questions):
    exercise_title = EXERCISE_CATEGORY_LOOKUP[category]
    # Exercise node
    exercise_dict = dict(
        kind = content_kinds.EXERCISE,
        title = exercise_title,
        author = 'Kamkalima',
        source_id=str(item_id)+':'+category,
        description='',
        language=getlang('ar').code,
        license=KAMKALIMA_LICENSE,
        exercise_data={
            'mastery_model': exercises.M_OF_N,         # or exercises.DO_ALL
            'randomize': False,
            'm': 3,                  # By default require 3 to count as mastery
        },
        # thumbnail=
        questions=[],
    )
    # Add questions
    questions = []
    for exercise_question in exercise_questions:
        question_dict = dict(
            question_type=exercises.SINGLE_SELECTION,
            id=str(exercise_question['id']),
            question=exercise_question['title'],
            correct_answer = None,
            all_answers = [],
            hints =[],
        )
        # Add answers to question
        for answer in exercise_question['answers']:
            answer_text = answer['title']
            question_dict['all_answers'].append(answer_text)
            if answer['is_correct']:
                question_dict['correct_answer'] = answer_text
        questions.append(question_dict)
    exercise_dict['questions'] = questions

    # Update m in case less than 3 quesitons in the exercise
    if len(questions) < 3:
        exercise_dict['exercise_data']['m'] = len(questions)
    return exercise_dict



# CHEF
################################################################################

class KamkalimaChef(JsonTreeChef):
    """
    The chef class that takes care of uploading channel to Kolibri Studio.
    We'll call its `main()` method from the command line script.
    """
    RICECOOKER_JSON_TREE = 'kamkalima_ricecooker_json_tree.json'

    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel
        """
        LOGGER.info('in pre_run...')
        ricecooker_json_tree = dict(
            title='Kamkalima (العربيّة)',         # a humand-readbale title
            source_domain=KAMKALIMA_DOMAIN,       # content provider's domain
            source_id='audios-and-texts',        # an alphanumeric channel ID
            description=KAMKALIMA_CHANNEL_DESCRIPTION,
            thumbnail='./chefdata/kk-logo.png',
            language=getlang('ar').code,          # language code of channel
            children=[],
        )
        self.create_content_nodes(ricecooker_json_tree)

        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)


    def create_content_nodes(self, channel):
        """
        This function uses the methods `add_child` and `add_file` to build the
        hierarchy of topic nodes and content nodes. Every content node is associated
        with the underlying file node.
        """
        all_audios_items = get_all_audios()
        audio_item = all_audios_items[3]
        item_id = audio_item['id']
        for category, exercise_questions in audio_item['questions'].items():
            exercise_node = exercise_from_kamkalima_questions_list(item_id, category, exercise_questions)
        
        channel['children'].append(exercise_node)



# CLI
################################################################################

if __name__ == '__main__':
    """
    This code will run when the sushi chef scripy is called on the command line.
    """
    chef = KamkalimaChef()
    chef.main()

