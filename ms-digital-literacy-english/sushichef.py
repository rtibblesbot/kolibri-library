import os
import requests
import time

from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import TopicNode, IMSCPNode
from ricecooker.classes.licenses import get_license
from ricecooker.classes.files import IMSCPZipFile
from ricecooker.config import LOGGER

SESSION = requests.Session()
COURSE_URL = "https://www.microsoft.com/en-us/digital-literacy"

"""
    Web scrapping the links for the course is not possible because MS does not 
    allow it. This message is returned:
    Your current User-Agent string appears to be from an automated process, 
    if this is incorrect, please click this link:
    <a href="http://www.microsoft.com/en/us/default.aspx?redir=true">
    United States English Microsoft Homepage</a></p>
"""

# HELPER METHODS
################################################################################


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


def get_course(index, lesson):

    topic = TopicNode(
        title="{} - {}".format(index, lesson),
        source_id="{}_id".format(lesson.replace(" ", "_")),
    )
    node = IMSCPNode(
        title=lesson,
        description="{} Course".format(lesson),
        source_id="{}_id".format(lesson.replace(" ", "-")),
        license=get_license("CC BY-NC-SA", copyright_holder="Microsoft"),
        language="en",
        files=[
            IMSCPZipFile(
                path="chefdata/{}.zip".format(lesson),
                language="en",
            )
        ],
    )
    topic.add_child(node)
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

    def crawl(self, args, options):
        print("crawling")
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
        return lessons

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

    def pre_run(self, args, options):
        self.lessons = self.crawl(args, options)
        self.download_courses()

    def construct_channel(self, *args, **kwargs):
        channel = self.get_channel(*args, **kwargs)
        for count, lesson in enumerate(self.lessons):
            channel.add_child(get_course(count + 1, lesson))

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --token=YOURTOKENHERE9139139f3a23232

    """
    chef = DigitalLiteracySushiChef()
    chef.main()
