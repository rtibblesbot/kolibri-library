#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import re
import requests
import tempfile

from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import HTMLZipFile, VideoFile
from ricecooker.classes.licenses import CC_BYLicense
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from ricecooker.utils.caching import FileCache
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip
from le_utils.constants import roles
from le_utils.constants.languages import getlang
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from deep_translator import GoogleTranslator
from metadata_tags import METADATA_BY_CAT

DEFAULT_LANG = 'en'
BASE_TITLE = "PhET Interactive Simulations"
BASE_SOURCE_ID = "phet-html5-simulations------testagain"

retry_strategy = Retry(
    total=5,
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)

sess = requests.Session()
cache = FileCache('.webcache')
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


class PhET(SushiChef):
    def __init__(self, *args, **kwargs):
        """
        The class is constructed with these defaults as it is meant to run
        initially in English only. This is because all sims are available in
        English and we will gather the other locales as we process them.

        TODO: Once the initial gathering of locale data is complete, it should
        be stored in a file to serve as a cache for future runs. Maybe a
        --skip-cache option could be watched for?
        """
        self.channel_name = BASE_TITLE
        self.channel_source_id = BASE_SOURCE_ID
        self.channel_domain = "phet.colorado.edu"
        self.channel_language = DEFAULT_LANG
        self.channel_thumbnail = 'chefdata/phet-logo-TM-partners.png'
        self.channel_description = CHANNEL_DESCRIPTIONS.get(self.channel_language)

        print("Running Language: ", self.channel_language)

        self.available_locales = set()
        self.downloaded_locales = set()

        super().__init__(PhET, *args, **kwargs)

    def _update_translators(self):
        self.translator = GoogleTranslator(
            source='auto', target=self.channel_language
        )
        self.lang_en_translator = GoogleTranslator(
            source=self.channel_language, target=self.channel_language
        )

    def run_with_locale(self, locale):
        """
        After the English chef completes, this method will be called to run another language.
        """
        # JP: Not sure why this is necessary but it was in the original code
        if locale == 'id':
            locale = 'in'

        # Setup channel info for new locale
        self.channel_name = self._localized_channel_title(locale)
        self.channel_source_id = self.channel_source_id + f'-{locale}'
        self.channel_language = locale

        # Setup translators for new locale
        self.translator = GoogleTranslator(
            source='auto', target=self.channel_language
        )
        self.lang_en_translator = GoogleTranslator(
            source=self.channel_language, target=DEFAULT_LANG
        )

        self.channel_description = CHANNEL_DESCRIPTIONS.get(
            locale,
            self.translator.translate(text=CHANNEL_DESCRIPTIONS.get(DEFAULT_LANG))  # Fallback to translator
        )

        # Run the chef again with the new locale
        self.main()

    def construct_channel(self, *args, **kwargs):
        channel = ChannelNode(
            source_domain=self.channel_domain,
            source_id=self.channel_source_id,
            title=self.channel_name,
            thumbnail=self.channel_thumbnail,
            description=self.channel_description,
            language=self.channel_language,
        )
        print("Constructed channel: ", self.channel_name)

        r_sim = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/simulations?locale={self.channel_language}")
        r_cat = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/categories")
        r_keyword = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/keywords?locale={self.channel_language}")

        sim_data = json.loads(r_sim.text)
        cat_data = json.loads(r_cat.text)
        keyword_data = json.loads(r_keyword.text)

        dict_downloaded_paths = {}

        self.download_category(
            parent=channel,
            cat_id="1",
            categories=cat_data,
            sims={sim["id"]: sim for sim in sim_data["simulations"]},
            keywords={keyword_data.get(key).get("id"): keyword_data.get(key)["strings"][self.channel_language] for key in
                      keyword_data if keyword_data.get(key)["strings"]},
            language=self.channel_language,
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
        if dict_cat_name.get(self.channel_language):
            cat_name = dict_cat_name.get(self.channel_language)
        elif dict_cat_name.get(DEFAULT_LANG):
            cat_name = dict_cat_name.get(DEFAULT_LANG)
        # loop through all subtopics and recursively add them
        # (reverse order seems to give most rational results)
        for child_id in reversed(cat["childrenIds"]):
            metadata = {}
            if METADATA_BY_CAT.get(child_id):
                metadata = METADATA_BY_CAT.get(child_id)
            # look up the child category by ID
            subcat = categories[str(child_id)]
            # skip it if it's in our blacklist
            if subcat["name"] in ID_BLACKLIST_BY_LANG.get(language, ID_BLACKLIST_BY_LANG.get(DEFAULT_LANG, [])):
                continue
            # make the title human-readable, and clean it up

            title = subcat['strings'].get(language)
            if not title:
                title = subcat["name"].replace("-", " ").title()
                title = title.replace(" And ", " and ")
                title = title.replace("Mathconcepts", "Concepts")
                title = title.replace("Mathapplications", "Applications")
            if language == DEFAULT_LANG:
                pass
            elif language == "ar":
                title = ARABIC_NAME_CATEGORY[title]
            elif language == 'ht':
                title = HAITIAN_NAME_CATEGORY[title]

            if metadata:
                subtopic = TopicNode(
                    source_id=subcat["name"],
                    title=title,
                    derive_thumbnail=True,
                    **metadata
                )
            else:
                subtopic = TopicNode(
                    source_id=subcat["name"],
                    title=title,
                    derive_thumbnail=True
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

        # When we're processing the English channel, we want to gather all the available locales
        if self.channel_language == DEFAULT_LANG:
            self.available_locales.update(sim_detail_data.get('availableLocales', []))

        description = None
        run_url = sim.get('defaultData').get('runUrl')
        # Ensure we're downloading the localized sim
        if run_url.endswith("_en.html") and language != DEFAULT_LANG:
            run_url = run_url.replace("_en.html", f"_{language}.html")
        title = sim.get('defaultData').get('title')
        description = sim.get('defaultData').get('description')

        if sim.get('localizedData') and sim.get('localizedData').get(language):
            if sim.get('localizedData').get(language).get('runUrl'):
                run_url = sim.get('localizedData').get(language).get('runUrl')
            if sim.get('localizedData').get(language).get('title'):
                title = sim.get('localizedData').get(language).get('title')
            if sim.get('localizedData').get(language).get('description'):
                description = sim.get('localizedData').get(language).get('description')
        elif self.channel_language != DEFAULT_LANG:
            if self.translator:
                title = self.translator.translate(text=title)
            if description:
                description = self.translator.translate(text=description)

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
                middleware_kwargs={ "sim_title": title },
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
        elif language != DEFAULT_LANG:
            if self.translator:
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
            description=description,
            license=CC_BYLicense("PhET Interactive Simulations, University of Colorado Boulder"),
            author=authors,
            # tags=[keywords[topic] for topic in sim["topicIds"]],
            thumbnail=sim_image,
            language=getlang(language),
            derive_thumbnail=True

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
                    derive_thumbnail=True
                )

                topic.add_child(videonode)

        # add the sim node into the topic
        topic.add_child(simnode)

    def _localized_channel_title(self, locale):
        if locale == 'ht':
            return "PhET (Kreyòl ayisyen)"
        return f'{BASE_TITLE} ({getlang(locale).native_name})'


def process_sim_html(content, destpath, **kwargs):
    """Remove various pieces of the code that make requests to online resources, to avoid using
    bandwidth for users expecting a fully offline or zero-rated website."""

    # remove "are we online" check
    content = content.replace("check:function(){var t=this", "check:function(){return;var t=this")

    # remove online links from "about" modal
    content = content.replace("getLinks:function(", "getLinks:function(){return [];},doNothing:function(")

    # setting up the query parameters for cases in which it works
    regex = r"(this\.getAllForString\([^,]+,[^w]*)(window\.location\.search)(\s*\))"
    replacement = r"\1window.location.search === '' ? '?allowLinks=false&disableFullscreen' : window.location.search\3"
    content = re.sub(regex, replacement, content)
    soup = BeautifulSoup(content, "html.parser")


    for script in soup.find_all("script"):
        # remove Google Analytics and online image bug requests
        if "analytics.js" in str(script):
            script.extract()

        if 'phetWebsite' in str(script):
            # remove menu options that link to online resources
            # fallbacks in case the above regex work fails
            script.string = re.compile('tandem: e.createTandem\(\"screenshotMenuItem\"\),').sub("", script.string)
            script.string = re.compile('tandem: e.createTandem\(\"fullScreenMenuItem\"\),').sub("", script.string)
            script.string = re.compile('string!JOIST/menuItem.reportAProblem').sub("", script.string)
            script.string = re.compile('string!JOIST/menuItem.phetWebsite').sub("", script.string)

    clean_title = kwargs.get("sim_title").replace(" ", "-").replace("'", "-")

    ##############
    # DEBUG HELP #
    ##############
    """
    Set your env var `DUMP_SIMS=true` when running the chef to have the resulting HTML files dumped
    to a `processed_sims` directory
    """
    if os.environ.get("DUMP_SIMS", False):

        # check if the processed_sims directory exists
        if not os.path.exists("processed_sims"):
            # create it if not
            os.makedirs("processed_sims")

        # Write's every sim's HTML to the directory
        # in a terminal, run: python -m http.server <port> to test sims in your browser
        with open("processed_sims/{}.html".format(clean_title), 'w') as f:
            f.write(str(soup))
            f.close()
    return str(soup)


if __name__ == '__main__':
    print('PhET chef started')
    phet_chef = PhET()
    phet_chef.main()
    def run_again():
        locale = phet_chef.available_locales.pop()
        try:
            if getlang(locale):
                phet_chef.run_with_locale(getlang(locale).primary_code)
            else:
                run_again()
        except KeyError:
            print("Processed all locales successfully.")
        except Exception as e:
            print(f"Error running with locale: '{locale}' ", e)
        finally:
            run_again()
    run_again()
