#!/usr/bin/env python
import csv
import json
import os
import re

from le_utils.constants.labels import levels
from le_utils.constants.labels import subjects
from ricecooker.chefs import SushiChef
from ricecooker.classes import files
from ricecooker.classes import licenses
from ricecooker.classes import nodes
from ricecooker.config import LOGGER
from ricecooker.utils.youtube import YouTubePlaylistUtils
from ricecooker.utils.youtube import YouTubeVideoUtils


YOUTUBE_CACHE_DIR = os.path.join("chefdata", "youtubecache")


def extract_id_from_link(link):
    match = re.search(r"list=([^&]+)", link)
    return match.group(1) if match else None


def convert_row(row):
    return {
        "level1Folder": row["Level 1 folders"],
        "level2Folder": row["Level 2 folders"],
        "grade_level": row["grade_level"],
        "subject": row["subject"],
        "id": extract_id_from_link(row["Link"]),
    }


def convert_csv(csv_path):
    with open(csv_path, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        return [convert_row(row) for row in reader]


VIDEO_JSON_FOLDER = os.path.join("chefdata", "video_json")


# create a csv folder in chefdata and write video info to it
def get_youtube_playlist_data():
    playlists = convert_csv("playlists.csv")

    if not os.path.isdir(VIDEO_JSON_FOLDER):
        os.makedirs(VIDEO_JSON_FOLDER)
    for playlist_data in playlists:
        if not os.path.isfile(
            os.path.join(VIDEO_JSON_FOLDER, playlist_data["id"] + ".json")
        ):
            playlist = YouTubePlaylistUtils(
                id=playlist_data["id"], cache_dir=YOUTUBE_CACHE_DIR
            )
            playlist_info = playlist.get_playlist_info(use_proxy=False)
            for child in playlist_info["children"]:
                video = YouTubeVideoUtils(id=child["id"], cache_dir=YOUTUBE_CACHE_DIR)
                child["details"] = video.get_video_info(use_proxy=False)
            with open(
                os.path.join(VIDEO_JSON_FOLDER, playlist_data["id"] + ".json"), "w"
            ) as outfile:
                json.dump(playlist_info, outfile)
    with open(
        os.path.join(VIDEO_JSON_FOLDER, playlist_data["id"] + ".json")
    ) as json_file:
        playlist_data["info"] = json.load(json_file)
    return playlists


# Run constants
################################################################################
CHANNEL_NAME = "Guyana Learning Channel"  # Name of Kolibri channel
CHANNEL_SOURCE_ID = "GuyanaLearningChannel"  # Unique ID for content source
CHANNEL_DOMAIN = "https://www.youtube.com/@GuyanaLearningChannel/playlists"  # Who is providing the content
CHANNEL_LANGUAGE = "en"  # Language of channel
CHANNEL_DESCRIPTION = "Educational videos from the Guyana Ministry of Education for Grades 1 to 11. Including NGSA booster materials."  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://scontent-sjc3-1.xx.fbcdn.net/v/t39.30808-6/330600658_186248280790338_7083545507183946478_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=09cbfe&_nc_ohc=pCwUQY41DfYAX_DjO-P&_nc_ht=scontent-sjc3-1.xx&oh=00_AfD9bFU6QI6SZQWszr45l1jc6cdXPVav9JV881ah30aChg&oe=6497FC82"  # Local path or url to image file (optional)

COPYRIGHT_HOLDER = (
    "Guyana Ministry of Education"  # Name of content creator or rights holder
)


# The chef subclass
################################################################################
class GuyanaSEIPChef(SushiChef):
    """
    This class converts content from the content source into the format required by Kolibri,
    then uploads the {channel_name} channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://ricecooker.readthedocs.io
    """

    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": CHANNEL_DOMAIN,
        "CHANNEL_SOURCE_ID": CHANNEL_SOURCE_ID,
        "CHANNEL_TITLE": CHANNEL_NAME,
        "CHANNEL_LANGUAGE": CHANNEL_LANGUAGE,
        "CHANNEL_THUMBNAIL": CHANNEL_THUMBNAIL,
        "CHANNEL_DESCRIPTION": CHANNEL_DESCRIPTION,
    }

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(
            *args, **kwargs
        )  # Create ChannelNode from data in self.channel_info

        playlists = get_youtube_playlist_data()

        for playlist in playlists:
            playlist_info = playlist["info"]
            if playlist_info is None:
                LOGGER.warning(
                    "Skipping playlist {0} as not available from YouTube".format(
                        playlist["id"]
                    )
                )
                continue

            # Get channel description if there is any
            playlist_description = playlist_info["description"]

            grade_levels = [
                level
                for level, label in levels.choices
                if label.lower() == playlist["grade_level"].lower()
            ]

            categories = [
                subject
                for subject, label in subjects.choices
                if label.lower() == playlist["subject"].lower()
            ]

            topic_source_id = "aimhi-child-topic-{0}".format(playlist_info["title"])
            topic_node = nodes.TopicNode(
                title=playlist_info["title"],
                source_id=topic_source_id,
                author=COPYRIGHT_HOLDER,
                provider=COPYRIGHT_HOLDER,
                description=playlist_description,
                language=CHANNEL_LANGUAGE,
                grade_levels=grade_levels,
                categories=categories,
            )

            for child in playlist_info["children"]:
                video_details = child["details"]
                if video_details is None:
                    LOGGER.warning(
                        "Skipping video {0} as not available from YouTube".format(
                            child["id"]
                        )
                    )
                    continue
                video_source_id = "GuyanaSEIP-{0}-{1}".format(
                    playlist["id"], video_details["id"]
                )

                thumbnail_link = video_details["thumbnail"] or None

                video_node = nodes.VideoNode(
                    source_id=video_source_id,
                    title=video_details["title"],
                    description=video_details["description"],
                    author=COPYRIGHT_HOLDER,
                    language=CHANNEL_LANGUAGE,
                    provider=COPYRIGHT_HOLDER,
                    thumbnail=thumbnail_link,
                    license=licenses.get_license(
                        "CC BY-NC-ND", copyright_holder=COPYRIGHT_HOLDER
                    ),
                    files=[
                        files.YouTubeVideoFile(
                            youtube_id=video_details["id"], language=CHANNEL_LANGUAGE
                        )
                    ],
                )
                topic_node.add_child(video_node)
                if topic_node.thumbnail is None and thumbnail_link is not None:
                    # If the topic node does not have a thumbnail set the first
                    # video's thumbnail as the topic thumbnail, parallel to youtube playlists
                    topic_node.set_thumbnail(thumbnail_link)

            # add topic to channel
            channel.add_child(topic_node)

        return channel


# CLI
################################################################################
if __name__ == "__main__":
    # This code runs when script.py is called from the command line
    chef = GuyanaSEIPChef()
    chef.main()
