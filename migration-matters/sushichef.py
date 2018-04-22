#!/usr/bin/env python
import os
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from le_utils.constants import licenses


# Run constants
################################################################################
CHANNEL_NAME = "Migration Matters"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-migration-matters-en"    # Channel's unique id
CHANNEL_DOMAIN = "migrationmatters.me/#featured_courses"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = "Migration Matters is a non-profit "\
                      "that was founded in 2016 to address "\
                      "big topics on migration through short-form "\
                      "video courses that empower the public to have "\
                      "more nuanced and evidence-based conversations "\
                      "about migration and refugees."                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "thumbnail.png"                                    # Local path or url to image file (optional)

# Additional constants
################################################################################
from client import Client
from bs4 import BeautifulSoup
import requests
import youtube_dl
import re
from fake_useragent import UserAgent

BASE_URL = "https://iversity.org"
CLIENT = Client("shivi@learningequality.org", "kolibri")
CHANNEL_LICENSE = licenses.CC_BY_NC_ND
COPYRIGHT_HOLDER = "CC BY-NC-ND 4.0"
EMAIL_COURSE_URL = "http://migrationmatters.me/episode/"
_headers = { 'User-Agent': str(UserAgent().chrome) }
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
episode_dict = {}
page_dict = {}

# Create download directory if it doesn't already exist
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# The chef subclass
################################################################################
class MyChef(SushiChef):

    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in during upload_channel (currently None)
          - kwargs: extra argumens and options not handled by `uploadchannel`.
            For example, add the command line option   lang="fr"  and the string
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        CLIENT.login("{}/en/users/sign_in".format(BASE_URL))
        scrape_iversity(channel)
        scrape_email_courses(channel, EMAIL_COURSE_URL)

        # create a topic node for each episode
        # and add videos with same episode as children
        for episode in episode_dict:
            source_id = episode.strip().replace(" ", "_")
            topic = nodes.TopicNode(source_id=source_id, title=episode)
            for video in episode_dict[episode]:
                topic.add_child(video)
            channel.add_child(topic)

        return channel

def crawl_each_post(channel, post_url):
    resp = requests.get(post_url, headers=_headers)
    soup = BeautifulSoup(resp.content, "html.parser")
    wrapper = soup.find('div', {'class': 'wpb_wrapper'})
    course_name = wrapper.find('div', {'class': 'vc_custom_heading'}).getText().strip()
    delimiters = " OF ", " FROM "
    regexPattern = '|'.join(map(re.escape, delimiters))
    course = re.split(regexPattern, course_name)[1]
    wpb_video_wrapper = wrapper.find_all('div', {'class': 'wpb_video_wrapper'})

    if wpb_video_wrapper:

        for each_wrapper in wpb_video_wrapper:
            video_url = each_wrapper.find('iframe').attrs["src"].split("?feature")[0]
            video_id = video_url.split("/")[-1]

            ydl = youtube_dl.YoutubeDL({'outtmpl': './downloads/%(id)s.%(ext)s'})

            with ydl:
                result = ydl.extract_info(
                    "http://www.youtube.com/watch?v={}".format(video_id)
                )
            if 'entries' in result:
                video = result['entries'][0]
            else:
                video = result

            video_title = video["title"]
            video_source_id = video_title.strip().replace(" ", "_")
            video_path = "{}/{}.mp4".format(DOWNLOAD_DIRECTORY, video_id)
            video_file = files.VideoFile(path=video_path)
            video_node = nodes.VideoNode(
                source_id=video_source_id,
                title=video_title,
                files=[video_file],
                license=CHANNEL_LICENSE,
                copyright_holder=COPYRIGHT_HOLDER
            )

            if course not in episode_dict:
                episode_dict[course] = [video_node]
            else:
                episode_dict[course].append(video_node)
            LOGGER.info("   Uploading video - {}".format(video_title.strip()))

def crawl_video(channel, url, first=False):
    resp = requests.get(url, headers=_headers)
    soup = BeautifulSoup(resp.content, "html.parser")
    posts = soup.find_all('div', {'class': 'post'})
    for post in posts:
        post_url = post.find('a').attrs["href"]
        crawl_each_post(channel, post_url)
    if first:
        return soup

def scrape_email_courses(channel, url):
    soup = crawl_video(channel, url, True)
    pagination = soup.find('div', {'class': 'pagination'}).find_all('li')

    for page in pagination:
        pg, status = page.find("a").string, page.attrs.get("class")
        if pg not in page_dict:
            page_dict[pg] = status
            if status is None:
                next_page_url = page.find("a").attrs["href"]
                crawl_video(channel, next_page_url)

def scrape_iversity(channel):
    url = "{}/en/my/courses/rethinking-us-them-integration-and-diversity-in-europe/lesson_units".format(BASE_URL)
    LOGGER.info("   Scraping Migration Matters at {}".format(url))
    source = read_source(url)
    chapters = source.find_all('div', {'class': 'chapter-units-wrapper'})

    for chapter in chapters:
        title = str(chapter.find('div', {'class': 'chapter-title'}).string)
        source_id = title.strip().replace(" ", "_")
        topic = nodes.TopicNode(source_id=source_id, title=title)
        lessons = chapter.find_all('a', {'class': 'unit-wrapper'})

        for lesson in lessons:
            video_exists = lesson.find('i', {'class': 'unit_video'})
            if video_exists:
                video_title = str(lesson.find('span', {'class': 'unit-title'}).string)
                video_source_id = video_title.strip().replace(" ", "_")
                video_url = "{}{}".format(BASE_URL, lesson.attrs["href"])
                video_source = read_source(video_url)
                video_info = video_source.find('video')
                video_link = video_info.find('source', {'res':'480'}).attrs["src"]
                video_file = files.VideoFile(path=video_link)
                video_node = nodes.VideoNode(
                    source_id=video_source_id,
                    title=video_title,
                    files=[video_file],
                    license=CHANNEL_LICENSE,
                    copyright_holder=COPYRIGHT_HOLDER
                )
                LOGGER.info("   Uploading video - {}".format(video_title.strip()))
                topic.add_child(video_node)
        channel.add_child(topic)

def read_source(url):
    response = CLIENT.get(url)
    return BeautifulSoup(response.content, 'html5lib')

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
