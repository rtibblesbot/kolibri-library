#!/usr/bin/env python
from collections import defaultdict
from jinja2 import Template
import json
import os
import requests

from le_utils.constants import content_kinds, exercises, file_types, licenses
from le_utils.constants.languages import getlang
from ricecooker.chefs import JsonTreeChef
from ricecooker.config import LOGGER
from ricecooker.classes.licenses import get_license
from ricecooker.utils.html_writer import HTMLWriter
from ricecooker.utils.jsontrees import write_tree_to_json_tree




# KAMKALIMA CONSTANTS
################################################################################
KAMKALIMA_DOMAIN = "https://kamkalima.com"
KAMKALIMA_CHANNEL_DESCRIPTION = """تقدم المصادر التعليمية الخاصة باللغة العربية من منصة كم كلمة محتوى عربي متفاعل لمتعلمي ومعلمي المرحلة الثانوية. وتمكن النصوص والأنشطة التفاعلية المتعلمين من تطوير مهارات الاستماع والقراءة بالإضافة إلى مهارات وقواعد الكتابة العربية. وتقدم القناة للمعلمين مجموعة من الأدوات التربوية لتمكنهم من متابعة تقدم وتعلم المتعلمين على اختلاف مستوياتهم."""
KAMKALIMA_LICENSE = get_license(
    licenses.CC_BY_NC_ND, copyright_holder="Kamkalima"
).as_dict()

# KAMKALIMA API
################################################################################
AUTHORIZATION_ENDPOINT = KAMKALIMA_DOMAIN + "/oauth/token"
API_AUDIOS_ENDPOINT = KAMKALIMA_DOMAIN + "/api/v1/content/audios"
API_TEXTS_ENDPOINT = KAMKALIMA_DOMAIN + "/api/v1/content/texts"

CLIENT_CREDENTIALS_PATH = "credentials/client_credentials.json"


HTML5APP_ZIPS_LOCAL_DIR = "chefdata/zipfiles"
HTML5APP_TEMPLATE = "chefdata/html5app_template"


# AUTHENTICATION API
################################################################################

def get_authentication_token():
    """
    Call `/oauth/token` to obtain `access_token` for use with the content API.
    """
    client_credentials = json.load(open(CLIENT_CREDENTIALS_PATH))
    data = {
        "grant_type": "client_credentials",
        "client_id": client_credentials["client_id"],
        "client_secret": client_credentials["client_secret"],
    }
    response = requests.post(AUTHORIZATION_ENDPOINT, data=data)
    if response.ok:
        access_token = response.json()['access_token']
        LOGGER.info('Successfully obtained authorization token')
        return access_token
    else:
        raise ConnectionError('Get auth token failed ' + AUTHORIZATION_ENDPOINT)



# API EXTRACT FUNCTIONS
################################################################################

def get_all_items(start_url, access_token):
    """
    Get items from all pages through the API (texts or audios).
    """
    all_items = []
    current_url = start_url
    while True:
        headers = {
            'Authorization': 'Bearer ' + access_token
        }
        LOGGER.debug('GET ' + current_url)
        resp = requests.get(current_url, headers=headers)
        if not resp.ok:
            LOGGER.error("Response " + str(resp.status_code) + " on " + current_url)
            break
        data = resp.json()
        items = data["items"]
        all_items.extend(items)
        if (
            "next_page_url" in data
            and data["next_page_url"]
            and KAMKALIMA_DOMAIN in data["next_page_url"]
        ):  # key exists, is not null, and looks like a valid URL
            current_url = data["next_page_url"]
        else:
            LOGGER.debug('Reached end of API results')
            break
    if all_items:  # > 0
        LOGGER.info("  Found %s items" % len(all_items) )
        return all_items
    else:
        raise RuntimeError("Kamkalima API not accessible or 0 items returned.")


# TRANSFORM FUNCTIONS
################################################################################

EXERCISE_CATEGORY_LOOKUP = {
    "comprehension": "الاستيعاب",
    "grammar": "القواعد",
    "listening": "الاستماع",
    "vocabulary": "المفردات والتراكيب",
}
# EXERCISE_AR = 'ممارسه الرياضه'  # Maybe add this to each catrogy??


def exercise_from_kamkalima_questions_list(item_id, category, exercise_questions):
    exercise_title = EXERCISE_CATEGORY_LOOKUP[category]
    # Exercise node
    exercise_dict = dict(
        kind=content_kinds.EXERCISE,
        title=exercise_title,
        author="Kamkalima",
        source_id=str(item_id) + ":" + category,
        description="",
        language=getlang("ar").code,
        license=KAMKALIMA_LICENSE,
        exercise_data={
            "mastery_model": exercises.M_OF_N,
            "randomize": False,
            "m": 3,  # By default require 3 to count as mastery
        },
        # thumbnail=
        questions=[],
    )
    # Add questions to exercise node
    questions = []
    for exercise_question in exercise_questions:
        question_dict = dict(
            question_type=exercises.SINGLE_SELECTION,
            id=str(exercise_question["id"]),
            question=exercise_question["title"],
            correct_answer=None,
            all_answers=[],
            hints=[],
        )
        # Add answers to question
        for answer in exercise_question["answers"]:
            answer_text = answer["title"]
            if answer_text not in question_dict["all_answers"]:
                question_dict["all_answers"].append(answer_text)
                if answer["is_correct"]:
                    question_dict["correct_answer"] = answer_text
            else:
                LOGGER.warning("Duplicate answer in id=" + question_dict["id"])
        questions.append(question_dict)
    exercise_dict["questions"] = questions
    # Update m in case less than 3 quesitons in the exercise
    if len(questions) < 3:
        exercise_dict["exercise_data"]["m"] = len(questions)
    return exercise_dict


def group_by_theme(items):
    items_by_theme = defaultdict(list)
    for item in items:
        themes = item["themes"]
        for theme in themes:
            theme_name = theme["name"]
            items_by_theme[theme_name].append(item)
    return items_by_theme


def audio_node_from_kamkalima_audio_item(audio_item):
    if not audio_item["audio"]:
        LOGGER.error('No audio URL for audio id=' + str(audio_item['id']) + '  with title=' + audio_item['title'])
        return None
    audio_node = dict(
        kind=content_kinds.AUDIO,
        source_id=str(audio_item["id"]),
        title=audio_item["title"],
        description=audio_item["excerpt"],
        language=getlang("ar").code,
        license=KAMKALIMA_LICENSE,
        author=audio_item["author"]["name"],
        # aggregator
        # provider
        thumbnail=audio_item["image"],
        files=[
            {
                "file_type": file_types.AUDIO,
                "path": audio_item["audio"],
                "language": getlang("ar").code,
            }
        ],
    )
    return audio_node


def make_html5zip_from_text_item(text_item):
    id_str = str(text_item["id"])
    zip_path = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, id_str + ".zip")
    if os.path.exists(zip_path):
        LOGGER.debug("Found existing zip at " + zip_path)
        return zip_path
    else:
        LOGGER.debug("Creating zip from text_item id=" + str(text_item['id']))


    # load template
    template_path = os.path.join(HTML5APP_TEMPLATE, "index.template.html")
    template_src = open(template_path).read()
    template = Template(template_src)

    # extract properties
    title = text_item["title"]
    content = text_item["body"]
    author=text_item["author"]["name"],
    description = text_item["excerpt"]
    if "image" in text_item:
        splash_image_url = text_item["image"]
        show_splash_image = True
    else:
        show_splash_image = False

    # render template to string
    index_html = template.render(
        title=title,
        content=content,
        author=author,
        description=description,
        show_splash_image=show_splash_image,
    )

    # save to zip file
    with HTMLWriter(zip_path, "w") as zipper:
        # index.html
        zipper.write_index_contents(index_html)
        # css/styles.css
        with open(os.path.join(HTML5APP_TEMPLATE, "css/styles.css")) as stylesf:
            zipper.write_contents("styles.css", stylesf.read(), directory="css/")
        if show_splash_image:
            # img/splash.jpg
            resp = requests.get(splash_image_url)
            zipper.write_contents("splash.jpg", resp.content, directory="img/")
        else:
            LOGGER.warning("zip with id " + id_str + " has no splash image")

    return zip_path


def html5_node_from_kamkalima_text_item(text_item):
    zip_path = make_html5zip_from_text_item(text_item)
    html5_node = dict(
        kind=content_kinds.HTML5,
        source_id=str(text_item["id"]),
        title=text_item["title"],
        description=text_item["excerpt"],
        language=getlang("ar").code,
        license=KAMKALIMA_LICENSE,
        author=text_item["author"]["name"],
        # aggregator
        # provider
        thumbnail=text_item["image"],
        files=[
            {
                "file_type": file_types.HTML5,
                "path": zip_path,
                "language": getlang("ar").code,
            }
        ],
    )
    return html5_node


def topic_node_from_item(item_type, item):
    """
    In order to keep the audios and texts close to their associated exercises,
    we'll store each item as a topic node.
    `item_type` is either `audio` or `html5`
    """
    topic_node = dict(
        kind=content_kinds.TOPIC,
        source_id=str(item["id"]) + ":" + "container",
        title=item["title"],
        # description=item['excerpt'],
        language=getlang("ar").code,
        children=[],
    )

    # Add content node
    if item_type == "audio":
        audio_node = audio_node_from_kamkalima_audio_item(item)
        if audio_node:
            topic_node["children"].append(audio_node)
    elif item_type == "text":
        html5_node = html5_node_from_kamkalima_text_item(item)
        if html5_node:
            topic_node["children"].append(html5_node)
    else:
        raise ValueError("unrecognized item_type " + item_type)

    # Add associated exercises
    item_id = item["id"]
    for category, exercise_questions in item["questions"].items():
        exercise_node = exercise_from_kamkalima_questions_list(
            item_id, category, exercise_questions
        )
        topic_node["children"].append(exercise_node)
    return topic_node


# CHEF
################################################################################


class KamkalimaChef(JsonTreeChef):
    """
    The chef class that takes care of uploading channel to Kolibri Studio.
    We'll call its `main()` method from the command line script.
    """

    RICECOOKER_JSON_TREE = "kamkalima_ricecooker_json_tree.json"

    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel.
        """
        LOGGER.info("in pre_run...")

        if args["update"]:
            LOGGER.info(
                "Deleting all zips in cache dir {}".format(HTML5APP_ZIPS_LOCAL_DIR)
            )
            for zip_file in os.listdir(HTML5APP_ZIPS_LOCAL_DIR):
                zip_file_abs_path = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, zip_file)
                if zip_file_abs_path.endswith(".zip"):
                    os.remove(zip_file_abs_path)

        ricecooker_json_tree = dict(
            title="Kamkalima (العربيّة)",  # a humand-readbale title
            source_domain=KAMKALIMA_DOMAIN,  # content provider's domain
            source_id="audios-and-texts",  # an alphanumeric channel ID
            description=KAMKALIMA_CHANNEL_DESCRIPTION,
            thumbnail="./chefdata/kk-logo.png",  # logo created from SVG
            language=getlang("ar").code,  # language code of channel
            children=[],
        )
        self.add_content_nodes(ricecooker_json_tree)

        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)

    def add_content_nodes(self, channel):
        """
        Build the hierarchy of topic nodes and content nodes.
        """
        LOGGER.info("Creating channel content nodes...")

        LOGGER.info("  Calling Kamkalima API to get authorization token.")
        access_token = get_authentication_token()

        LOGGER.info("  Calling Kamkalima API to get texts items:")
        all_texts_items = get_all_items(API_TEXTS_ENDPOINT, access_token)
        texts_by_theme = group_by_theme(all_texts_items)

        LOGGER.info("  Calling Kamkalima API to get audios items:")
        all_audios_items = get_all_items(API_AUDIOS_ENDPOINT, access_token)
        audios_by_theme = group_by_theme(all_audios_items)

        all_themes = set(texts_by_theme.keys()).union(audios_by_theme.keys())

        LOGGER.info("Organizing content items by theme:")
        for theme in all_themes:
            LOGGER.info("  Processing theme " + theme)
            theme_topic_node = dict(
                kind=content_kinds.TOPIC, source_id=theme, title=theme, children=[]
            )
            # Add audios for this theme
            audio_items = audios_by_theme[theme]
            for audio_item in audio_items:
                child_topic = topic_node_from_item("audio", audio_item)
                theme_topic_node["children"].append(child_topic)
            # Add texts for this theme
            text_items = texts_by_theme[theme]
            for text_item in text_items:
                child_topic = topic_node_from_item("text", text_item)
                theme_topic_node["children"].append(child_topic)
            # Add theme topic to channel
            channel["children"].append(theme_topic_node)


# CLI
################################################################################

if __name__ == "__main__":
    """
    This code will run when the sushi chef scripy is called on the command line.
    """
    chef = KamkalimaChef()
    chef.main()
