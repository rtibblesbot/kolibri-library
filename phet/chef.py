#!/usr/bin/env python

import json
import re
import requests
import tempfile
import zipfile
import time
import random

from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import HTMLZipFile, VideoFile
from ricecooker.classes.licenses import CC_BYLicense
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip
from le_utils.constants import roles
from le_utils.constants.languages import getlang

sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)

ID_BLACKLIST_BY_LANG = {
    'en': ["html", "by-device", "new", "quantum", "general"],
    'ar': ["html", "by-device", "new", "quantum", "general", "by-level"]
}

BASE_URL = "https://phet-api.colorado.edu"
BASE_URL_DOWNLOAD = "https://phet.colorado.edu"

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

# CHANNEL_ID = "d5c3b3aa38fd46c09b4643cea5d21779"  # Test channel ID
CHANNEL_NAME = "channel PhET Interactive Simulations "  # Name of Kolibri channel
CHANNEL_SOURCE_ID = "channel_PhET_Interactive_Simulations"  # Unique ID for content source
CHANNEL_DOMAIN = "https://phet.colorado.edu"  # Who is providing the content
CHANNEL_LANGUAGE = "ta"  # Language of channel
CHANNEL_THUMBNAIL = 'chefdata/phet-logo-TM-partners.png'

class PhETSushiChef(SushiChef):
    channel_info = {
        # 'CHANNEL_ID': CHANNEL_ID,
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_TITLE': CHANNEL_NAME,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTIONS,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL
    }

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

        # channel = ChannelNode(
        #     source_domain = 'phet.colorado.edu',
        #     source_id = 'phet-html5-simulations{}'.format(source_id_suffix),
        #     title = 'PhET Interactive Simulations ({})'.format(lang_obj.native_name),
        #     thumbnail = 'chefdata/phet-logo-TM-partners.png',
        #     description = description,
        #     language=lang_obj,
        # )

        channel = ChannelNode(
            source_domain='phet.colorado.edu',
            source_id='phet-html5-simulations{}-test'.format(source_id_suffix),
            title='PhET Interactive Simulations ({})'.format(lang_obj.native_name),
            thumbnail='chefdata/phet-logo-TM-partners.png',
            description=description,
            language=lang_obj,
        )

        return channel

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        # print("channel",channel)
        channel_info = self.channel_info
        LANGUAGE = kwargs.get("lang", "ht")
        channel = ChannelNode(
            source_domain=channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id=channel_info['CHANNEL_SOURCE_ID']+f'-{LANGUAGE}',
            title=channel_info['CHANNEL_TITLE'],
            thumbnail=channel_info.get('CHANNEL_THUMBNAIL'),
            description=channel_info.get('CHANNEL_DESCRIPTION').get(LANGUAGE),
            language="en",
        )

        # r = sess.get("https://phet.colorado.edu/services/metadata/1.1/simulations?format=json&type=html&locale=" + LANGUAGE)
        # data = json.loads(r.content.decode())
        # self.download_category(
        #     parent=channel,
        #     cat_id="1",
        #     categories=data["categories"],
        #     sims={proj["simulations"][0]["id"]: proj["simulations"][0] for proj in data["projects"]},
        #     keywords={kw["id"]: kw["strings"][0][LANGUAGE] for kw in data["keywords"]},
        #     language=LANGUAGE,
        # )
        r_sim = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/simulations?locate=" + LANGUAGE)
        r_cat = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/categories?locale=" + LANGUAGE)
        r_keyword = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/keywords?locale=" + LANGUAGE)
        sim_data = json.loads(r_sim.text)
        cat_data = json.loads(r_cat.text)
        keyword_data = json.loads(r_keyword.text)
        self.download_category(
            parent=channel,
            cat_id="1",
            categories=cat_data,
            sims={sim["id"]: sim for sim in sim_data["simulations"]},
            keywords={keyword_data.get(key).get("id"): keyword_data.get(key)["strings"][LANGUAGE] for key in
                      keyword_data if keyword_data.get(key)["strings"]},
            language=LANGUAGE

        )

        return channel

    def download_category(self, parent, cat_id, categories, sims, keywords, language):
        """
        Process a category, and add all its sub-categories, and its simulations/videos.
        """

        print("Processing category:", cat_id)
        cat = categories[str(cat_id)]
        random_sleep = random.randint(0,2)
        time.sleep(random_sleep)
        # loop through all subtopics and recursively add them
        # (reverse order seems to give most rational results)
        for child_id in reversed(cat["childrenIds"]):
            # look up the child category by ID
            subcat = categories[str(child_id)]
            # skip it if it's in our blacklist
            if subcat["name"] in ID_BLACKLIST_BY_LANG.get(language, ID_BLACKLIST_BY_LANG['en']):
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
                self.download_sim(parent, sims[sim_id], sim_id, keywords, language)

    def download_sim(self, topic, sim, sim_id, keywords, language):
        """
        Download, zip, and add a node for a sim, as well as any associated video.
        """
        sim_detail_res = sess.get(
            f'https://phet-api.colorado.edu/partner-services/2.0/metadata/simulations/{sim_id}?locale={language}')
        sim_detail_data = json.loads(sim_detail_res.text)
        time.sleep(2)
        # localized_sim = sim["localizedSimulations"][0]
        run_url = sim.get('defaultData').get('runUrl')
        title = sim.get('defaultData').get('title')
        if sim.get('localizedData') and sim.get('localizedData').get(language):
            if sim.get('localizedData').get(language).get('runUrl'):
                run_url = sim.get('localizedData').get(language).get('runUrl')
            if sim.get('localizedData').get(language).get('title'):
                title = sim.get('localizedData').get(language).get('title')

        download_url = f'{BASE_URL_DOWNLOAD}{run_url}?download'
        print("\tProcessing sim:", title)

        dst = tempfile.mkdtemp()
        download_file(
            download_url,
            dst,
            filename="index.html",
            request_fn=sess.get,
            middleware_callbacks=[process_sim_html],
        )

        zippath = create_predictable_zip(dst)
        authors = None
        if sim_detail_data.get("thanksTo"):
            authors = re.sub(" \(.*?\)", "", sim_detail_data["thanksTo"])
            authors = re.sub("<br\/?>", ", ", authors)

        if language == "ar":
            if title in ARABIC_NAME_CATEGORY:
                title = ARABIC_NAME_CATEGORY[title]
            if title in SIM_TYPO:
                title = SIM_TYPO[title]

        # get thumbnail image
        lst_sim_images = sim.get('defaultData').get('simImages')
        sim_image = lst_sim_images[0].get('url')
        for dict_image in lst_sim_images:
            if dict_image.get('width') == 128:
                sim_image = dict_image.get('url')
                break

        # create a node for the sim
        simnode = HTML5AppNode(
            source_id="sim-%d" % sim["id"],
            files=[HTMLZipFile(zippath)],
            title=title,
            # description=sim["description"][language][:200],
            license=CC_BYLicense("PhET Interactive Simulations, University of Colorado Boulder"),
            author=authors,
            # tags=[keywords[topic] for topic in sim["topicIds"]],
            thumbnail=sim_image,
            language=getlang(language),
        )

        # if there's a video, extract it and put it in the topic right before the sim
        if sim_detail_data.get('defaultData') and sim_detail_data.get('defaultData').get('simPrimerVideoData'):
            videos = sim_detail_data["defaultData"]["simPrimerVimeoData"]['files']
            if videos:
                video_url = [v for v in videos if v.get("height") == 540][0]["link"]

                videonode = VideoNode(
                    source_id="video-%d" % sim["id"],
                    files=[VideoFile(video_url)],
                    title="Video: %s" % title,
                    license=CC_BYLicense("PhET Interactive Simulations, University of Colorado Boulder"),
                    thumbnail=sim_image,
                    role=roles.COACH,
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
            script.string = re.compile(
                '\{[^}]+createTandem\("phetWebsiteButton"\).*createTandem\("getUpdate"[^\}]*\},').sub("",
                                                                                                      script.string.replace(
                                                                                                          "\n", " "))

    return str(soup)


if __name__ == '__main__':
    PhETSushiChef().main()
