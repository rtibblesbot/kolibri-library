import os
import subprocess
import sys
import time
import zipfile

import requests
import xmltodict

from bs4 import BeautifulSoup
from le_utils.constants import exercises
from lxml import etree

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import ExerciseNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.config import LOGGER

SESSION = requests.Session()
COURSE_URL = "https://www.microsoft.com/en-us/digital-literacy"


def make_request(url, timeout=60, method="GET", **kwargs):
    """
    Failure-resistant HTTP GET/HEAD request helper method.
    """
    retry_count = 0
    max_retries = 5
    # needs to change the User-Agent to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
    }
    while True:
        try:
            response = SESSION.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
            break
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            retry_count += 1
            LOGGER.warning(
                "Connection error ('{msg}'); about to perform retry {count} of {trymax}.".format(
                    msg=str(e), count=retry_count, trymax=max_retries
                )
            )
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                LOGGER.error("FAILED TO RETRIEVE:" + str(url))
                return None
    if response.status_code != 200:
        LOGGER.error("ERROR " + str(response.status_code) + " when getting url=" + url)
        return None
    return response


def download_page(url):
    """
    Download `url` (following redirects) and soupify response contents.
    Returns (final_url, page) where final_url is URL afrer following redirects.
    """
    response = make_request(url)
    if not response:
        return (None, None)
    html = response.text
    page = BeautifulSoup(html, "html.parser")
    LOGGER.debug("Downloaded page " + str(url))
    return (response.url, page)


def get_text(element):
    """
    Extract text contents of `element`, normalizing newlines to spaces and stripping.
    """
    if element is None:
        return ""
    else:
        return element.get_text().replace("\r", "").replace("\n", " ").strip()


def strip_ns_prefix(tree):
    """Strip namespace prefixes from an LXML tree.
    From https://stackoverflow.com/a/30233635
    """
    for element in tree.xpath("descendant-or-self::*[namespace-uri()!='']"):
        element.tag = etree.QName(element).localname


def get_quiz_from_objective(objective):
    questions = objective.findall("question")
    exercises = []
    for item in questions:
        if item.get("type") == "choice":
            question = item.find("prompt").text
            answers = [c.text for c in item.findall("choice")]
            correct = [c.text for c in item.findall("choice") if c.get("correct")][0]
            exercises.append(
                SingleSelectQuestion(
                    id="question_{}_{}_id".format(
                        objective.get("name").replace(" ", "_"), item.get("id")
                    ),
                    question=question,
                    all_answers=answers,
                    correct_answer=correct,
                )
            )

    return exercises


def get_exercise_node(idx, objectives, lesson):
    objective = [o for o in objectives if o.get("id") == idx][0]
    questions = get_quiz_from_objective(objective)
    node = ExerciseNode(
        source_id="questions_{}_id".format(objective.get("name").replace(" ", "_")),
        title="Knowledge check: {}".format(objective.get("name")),
        author="Microsoft",
        description="Knowledge check: {}".format(lesson),
        language="en",
        license=get_license("CC BY-NC-SA", copyright_holder="Microsoft"),
        thumbnail=None,
        exercise_data={
            "mastery_model": exercises.QUIZ,
            "randomize": True,
        },
        questions=questions,
    )
    return node


def get_course(lesson, zip_video_file):
    def tttl_from_mp4(mp4_file):
        file_path = mp4_file.replace("/Videos/", "/Captions/")
        file_name = os.path.splitext(file_path)
        ttml_file = "{}_Video_cc.ttml".format(file_name[0].strip())
        if not os.path.exists(ttml_file):
            ttml_file = "{}.ttml".format(file_name[0].strip())
        return ttml_file

    scorm_file = "chefdata/{}.zip".format(lesson)
    with zipfile.ZipFile(scorm_file) as zf:
        zf.extract("imsmanifest.xml", "chefdata")
        zf.extract("SCO1\en-us\pages.xml", "chefdata")

    # lesson info:
    manifest = etree.parse("chefdata/imsmanifest.xml").getroot()
    mt = manifest.find("metadata", manifest.nsmap)
    strip_ns_prefix(mt)
    general = xmltodict.parse(etree.tostring(mt.find("lom/general")))["general"]
    lesson_title = general["title"].get("langstring", {}).get("#text")
    lesson_desc = general["description"].get("langstring", {}).get("#text")

    topic = TopicNode(
        title=lesson_title,
        source_id="{}_id".format(lesson_title.replace(" ", "_")),
        description=lesson_desc,
    )

    # prepare video and subtitles files:
    filename = "chefdata/{}.zip".format(zip_video_file)
    if os.path.exists(filename) and not os.path.exists(
        "chefdata/{}".format(zip_video_file)
    ):
        LOGGER.info("Unzipping files for lesson: {}".format(lesson))
        with zipfile.ZipFile(filename, "r") as zip_ref:
            zip_ref.extractall("chefdata/{}".format(zip_video_file))

    # get list of mp4 files:
    list_of_mp4s = []
    dir_name = "chefdata/{}".format(
        os.path.basename(os.path.splitext(zip_video_file)[0])
    )
    for path, _, files in os.walk(dir_name):
        for f in files:
            file_path = os.path.join(path, f)
            if os.path.isfile(file_path) and f.endswith(".mp4"):
                list_of_mp4s.append(file_path)

    # parse xml with all the lessons structure:
    page = etree.parse("chefdata/SCO1\en-us\pages.xml").getroot()
    level0_elements = page.findall("level0")  # parent topic
    objectives = page.find("objectives").getchildren()
    discarded = ("Homepage", "Print your certificate")
    for level0 in level0_elements:  # subtopics with videos and exercises
        level0_name = level0.get("name")
        if level0_name in discarded:
            continue
        levels1 = level0.getchildren()
        if len(levels1) <= 1:
            continue

        sub_topic = TopicNode(
            title=level0_name,
            source_id="{}_id".format(level0_name.replace(" ", "_")),
            description=levels1[0].getchildren()[0].text,
        )
        topic.add_child(sub_topic)

        for level1 in levels1[1:]:
            videos = level1.getchildren()
            if level1.get("name") == "Knowledge check":
                sub_topic.add_child(
                    get_exercise_node(level1.get("objectives"), objectives, level0_name)
                )
                continue
            if len(videos) == 0:
                continue
            for idx, video in enumerate(videos):
                if video.tag == "video":
                    video_file_name = [
                        v for v in list_of_mp4s if v.endswith(video.get("fileName"))
                    ]
                    if len(video_file_name) != 0:
                        title = (
                            level1.get("name")
                            if idx == 0
                            else "{}-{} part".format(level1.get("name"), idx)
                        )
                        video_node = VideoNode(
                            title=title,
                            author="Microsoft",
                            source_id="{}_{}_id".format(
                                os.path.basename(video_file_name[0]),
                                level1.get("pageId"),
                            ),
                            license=get_license(
                                "CC BY-NC-SA", copyright_holder="Microsoft"
                            ),
                            files=[
                                VideoFile(path=video_file_name[0], language="en"),
                                SubtitleFile(
                                    path=tttl_from_mp4(video_file_name[0]),
                                    language="en",
                                ),
                            ],
                        )
                        sub_topic.add_child(video_node)

    return topic


class DigitalLiteracySushiChef(SushiChef):

    channel_info = {
        "CHANNEL_TITLE": "Microsoft Digital Literacy - English",
        "CHANNEL_SOURCE_DOMAIN": "https://www.microsoft.com/en-us/digital-literacy",
        "CHANNEL_SOURCE_ID": "ms-digital-literacy-english",
        "CHANNEL_LANGUAGE": "en",
        "CHANNEL_THUMBNAIL": "chefdata/MDL.jpg",
        "CHANNEL_DESCRIPTION": "Learn how to gain digital literacy to use devices, software, and the Internet to collaborate with others and discover, use, and create information.",
    }

    SETTINGS = {
        "compress": True,
        "ffmpeg_settings": {"video-height": 480},
    }

    def crawl(self):
        LOGGER.info("Crawling...")
        _, page = download_page(COURSE_URL)
        scorm_intro = page.find_all(
            "p",
            string="Download the English Digital Literacy SCORM packages by course module.",
        )
        list_of_lessons = scorm_intro[0].find_next_sibling("ul")
        lessons = {}
        for li in list_of_lessons.find_all("li"):
            lesson = li.find("a")
            lessons[lesson.get_text()] = lesson.get("href")
        self.lessons = lessons

        course_intro = page.find_all(
            "button",
            string="English course resources",
        )
        list_of_topics = course_intro[0].find_all_next("ul")[0]
        topics = {}
        for li in list_of_topics.find_all("li"):
            topic = li.find("a")
            if (
                "Transcript" not in topic.get_text()
            ):  # skip download of Transcript Files
                topics[topic.get_text()] = topic.get("href")
        self.zipped_videos = topics

    def download_courses(self):
        for lesson, url in self.lessons.items():
            LOGGER.info("Downloading lesson: {}".format(lesson))
            filename = "chefdata/{}.zip".format(lesson)
            if not os.path.exists(filename):
                response = requests.get(url, stream=True)
                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=512):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
            else:
                LOGGER.info("File already exists for lesson: {}".format(lesson))

        # This is a waste of disk space and bandwidth but scorm files don't
        # have video subtitles and video files don't have course info !!
        for lesson, url in self.zipped_videos.items():
            filename = "chefdata/{}.zip".format(lesson)
            if not os.path.exists(filename):
                LOGGER.info("Downloading topic: {}".format(lesson))
                response = requests.get(url, stream=True)
                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=512):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
            else:
                LOGGER.info("Video file already exists for lesson: {}".format(lesson))

    def get_teacher_resources(self):
        filename = "chefdata/Teacher Resource files"
        if not os.path.exists(filename):
            with zipfile.ZipFile("{}.zip".format(filename), "r") as zip_ref:
                zip_ref.extractall(filename)

        # convert files to pdf:
        pdf_files = []
        for path, _, files in os.walk(filename):
            for f in files:
                file_path = os.path.join(path, f)
                pdf_file_path = "chefdata/teacher_files/{}.pdf".format(
                    os.path.basename(os.path.splitext(file_path)[0])
                )
                if os.path.isfile(file_path) and not os.path.exists(pdf_file_path):
                    LOGGER.info("Converting {} to pdf...".format(file_path))
                    args = [
                        "libreoffice",
                        "--headless",
                        "--convert-to",
                        "pdf",
                        file_path,
                        "--outdir",
                        "chefdata/teacher_files/",
                    ]
                    try:
                        subprocess.run(args)
                    except FileNotFoundError:
                        LOGGER.error("LibreOffice must be installed and accesible in order to run this chef.")
                        sys.exit(1)
                elif os.path.exists(pdf_file_path):
                    pdf_files.append(pdf_file_path)

        topic = TopicNode(
            title="Teacher resources",
            source_id="teacher_resources_id",
            description="Resources for teachers.",
        )
        for index, pdf in enumerate(sorted(pdf_files)):
            node = DocumentNode(
                title=os.path.basename(os.path.splitext(pdf)[0]).replace("_", " "),
                description="Teacher guide",
                source_id="teacher_resource_{}_id".format(index),
                license=get_license("CC BY-NC-SA", copyright_holder="Microsoft"),
                language="en",
                files=[
                    DocumentFile(
                        path=pdf,
                        language="en",
                    )
                ],
            )
            topic.add_child(node)

        return topic

    def pre_run(self, args, options):
        self.crawl()
        self.download_courses()

    def construct_channel(self, *args, **kwargs):
        channel = self.get_channel(*args, **kwargs)
        video_files = list(self.zipped_videos.keys())

        for count, lesson in enumerate(self.lessons):
            channel.add_child(get_course(lesson, video_files[count]))

        channel.add_child(self.get_teacher_resources())
        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --token=YOURTOKENHERE9139139f3a23232

    """
    chef = DigitalLiteracySushiChef()
    chef.main()
