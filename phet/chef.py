#!/usr/bin/env python

import json
import re
import requests
import tempfile
import zipfile

from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import HTMLZipFile, VideoFile
from ricecooker.classes.licenses import CC_BYLicense
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip

sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)

ID_BLACKLIST = ["html", "by-device", "new", "quantum", "general"]


class PhETSushiChef(SushiChef):

    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'phet.colorado.edu',
        'CHANNEL_SOURCE_ID': 'phet-html5-simulations',
        'CHANNEL_TITLE': 'PhET Interactive Simulations',
        'CHANNEL_THUMBNAIL': 'https://phet.colorado.edu/images/phet-social-media-logo.png',
        'CHANNEL_DESCRIPTION': 'The PhET Interactive Simulations project at the University of Colorado Boulder creates free interactive math and science simulations that engage students through an intuitive, game-like environment where students learn through exploration and discovery.',
    }

    def construct_channel(self, **kwargs):

        channel = ChannelNode(
            source_domain = self.channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = self.channel_info['CHANNEL_SOURCE_ID'],
            title = self.channel_info['CHANNEL_TITLE'],
            thumbnail = self.channel_info.get('CHANNEL_THUMBNAIL'),
            description = self.channel_info.get('CHANNEL_DESCRIPTION'),
        )

        LANGUAGE = "en"

        r = sess.get("https://phet.colorado.edu/services/metadata/1.1/simulations?format=json&type=html&locale=" + LANGUAGE)
        data = json.loads(r.content.decode())
        self.download_category(
            parent=channel,
            cat_id="1",
            categories=data["categories"],
            sims={proj["simulations"][0]["id"]: proj["simulations"][0] for proj in data["projects"]},
            keywords={kw["id"]: kw["strings"][0][LANGUAGE] for kw in data["keywords"]},
            language=LANGUAGE,
        )

        return channel

    def download_category(self, parent, cat_id, categories, sims, keywords, language):
        """
        Process a category, and add all its sub-categories, and its simulations/videos.
        """

        print("Processing category:", cat_id)

        cat = categories[str(cat_id)]

        # loop through all subtopics and recursively add them
        # (reverse order seems to give most rational results)
        for child_id in reversed(cat["childrenIds"]):
            # look up the child category by ID
            subcat = categories[str(child_id)]
            # skip it if it's in our blacklist
            if subcat["name"] in ID_BLACKLIST:
                continue
            # make the title human-readable, and clean it up
            title = subcat["name"].replace("-", " ").title()
            title = title.replace(" And ", " and ")
            title = title.replace("Mathconcepts", "Concepts")
            title = title.replace("Mathapplications", "Applications")
            # create the topic node, and add it to the parent
            subtopic = TopicNode(
                source_id=subcat["name"],
                title=title,
            )
            parent.add_child(subtopic)
            # recursively download the contents of the topic
            self.download_category(subtopic, child_id, categories, sims, keywords, language)

        # loop through all sims in this topic and add them, but only if we're at a leaf topic
        if len(parent.children) == 0:
            for sim_id in cat["simulationIds"]:
                # skip ones that aren't found (probably as they aren't HTML5)
                if sim_id not in sims:
                    continue
                self.download_sim(parent, sims[sim_id], keywords, language)

    def download_sim(self, topic, sim, keywords, language):
        """
        Download, zip, and add a node for a sim, as well as any associated video.
        """

        localized_sim = sim["localizedSimulations"][0]

        print("\tProcessing sim:", localized_sim["title"])

        dst = tempfile.mkdtemp()
        download_file(
            localized_sim["downloadUrl"],
            dst,
            filename="index.html",
            request_fn=sess.get,
            middleware_callbacks=[process_sim_html],
        )

        zippath = create_predictable_zip(dst)

        authors = re.sub(" \(.*?\)", "", sim["credits"]["designTeam"])
        authors = re.sub("<br\/?>", ", ", authors)

        # create a node for the sim
        simnode = HTML5AppNode(
            source_id="sim-%d" % sim["id"],
            files=[HTMLZipFile(zippath)],
            title=localized_sim["title"],
            description=sim["description"][language][:200],
            license=CC_BYLicense("PhET Interactive Simulations, University of Colorado Boulder"),
            # author=authors,
            # tags=[keywords[topic] for topic in sim["topicIds"]],
            thumbnail=sim["media"]["thumbnailUrl"],
        )

        # if there's a video, extract it and put it in the topic right before the sim
        videos = sim["media"]["vimeoFiles"]
        if videos:
            video_url = [v for v in videos if v.get("height") == 540][0]["link"]

            videonode = VideoNode(
                source_id="video-%d" % sim["id"],
                files=[VideoFile(video_url)],
                title="Video: %s" % localized_sim["title"],
                license=CC_BYLicense("PhET Interactive Simulations, University of Colorado Boulder"),
                thumbnail=sim["media"]["thumbnailUrl"],
            )

            topic.add_child(videonode)

        # add the sim node into the topic
        topic.add_child(simnode)


def process_sim_html(content, destpath, **kwargs):
    """Remove various pieces of the code that make requests to online resources, to avoid using
    bandwidth for users expecting a fully offline or zero-rated website."""

    # remove "are we online" check
    content = content.replace("check:function(){var t=this", "check:function(){return;var t=this")

    # remove online links from "about" modal
    content = content.replace("getLinks:function(", "getLinks:function(){return [];},doNothing:function(")

    soup = BeautifulSoup(content, "html.parser")

    for script in soup.find_all("script"):
        # remove Google Analytics and online image bug requests
        if "analytics.js" in str(script):
            script.extract()
        # remove menu options that link to online resources
        if 'createTandem("phetWebsiteButton' in str(script):
            script.string = re.compile('\{[^}]+createTandem\("phetWebsiteButton"\).*createTandem\("getUpdate"[^\}]*\},').sub("", script.string.replace("\n", " "))

    return str(soup)


if __name__ == '__main__':
    PhETSushiChef().main()