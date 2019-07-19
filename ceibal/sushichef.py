#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
from bs4 import BeautifulSoup
import subprocess
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages
# import cssutils
# import requests
# import re
# from urllib.parse import urlparse
# import youtube_dl
import zipfile
from ceibal_scrapers import CeibalPageScraper
# import tempfile
import shutil
# import json

# from pydrive.files import FileNotDownloadableError, ApiRequestError
# from pydrive.auth import GoogleAuth
# from pydrive.drive import GoogleDrive

# gauth = GoogleAuth()
# try:
#     gauth.DEFAULT_SETTINGS['client_config_file'] = "credentials.json"
#     gauth.LoadCredentialsFile("credentials.txt")
# except:
#     # Try to load saved client credentials
#     gauth.LoadClientConfigFile("credentials.json")
#     if gauth.credentials is None:
#         # Authenticate if they're not there
#         gauth.LocalWebserverAuth()
#     elif gauth.access_token_expired:
#         # Refresh them if expired
#         gauth.Refresh()
#     else:
#         # Initialize the saved creds
#         gauth.Authorize()
#     # Save the current credentials to a file
#     gauth.SaveCredentialsFile("credentials.txt")

# DRIVE = GoogleDrive(gauth)


# import logging
# cssutils.log.setLevel(logging.FATAL)
# Run constants
################################################################################
CHANNEL_NAME = "Ceibal"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-ceibal-es-test"    # Channel's unique id
CHANNEL_DOMAIN = "rea.ceibal.edu.uy"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = "El repositorio de Recursos educativos abiertos (REA) de Ceibal es una plataforma "\
                    "que alberga los REA construidos por los contenidistas de Ceibal "\
                    "y por la comunidad educativa; su misión no solamente es hacer de "\
                    "depósito, sino el ser un espacio para el intercambio de recursos y "\
                    "materiales pedagógicos facilitando la adaptación de estos y la interacción "\
                    "entre distintas comunidades de práctica."
CHANNEL_THUMBNAIL = "https://yt3.ggpht.com/a/AGF-l78Li2_W_X6fyV3lu6etxgfcFmb1xr73FCao6A=s900-mo-c-c0xffffffff-rj-k-no"

# Additional constants
################################################################################
BASE_URL = "https://rea.ceibal.edu.uy/"
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# VIDEO_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "videos"])
# if not os.path.exists(VIDEO_DIRECTORY):
#     os.makedirs(VIDEO_DIRECTORY)

# DRIVE_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "gdrive"])
# if not os.path.exists(DRIVE_DIRECTORY):
#     os.makedirs(DRIVE_DIRECTORY)

LICENSE_MAP = {
    'BY-NC': licenses.CC_BY_NCLicense,
    'BY-NC-SA':licenses.CC_BY_NC_SALicense,
    'BY': licenses.CC_BYLicense,
    'BY-SA': licenses.CC_BY_SALicense
}


# The chef subclass
################################################################################
class CeibalChef(SushiChef):
    """
    This class uploads the Ceibal channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }
    # Your chef subclass can override/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

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

        scrape_channel(channel)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel

def get_source_id(text):
    return "{}{}".format(BASE_URL, text.lstrip('/').lower().replace(' ', '_'))


def scrape_channel(channel):
    # Read from Categorias dropdown menu
    page = BeautifulSoup(downloader.read(BASE_URL), 'html5lib')
    dropdown = page.find('a', {'id': 'btn-categorias'}).find_next_sibling('ul')

    # Go through dropdown and generate topics and subtopics
    for category_list in dropdown.find_all('li', {'class': 'has-children'}):

        # Parse categories
        for category in category_list.find_all('li', {'class': 'has-children'}):
            # Add this topic to channel when scraping entire channel
            category_name = category.find('a').text
            topic = nodes.TopicNode(title=category_name, source_id=get_source_id(category_name))
            channel.add_child(topic)
            LOGGER.info(topic.title)

            # Parse subcategories
            for subcategory in category.find_all('li'):
                if not subcategory.attrs.get('class') or 'go-back' not in subcategory.attrs['class']:
                    # Get rid of this check to scrape entire site
                    subcategory_name = subcategory.find('a').text
                    subcategory_link = subcategory.find('a')['href']
                    LOGGER.info('  {}'.format(subcategory_name))
                    subtopic = nodes.TopicNode(title=subcategory_name, source_id=get_source_id(subcategory_link))
                    topic.add_child(subtopic)

                    # Parse resources
                    scrape_subcategory(subcategory_link, subtopic)


def scrape_subcategory(link, topic):
    url = "{}{}".format(BASE_URL, link.lstrip("/"))
    resource_page = BeautifulSoup(downloader.read(url), 'html5lib')

    # Skip "All" category
    for resource_filter in resource_page.find('div', {'class': 'menu-filtro'}).find_all('a')[1:]:
        LOGGER.info('    {}'.format(resource_filter.text))
        source_id = get_source_id('{}/{}'.format(topic.title, resource_filter.text))
        filter_topic = nodes.TopicNode(title=resource_filter.text, source_id=source_id)
        scrape_resource_list(url + resource_filter['href'], filter_topic)
        topic.add_child(filter_topic)

def scrape_resource_list(url, topic):
    resource_list_page = BeautifulSoup(downloader.read(url), 'html5lib')

    # Go through pages, omitting Previous and Next buttons
    for page in range(len(resource_list_page.find_all('a', {'class': 'page-link'})[1:-1])):
        # Use numbers instead of url as the links on the site are also broken
        resource_list = BeautifulSoup(downloader.read("{}&page={}".format(url, page + 1)), 'html5lib')
        for resource in resource_list.find_all('a', {'class': 'card-link'}):
            resource_file = scrape_resource(resource['href'], topic)


def scrape_resource(url, topic):
    resource = BeautifulSoup(downloader.read(url), 'html5lib')
    LOGGER.info('      {}'.format(resource.find('h2').text))

    filepath = download_resource(resource.find('div', {'class': 'decargas'}).find('a')['href'])
    license = None
    author = ''
    for data_section in resource.find('div', {'class': 'datos_generales'}).find_all('h4'):
        if 'Licencia' in data_section.text:
            try:
                license = LICENSE_MAP[data_section.find_next_sibling('p').text](copyright_holder="Ceibal")
            except KeyError as e:
                LOGGER.error(str(e))
                license = licenses.CC_BYLicense
        elif 'Autor' in data_section.text:
            author = data_section.find_next_sibling('p').text
    if filepath:
        thumbnail = resource.find('div', {'class': 'img-recurso'}).find('img')['src']
        if thumbnail.endswith('.gif'):
            thumbnail = os.path.sep.join([DOWNLOAD_DIRECTORY, thumbnail.split('/')[-1].replace('.gif', '.png')])
            with open(thumbnail, 'wb') as fobj:
                fobj.write(downloader.read(resource.find('div', {'class': 'img-recurso'}).find('img')['src']))

        topic.add_child(nodes.HTML5AppNode(
            title=resource.find('h2').text,
            source_id=url,
            license=license,
            author=author,
            description=resource.find('form').find_all('p')[1].text,
            thumbnail=thumbnail,
            tags = [tag.text[:30] for tag in resource.find_all('a', {'class': 'tags'})],
            files=[files.HTMLZipFile(path=filepath)],
        ))

def download_resource(endpoint):
    filename, ext = os.path.splitext(endpoint)
    write_to_path = os.path.sep.join([DOWNLOAD_DIRECTORY, '{}.zip'.format(filename.lstrip('/').replace('/', '-'))])

    # if os.path.isfile(write_to_path):
    #     return write_to_path
    try:
        url = '{}{}'.format(BASE_URL, endpoint.lstrip('/'))
        contents = BeautifulSoup(downloader.read(url), 'html5lib')
        with html_writer.HTMLWriter(write_to_path) as zipper:
            # write_zip_page(url, contents, zipper)
            CeibalPageScraper(url, zipper, locale='es').process()
        return write_to_path
    except Exception as e:
        LOGGER.error(str(e))


def test_page(url, filename=None):
    contents = BeautifulSoup(downloader.read(url), 'html5lib')
    filename = filename or url.split('/')[-2].split('?')[0]
    write_to_path = os.path.sep.join([DOWNLOAD_DIRECTORY, '{}.zip'.format(filename.lstrip('/').replace('/', '-'))])
    with html_writer.HTMLWriter(write_to_path) as zipper:
        CeibalPageScraper(url, zipper, locale='en').process()

    extract_to_path = os.path.join(DOWNLOAD_DIRECTORY, filename.lstrip('/').replace('/', '-'))
    if os.path.exists(extract_to_path):
        shutil.rmtree(extract_to_path)

    with zipfile.ZipFile(write_to_path, 'r') as zipf:
        zipf.extractall(extract_to_path)
    print("Extracted at {}".format(write_to_path))


# CLI
################################################################################
import time
if __name__ == '__main__':
    print("********** STARTING **********")
    start = time.time()
    # This code runs when sushichef.py is called from the command line

    for test in [
    'actividad_el_procesamiento_del_lenguaje',
    # 'en_la_agenda_e_participaci_n_ciudadana',
    # '-rumbo-a-los-humedales'
        # 'los-esquemas',
    #     # 'actividad-de-la-unidad-c-mo-se-alimentan-los-seres-vivos',
    #     # 'la-luna-y-los-amigos',
    #     # 'seres-vivos-en-accion',
    #     # 'de-pajaros-y-huevos',
    #     # 'la_fecundaci_n_una_uni_n_que_trae_vida',
    #     # 'un-a-o-dedicado-a-la-luz-para-salir-de-las-sombras',
    #     # 'la-pesca-en-uruguay',
    #     # 'el-derecho-de-autor-protege-tus-creaciones',
    #     # '-c-mo-se-hace-e-portafolios',
    #     # '-c-mo-se-hace-e-portafolios',
    #     # 'de_fiesta_tradicional_y_uruguaya',
    #     # 'un-n-mero-en-7-000-millones',
    #     # 'el-hombre-que-quer-a-saberlo-todo',
    #     # 'noticia-alcanz-la-fama-hace-m-s-de-400-a-os',
    #     # 'juan_carlos_onetti',
    #     # 'la-murga-g-nero-popular-ciudadano',
    #     # 'en-el-m-gico-mundo-de-las-matem-ticas',
    #     # 'magia-matem-tica',
    #     # 'ecuaciones-de-segundo-grado',
    #     # 'e-propuesta-poliedros-a-trav-s-de-videolecciones',
    #     # 'que-es-una-teselacion',
    #     # 'estad-stica',
    #     # 'e-propuesta-lo-que-el-viento-se-llev',
    #     # '-c-mo-se-hace-videos',
    #     # 'como-se-hace-podcast',
    #     # 'a-trabajar-con-scratch',
    #     # 'e-propuesta-lo-que-el-viento-se-llev',
    #     # '-c-mo-se-hace-videos',
    #     # 'como-se-hace-podcast',
    ]:
        print(test)
        test_page('https://rea.ceibal.edu.uy/elp/{}/inicio'.format(test), 'test-elp-{}-inicio'.format(test))
    # chef = CeibalChef()
    # chef.main()

    print("FINISHED: {}".format(time.time() - start))

# BASIC_SITES = {
#     BASE_URL: {
#         'omit_list': [
#             ('p', {'id': 'nav-toggler'}),
#             ('nav', {'id': 'siteNav'}),
#         ]
#     },
#     'disfrutalasmatematicas.com': {
#         'omit_list': [
#             ('div', {'id': 'topads'}),
#             ('div', {'id': 'adhid2'}),
#             ('div', {'id': 'menu'}),
#             ('div', {'id': 'header'}),
#             ('div', {'class': 'related'}),
#             ('div', {'id': 'footer'}),
#             ('div', {'id': 'foot-menu'}),
#             ('div', {'id': 'cookieok'}),
#         ]
#     },
#     'wikipedia': {
#         'omit_list': [
#             ('span', {'class': 'mw-editsection'}),
#             ('div', {'id': 'mw-page-base'}),
#             ('div', {'id': 'mw-head-base'}),
#             ('div', {'id': 'mw-navigation'}),
#             ('div', {'id': 'footer'}),
#             ('a', {'class': 'mw-jump-link'}),
#             ('link', {'rel': 'apple-touch-icon'}),
#             ('link', {'rel': 'icon'}),
#             ('link', {'rel': 'search'}),
#             ('div', {'class': 'printfooter'}),
#         ]
#     },
#     'wikibooks': {
#         'omit_list': [
#             ('span', {'class': 'mw-editsection'}),
#             ('div', {'id': 'mw-page-base'}),
#             ('div', {'id': 'mw-head-base'}),
#             ('div', {'id': 'mw-navigation'}),
#             ('div', {'id': 'footer'}),
#             ('a', {'class': 'mw-jump-link'}),
#             ('link', {'rel': 'apple-touch-icon'}),
#             ('link', {'rel': 'icon'}),
#             ('link', {'rel': 'search'}),
#             ('div', {'class': 'printfooter'}),
#         ]
#     },
#     'impo.com.uy': {
#         'omit_list': [
#             ('nav', {'id': 'topnavbar'})
#         ]
#     },
#     'www.geoenciclopedia.com': {
#         'omit_list': [
#             ('header', {'id': 'main-header'}),
#             ('div', {'class': 'et_pb_widget_area_right'}),
#             ('footer', {'id': 'main-footer'})
#         ]
#     },
#     'ciudadseva.com': {
#         'omit_list': [
#             ('div', {'class': 'container'}),
#             ('nav', {'class': 'navbar-maqin'}),
#             ('div', {'class': 'hidden-print'})
#         ]
#     },
#     'www.literatura.us': {
#         'omit_list': [
#             ('a', {})
#         ]
#     },
#     'infoymate.es': {
#         'omit_list': []
#     },
#     'edu.xunta.es': {
#         'omit_list': []
#     },
#     'www.uoc.edu': {
#         'omit_list': [
#             ('div', {'class': 'alert-text'}),
#             ('div', {'id': 'eines'})
#         ]
#     },
#     'contenidos.ceibal.edu.uy': {
#         'omit_list': [
#             ('ul', {'id': 'mainMenu'}),
#             ('div', {'class': 'button'}),
#             ('div', {'id': 'related'}),
#         ]
#     }
# }

#     # Get iframe embeds
#     for iframe in contents.find_all('iframe'):
#         elif re.match(r'https://[^\.]+.google.com/.*file/d/[^/]+/(?:preview|edit)', iframe['src']):
#             download_google_drive_file(iframe, zipper)
#         elif 'genial.ly' in iframe['src']:
#             def preprocess_genial(url, contents, zipper):
#                 genial_id = url.split('/')[-1]
#                 response = requests.get('https://view.genial.ly/api/view/{}'.format(genial_id))
#                 for script in contents.find_all('script'):
#                     if script.get('src') and 'main' in script['src']:
#                         script_contents = downloader.read(get_relative_url(script['src'], script['src'])).decode('utf-8')
#                         genial_data = json.loads(response.content)

#                         if len(genial_data['Videos']) or len(genial_data['Audios']):
#                             LOGGER.error('Unhandled genial.ly video or audio at {}'.format(url))

#                         if genial_data['Genially']['ImageRender']:
#                             genial_data['Genially']['ImageRender'] = zipper.write_url(genial_data['Genially']['ImageRender'], genial_data['Genially']['ImageRender'].split('?')[0].split('/')[-1], directory='webimg')
#                         for image in genial_data['Images']:
#                             image['Source'] = zipper.write_url(image['Source'], '-'.join(image['Source'].split('?')[0].split('/')[-3:]), directory='webimg')
#                         for slide in genial_data['Slides']:
#                             slide['Background'] = zipper.write_url(slide['Background'], '-'.join(slide['Background'].split('?')[0].split('/')[-3:]), directory='webimg')
#                         for code in genial_data['Contents']:
#                             code_contents = BeautifulSoup(code['HtmlCode'], 'html.parser')
#                             for img in code_contents.find_all('img'):
#                                 image_filename = '-'.join(img['src'].split('?')[0].split('/')[-3:])
#                                 image_filename = image_filename if os.path.splitext(image_filename) else '.{}'.format(image_filename)
#                                 try:
#                                     img['src'] = zipper.write_url(img['src'], image_filename, directory="webimg")
#                                 except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
#                                     LOGGER.warning("Error processing genial.ly at {} ({})".format(url, str(e)))
#                             code['HtmlCode'] = code_contents.prettify()
#                         script_contents = script_contents.replace('r.a.get(c).then(function(e){return n(e.data)})', 'n({})'.format(json.dumps(genial_data)))
#                         script['class'] = ['skip-scrape']
#                         script['src'] = zipper.write_contents('genial-{}-embed.js'.format(genial_id), script_contents,  directory="js")
#                 new_soup = BeautifulSoup('<div></div>', 'html5lib')
#                 style_tag = new_soup.new_tag('style')
#                 style_tag.string = '.genially-view-logo { pointer-events: none;} .genially-view-navigation-actions, .genially-view-navigation-actions-toggle-button{display: none !important; pointer-events:none;}'
#                 contents.find('head').append(style_tag)
#             download_webpage(iframe, zipper, pre_process=preprocess_genial)
#         elif 'easel.ly' in iframe['src']:
#             page_contents = BeautifulSoup(downloader.read(iframe['src']), 'html5lib')
#             new_soup = BeautifulSoup('<div></div>', 'html5lib')
#             image = new_soup.new_tag('img')
#             easel = page_contents.find('div', {'id': 'easelly-frame'}).find('img')
#             easelname = '-'.join(easel['src'].split('?')[0].split('/')[-3:])[-20:]
#             image['src'] = zipper.write_url(easel['src'], easelname, directory='webimg')
#             iframe.replaceWith(image)
#         elif 'wevideo.com' in iframe['src']:
#             video_id = iframe['src'].split('#')[1]
#             new_soup = BeautifulSoup('<div></div>', 'html5lib')
#             video_tag = new_soup.new_tag('video')
#             video_tag['controls'] = 'controls'
#             video_tag['src'] = zipper.write_url('https://www.wevideo.com/api/2/media/{}/content'.format(video_id), 'wevideo-{}.mp4'.format(video_id), directory="videos")
#             iframe.replaceWith(video_tag)
#         elif 'ivoox.com' in iframe['src']:
#             new_soup = BeautifulSoup('<div></div>', 'html5lib')
#             audio_id = re.search(r'(?:player_ek_)([^_]+)(?:_2_1\.html)', iframe['src']).group(1)
#             audio_tag = new_soup.new_tag('audio')
#             audio_tag['controls'] = 'controls'
#             audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
#             source_tag = new_soup.new_tag('source')
#             audio_tag.append(source_tag)
#             source_tag['src'] = zipper.write_url('http://www.ivoox.com/listenembeded_mn_{}_1.m4a?source=EMBEDEDHTML5'.format(audio_id), 'ivoox-{}.m4a'.format(audio_id), directory="videos")
#             iframe.replaceWith(audio_tag)
#         elif 'soundcloud' in iframe['src'] and 'search?' not in iframe['src']:
#             download_soundcloud(iframe, zipper)
#         elif 'educaplay.com' in iframe['src']:
#             def preprocess_educaplay(page_url, contents, zipper):
#                 for script in contents.find_all('script'):
#                     if script.get('src') and 'xapiEventos.js' in script['src']:
#                         script_contents = downloader.read(get_relative_url(page_url, script['src'])).decode('utf-8')
#                         script_contents = script_contents.replace('img.src=rutaRecursos+imagen;', 'img.src = "img/" + imagen;');
#                         script_contents = script_contents.replace('/snd_html5/', 'audio/-snd_html5-')
#                         script['class'] = ['skip-scrape']
#                         script['src'] = zipper.write_contents('educaplay-embed.js', script_contents,  directory="js")
#             def post_process_educaplay(page_contents, page_url, zipper):
#                 new_soup = BeautifulSoup('', 'html5lib')
#                 style_tag = new_soup.new_tag('style')
#                 style_tag.string = '#banner { display: none !important; }'
#                 page_contents.head.append(style_tag)
#                 for audio in page_contents.find_all('audio'):
#                     for source in audio.find_all('source'):
#                         source['src'] = zipper.write_url(get_relative_url(page_url, source['src']), '-'.join(source['src'].split('?')[0].split('/')[-3:]), directory="audio")
#             download_webpage(iframe, zipper, pre_process=preprocess_educaplay, post_process=post_process_educaplay, omit_list=[('ins', {'class': 'adsbygoogle'})], loadjs=True)
#         elif 'recursostic.educacion.es' in iframe['src'] or 'recursos.cnice.mec.es' in iframe['src']:
#             def post_process_recursostic(page_contents, page_url, zipper):
#                 for script in page_contents.find_all('script'):
#                     if script.string:
#                         script.string = script.text.replace('background="HalfBakedBG.gif"', '')
#                         for match in re.finditer(r'(?:src)=(?:\'|\")([^\'\"]+)(?:\'|\")', script.string, re.MULTILINE):
#                             img_filename = match.group(1).split('?')[0].split('/')[-1][-20:]
#                             script.string = script.text.replace(match.group(1), zipper.write_url(get_relative_url(page_url, match.group(1)), img_filename, directory="webimg"))
#                         for match in re.finditer(r"onclick=\\(?:'|\")parent\.location\s*=\s*(?:'|\")([^'\"]+)(?:'|\")", script.string, re.MULTILINE):
#                             page_filename = 'recursostic-{}'.format(match.group(1).split('?')[0].split('/')[-1])
#                             page = BeautifulSoup(downloader.read(get_relative_url(page_url, match.group(1))), 'html5lib')
#                             page_link = write_zip_page(get_relative_url(page_url, match.group(1)), page, zipper, filename=page_filename, scrape_subpages=False, post_process=post_process_recursostic)
#                             script.string = script.text.replace(match.group(1), page_link)
#             download_webpage(iframe, zipper, post_process=post_process_recursostic)
#         else:
#             match_found = False
#             for (source_url, source_settings) in BASIC_SITES.items():
#                 if source_url in iframe['src']:
#                     try:
#                         download_webpage(iframe, zipper, omit_list=source_settings['omit_list'], scrape_subpages=source_settings.get('scrape_subpages'), loadjs=source_settings.get('loadjs'))
#                         match_found = True
#                     except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
#                         LOGGER.warn('Broken webpage at {} ({}: {})'.format(url, iframe['src'], str(e)))
#                     break
#             if not match_found:
#                 message.decompose()
#                 iframe.replaceWith(manage_unrecognized_source(url, iframe['src']))

# def download_youtube(url, zipper):
#     video_id = url.split('/')[-1].replace('?', '-')
#     video_path = os.path.join(VIDEO_DIRECTORY, '{}.mp4'.format(video_id))
#     dl_settings = {
#         'outtmpl': video_path,
#         'quiet': True,
#         'overwrite': True,
#         'format': "mp4",
#     }
#     if not os.path.exists(video_path):
#         with youtube_dl.YoutubeDL(dl_settings) as ydl:
#             ydl.download([url])

#     try:
#         return zipper.write_file(video_path, os.path.basename(video_path), directory="videos")
#     except Exception as e:
#         LOGGER.warning('Unable to download video {}'.format(url))
#         raise youtube_dl.utils.DownloadError('Unable to download video {}'.format(url))

# def download_soundcloud(iframe, zipper):
#     new_soup = BeautifulSoup('<div></div>', 'html5lib')
#     # Get image if there is one
#     contents = BeautifulSoup(downloader.read(iframe['src'], loadjs=True), 'html5lib')
#     image = contents.find('div', {'class': 'sc-artwork'})
#     if image:
#         url = re.search(r'background-image:url\(([^\)]+)\)', image.find('span')['style']).group(1)
#         img = new_soup.new_tag('img')
#         img['src'] = zipper.write_url(get_relative_url(url, url), url.split('?')[0].split('/')[-1][-20:], directory='webimg')
#         img['style'] = 'width:300px;'
#         iframe.insert_before(img)


#     if 'playlists' in iframe['src']:
#         iframe.replaceWith(manage_unrecognized_source(iframe['src'], iframe['src']))
#         return

#     try:
#         audio_id = re.search(r'tracks(?:/|%2F)([^\&]*)\&', iframe['src']).group(1).replace('%', '')
#         audio_path = os.path.join(VIDEO_DIRECTORY, '{}.mp3'.format(audio_id))
#         dl_settings = {
#             'outtmpl': audio_path,
#             'quiet': True,
#             'overwrite': True,
#             'format': "bestaudio[ext=mp3]",
#         }
#         if not os.path.exists(audio_path):
#             with youtube_dl.YoutubeDL(dl_settings) as ydl:
#                 ydl.download([iframe['src']])


#         audio_tag = new_soup.new_tag('audio')
#         audio_tag['controls'] = 'controls'
#         audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
#         source_tag = new_soup.new_tag('source')
#         source_tag['src'] = zipper.write_file(audio_path, directory="audios")
#         audio_tag.append(source_tag)
#         iframe.replaceWith(audio_tag)

#     except (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError) as e:
#         LOGGER.error(str(e))
#         iframe.replaceWith(manage_unrecognized_source(iframe['src'], iframe['src']))


# def download_google_drive_file(iframe, zipper):
#     try:
#         new_soup = BeautifulSoup('<div></div>', 'html5lib')
#         file_id = re.search(r'https://[^\.]+.google.com/.*file/d/([^/]+)/(?:preview|edit)', iframe['src']).group(1)
#         drive_file = DRIVE.CreateFile({'id': file_id})
#         _drivename, ext = os.path.splitext(drive_file['title'])
#         filename = '{}{}'.format(file_id, ext)

#         write_to_path = os.path.join(DRIVE_DIRECTORY, filename);
#         if not os.path.exists(write_to_path):
#             drive_file.GetContentFile(write_to_path)

#         if ext.endswith('pdf'):
#             embed_tag = new_soup.new_tag('embed')
#             embed_tag['style'] = 'width: 100vw;min-height: 500px;'
#             embed_tag['src'] = zipper.write_file(write_to_path, filename, directory="src")
#             iframe.replaceWith(embed_tag)
#         elif ext.endswith('png') or ext.endswith('jpg'):
#             img_tag = new_soup.new_tag('img')
#             img_tag['src'] = zipper.write_file(write_to_path, filename[-20:], directory="img")
#             iframe.replaceWith(img_tag)
#         else:
#             LOGGER.error('New google drive file type', iframe['src'])
#     except (FileNotDownloadableError, ApiRequestError) as e:
#         LOGGER.error('Unable to download {} ({})'.format(iframe['src'], str(e)))
#         iframe.replaceWith(manage_unscrapable_source(iframe['src']))
