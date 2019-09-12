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
from le_utils.constants.languages import getlang

sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)

ID_BLACKLIST = ["html", "by-device", "new", "quantum", "general", "by-level"]
ARABIC_NAME_CATEGORY = {
    "Physics": "الفيزياء",
    "Biology": "الأحياء",
    "Chemistry": "الكيمياء",
    "Motion": "الحركة",
    "Sound and Waves": "الصوت والأمواج",
    "Work Energy and Power": "الشغل والطاقة",
    "Earth Science": "علوم الأرض",
    "Math": "الرياضيات",
    "Heat and Thermodynamics": "الحرارة والديناميكا الحرارية",
    "Quantum Phenomena": "فيزياء الكم",
    "Light and Radiation": "الضوء والإشعاعات",
    "Electricity Magnets and Circuits": "المغناطيس الكهربائي والدّارة الكهربائية",
    "pH Scale": "مقياس معامل الحموضة pH",
    "مقياس pH  : إبتدائي": "مقياس معامل الحموضة pH  : إبتدائي",
    "Beer's Law Lab": "مختبر قانون بير",
    "Bending Light": "انكسار الضوء",
    "Concepts": "مفاهيم",
    "Applications": "تطبيقات",
}

SIM_TYPO = {
    "أشكال الجزئ": "أشكال الجزيء",
    "مولارية": "المولارية",
    "محاليل حمض-قلوي ": "المحاليل حمضي-قلوي ",
    "بناء ذرة": "بناء الذرة",
    "المظائر والكتلة الذرية": "النظائر والكتلة الذرية",
    "تحت ضغط": "تحت الضغط",
    "انشاء الدّالة": "إنشاء الدّالة",
    "تكوين العشرة": "تكوين العشرات",
    "رؤية اللّون": "رؤية الألوان",
}


CHANNEL_DESCRIPTIONS = {
    'ar': 'تزوّد هذه القناة والمعمول بمحتواها من قبل جامعة كونيتيكيت الأمريكية مجموعة من برمجيات المحاكاة التي يمكن للمتعلمين في المرحلة الإعدادية والثانوية التفاعل معها لفهم أكبر لما قد يدرسونه من قوانين وتجارب في الرياضيات والعلوم المختلفة وخاصة مادتي الكيمياء والفيزياء.',
    'en': 'The PhET Interactive Simulations project created by the University of Colorado Boulder provides interactive math and science simulations that engage students with intuitive, game-like environments. Students can learn about math, physics, biology, and chemistry through hands-on exploration and discovery. The simulations are appropriate for all ages and include guiding teacher lesson plans.',
}


class PhETSushiChef(SushiChef):

    def get_channel(self, **kwargs):
        LANGUAGE = kwargs.get("lang", "en")
        lang_obj = getlang(LANGUAGE)

        if LANGUAGE == "en":
            source_id_suffix = ''
        else:
            source_id_suffix = '-{}'.format(LANGUAGE)

        description = CHANNEL_DESCRIPTIONS.get(LANGUAGE, None)
        if description is None:
            description = CHANNEL_DESCRIPTIONS['en']

        channel = ChannelNode(
            source_domain = 'phet.colorado.edu',
            source_id = 'phet-html5-simulations{}'.format(source_id_suffix),
            title = 'PhET Interactive Simulations ({})'.format(lang_obj.native_name),
            thumbnail = 'chefdata/phet-logo-TM-partners.png',
            description = description,
            language=lang_obj,
        )

        return channel

    def construct_channel(self, **kwargs):

        channel = self.get_channel(**kwargs)
        LANGUAGE = kwargs.get("lang", "en")

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

            if language == "ar":
                title = ARABIC_NAME_CATEGORY[title]
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
            for sim_id in list(set(cat["simulationIds"])):
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

        title = localized_sim["title"]
        if language == "ar":
            if title in ARABIC_NAME_CATEGORY:
                title = ARABIC_NAME_CATEGORY[title]
            if title in SIM_TYPO:
                title = SIM_TYPO[title]

        # create a node for the sim
        simnode = HTML5AppNode(
            source_id="sim-%d" % localized_sim["id"],
            files=[HTMLZipFile(zippath)],
            title=title,
            description=sim["description"][language][:200],
            license=CC_BYLicense("PhET Interactive Simulations, University of Colorado Boulder"),
            # author=authors,
            # tags=[keywords[topic] for topic in sim["topicIds"]],
            thumbnail=sim["media"]["thumbnailUrl"],
            language=getlang(language),
        )

        # if there's a video, extract it and put it in the topic right before the sim
        videos = sim["media"]["vimeoFiles"]
        if videos:
            video_url = [v for v in videos if v.get("height") == 540][0]["link"]

            videonode = VideoNode(
                source_id="video-%d" % localized_sim["id"],
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
