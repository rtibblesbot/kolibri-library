#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import requests
import tempfile

from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import HTMLZipFile, VideoFile
from ricecooker.classes.licenses import CC_BYLicense
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip
from le_utils.constants import roles
from le_utils.constants.languages import getlang
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from deep_translator import GoogleTranslator
from metadata_tags import METADATA_BY_SLUG

retry_strategy = Retry(
    total=5,
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)

sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)
sess.mount('http://', adapter)
sess.mount('https://', adapter)
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

HAITIAN_NAME_CATEGORY = {
    'Elementary School': 'Lekòl Elemantè',
    'By Level': 'Pa Nivo',
    'Middle School': 'Lekòl mwayen',
    'High School': 'Lekòl Segondè',
    'University': 'Inivèsite',
    'By Device': 'Pa Aparèy',
    'Ipad Tablet': 'Tablet Ipad',
    'Chromebook': 'Chromebook',
    'Html': 'Html',
    'Concepts': 'Konsèp',
    'Applications': 'Aplikasyon',
    'Light and Radiation': 'Limyè ak Radyasyon ',
    'Electricity Magnets and Circuits': 'Leman elektrisite ak sikwi',
    'Biology': 'Biyoloji',
    'Chemistry': 'Chimi',
    'Earth Science': 'Syans Latè',
    'Math': 'Matematik',
    'General': 'Jeneral',
    'Root': 'Rasin',
    'Physics': 'Fizik',
    'Motion': 'Mouvman',
    'Sound and Waves': 'Son ak Vag',
    'Work Energy and Power': 'Travay Enèji ak pouvwa',
    'Heat and Thermodynamics': 'Chalè ak Thermodinamik',
    'Quantum Phenomena': 'Fenomèn Kantik',
    'Quantum': 'Quantum'}

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
    'ht': 'Pwojè PhET Interactive Simulations ki kreye pa Inivèsite Colorado Boulder ofri similasyon entèraktif matematik ak syans ki angaje elèv yo ak anviwònman entwisyon ki sanble ak yon jwèt. Elèv yo ka aprann matematik, fizik, byoloji, ak chimi atravè eksplorasyon pratik ak dekouvèt. Similasyon yo apwopriye pou tout laj e yo gen ladan plan leson pwofesè k ap gide yo.'
}

# CHANNEL_ID = "d5c3b3aa38fd46c09b4643cea5d21779"  # Test channel ID
CHANNEL_NAME = {"en": "PhET Interactive Simulations", "ht": "PhET (Kreyòl ayisyen)"}  # Name of Kolibri channel
CHANNEL_SOURCE_ID = "channel_PhET_Interactive_Simulations_TEST"  # Unique ID for content source
CHANNEL_DOMAIN = "https://phet.colorado.edu"  # Who is providing the content
CHANNEL_LANGUAGE = "en"  # Language of channel
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
    translator = None

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
        # channel = self.get_channel(**kwargs)
        channel_info = self.channel_info
        LANGUAGE = CHANNEL_LANGUAGE
        if not LANGUAGE:
            LANGUAGE = kwargs.get("lang", "en")
        self.translator = GoogleTranslator(source='auto', target=LANGUAGE)
        dict_downloaded_paths = {}
        title = channel_info['CHANNEL_TITLE'].get(LANGUAGE)
        if not title:
            title = channel_info['CHANNEL_TITLE'].get('en')
            title = '{}-{}'.format(title, LANGUAGE)
        description = channel_info.get('CHANNEL_DESCRIPTION').get(LANGUAGE)
        if not description:
            description = channel_info.get('CHANNEL_DESCRIPTION').get("en")
            description = self.translator.translate(description)

        channel = ChannelNode(
            source_domain=channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id=channel_info['CHANNEL_SOURCE_ID'] + f'-{LANGUAGE}',
            title=title,
            thumbnail=channel_info.get('CHANNEL_THUMBNAIL'),
            description=description,
            language=LANGUAGE,
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
            language=LANGUAGE,
            dict_downloaded_paths=dict_downloaded_paths
        )

        return channel

    def download_category(self, parent, cat_id, categories, sims, keywords, language, dict_downloaded_paths):
        """
        Process a category, and add all its sub-categories, and its simulations/videos.
        """
        print("Processing category:", cat_id)
        cat = categories[str(cat_id)]
        cat_name = None
        dict_cat_name = cat['strings']
        if dict_cat_name.get('en'):
            cat_name = dict_cat_name.get('en')
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
            if language == 'en':
                pass
            elif language == "ar":
                title = ARABIC_NAME_CATEGORY[title]
            elif language == 'ht':
                title = HAITIAN_NAME_CATEGORY[title]
            else:
                title = self.translator.translate(title)
            # create the topic node, and add it to the parent
            metadata = {}
            if METADATA_BY_SLUG.get(cat_name):
                metadata = METADATA_BY_SLUG.get(cat_name)
            sub_name = subcat.get('strings').get('en')
            sub_cat_metadata = METADATA_BY_SLUG.get(sub_name.lower())
            if sub_cat_metadata:
                if metadata.get('grade_levels'):
                    metadata.get('grade_levels').append(sub_cat_metadata.get('grade_levels'))
                if metadata.get('categories'):
                    metadata.get('categories').append(sub_cat_metadata.get('categories'))
                if not metadata:
                    metadata.update(sub_cat_metadata)
            if metadata:
                subtopic = TopicNode(
                    source_id=subcat["name"],
                    title=title,
                    **metadata
                )
            else:
                subtopic = TopicNode(
                    source_id=subcat["name"],
                    title=title
                )
            parent.add_child(subtopic)
            # recursively download the contents of the topic
            self.download_category(subtopic, child_id, categories, sims, keywords, language, dict_downloaded_paths)

        # loop through all sims in this topic and add them, but only if we're at a leaf topic
        if len(parent.children) == 0:
            for sim_id in list(set(cat["simulationIds"])):
                # skip ones that aren't found (probably as they aren't HTML5)
                if sim_id not in sims:
                    continue
                self.download_sim(parent, sims[sim_id], sim_id, keywords, language, dict_downloaded_paths)

    def download_sim(self, topic, sim, sim_id, keywords, language, dict_downloaded_paths):
        """
        Download, zip, and add a node for a sim, as well as any associated video.
        """
        sim_detail_res = sess.get(
            f'https://phet-api.colorado.edu/partner-services/2.0/metadata/simulations/{sim_id}?locale={language}')
        sim_detail_data = json.loads(sim_detail_res.text)
        # localized_sim = sim["localizedSimulations"][0]
        run_url = sim.get('defaultData').get('runUrl')
        title = sim.get('defaultData').get('title')
        if sim.get('highGradeLevel'):
            grade_level = sim.get('highGradeLevel').get('key')
        if sim.get('localizedData') and sim.get('localizedData').get(language):
            if sim.get('localizedData').get(language).get('runUrl'):
                run_url = sim.get('localizedData').get(language).get('runUrl')
            if sim.get('localizedData').get(language).get('title'):
                title = sim.get('localizedData').get(language).get('title')
            else:
                title = self.translator.translate(text=title)
        else:
            title = self.translator.translate(text=title)

        download_url = f'{BASE_URL_DOWNLOAD}{run_url}?download'
        print("\tProcessing sim:", title)
        dst = None
        if download_url not in dict_downloaded_paths:
            dst = tempfile.mkdtemp()
            dict_downloaded_paths[download_url] = {"dst": dst}
        if dst:
            download_file(
                download_url,
                dst,
                filename="index.html",
                request_fn=sess.get,
                middleware_callbacks=[process_sim_html],
            )

            zippath = create_predictable_zip(dst)
            dict_downloaded_paths.get(download_url).update({"zippath": zippath})

        authors = None
        if sim_detail_data.get("thanksTo"):
            authors = re.sub(" \(.*?\)", "", sim_detail_data["thanksTo"])
            authors = re.sub("<br\/?>", ", ", authors)

        if language == "ar":
            if title in ARABIC_NAME_CATEGORY:
                title = ARABIC_NAME_CATEGORY[title]
            if title in SIM_TYPO:
                title = SIM_TYPO[title]
        elif language == 'ht':
            if title in HAITIAN_NAME_CATEGORY:
                title = HAITIAN_NAME_CATEGORY[title]
        else:
            title = self.translator.translate(text=title)
        # get thumbnail image
        lst_sim_images = sim.get('defaultData').get('simImages')
        sim_image = lst_sim_images[0].get('url')
        for dict_image in lst_sim_images:
            if dict_image.get('width') == 128:
                sim_image = dict_image.get('url')
                break

        # create a node for the sim
        zippath = dict_downloaded_paths.get(download_url).get('zippath')
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
        if sim_detail_data.get('defaultData') and sim_detail_data.get('defaultData').get('simPrimerVimeoData'):
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
