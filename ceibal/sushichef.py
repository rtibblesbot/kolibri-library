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
import cssutils
import requests
import re
from urllib.parse import urlparse
import youtube_dl
import zipfile
from pressurecooker.videos import compress_video
import tempfile
import shutil
import json

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

gauth = GoogleAuth()
try:
    gauth.DEFAULT_SETTINGS['client_config_file'] = "credentials.json"
    gauth.LoadCredentialsFile("credentials.txt")
except:
    # Try to load saved client credentials
    gauth.LoadClientConfigFile("credentials.json")
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Refresh them if expired
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile("credentials.txt")

DRIVE = GoogleDrive(gauth)


import logging
cssutils.log.setLevel(logging.FATAL)
# Run constants
################################################################################
CHANNEL_NAME = "Ceibal"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-ceibal-es"    # Channel's unique id
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

VIDEO_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "videos"])
if not os.path.exists(VIDEO_DIRECTORY):
    os.makedirs(VIDEO_DIRECTORY)

DRIVE_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "gdrive"])
if not os.path.exists(DRIVE_DIRECTORY):
    os.makedirs(DRIVE_DIRECTORY)

# Determines which topics to scrape. In case we decide to scrape the whole channel,
# we can just get rid of the logic around this
TOPICS_TO_INCLUDE = ['educacion_socio_emocional', 'comunicacion_y_tecnologia']
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

        LOGGER.info('Scraping Ceibal channel...')

        self.scrape_channel(channel)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction
        LOGGER.info('DONE')
        # raise KeyError

        return channel

    def scrape_channel(self, channel):
        # Read from Categorias dropdown menu
        page = BeautifulSoup(downloader.read(BASE_URL), 'html5lib')
        dropdown = page.find('a', {'id': 'btn-categorias'}).find_next_sibling('ul')

        # Go through dropdown and generate topics and subtopics
        for category_list in dropdown.find_all('li', {'class': 'has-children'}):

            # Parse categories
            for category in category_list.find_all('li', {'class': 'has-children'}):
                # Add this topic to channel when scraping entire channel
                # category_name = category.find('a').string
                # topic = nodes.TopicNode(title=category_name, source_id=get_source_id(category_name))
                # channel.add_child(topic)
                # LOGGER.info(topic.title)

                # Parse subcategories
                for subcategory in category.find_all('li'):
                    if not subcategory.attrs.get('class') or 'go-back' not in subcategory.attrs['class']:
                        # Get rid of this check to scrape entire site
                        # if subcategory.find('a')['href'].split('/')[-1] in TOPICS_TO_INCLUDE:
                        subcategory_name = subcategory.find('a').string
                        subcategory_link = subcategory.find('a')['href']
                        LOGGER.info('  {}'.format(subcategory_name))
                        subtopic = nodes.TopicNode(title=subcategory_name, source_id=get_source_id(subcategory_link))
                        channel.add_child(subtopic)

                        # Parse resources
                        self.scrape_subcategory(subcategory_link, subtopic)


    def scrape_subcategory(self, link, topic):
        url = "{}{}".format(BASE_URL, link.lstrip("/"))
        resource_page = BeautifulSoup(downloader.read(url), 'html5lib')

        # Skip "All" category
        for resource_filter in resource_page.find('div', {'class': 'menu-filtro'}).find_all('a')[1:]:
            LOGGER.info('    {}'.format(resource_filter.string))
            source_id = get_source_id('{}/{}'.format(topic.title, resource_filter.string))
            filter_topic = nodes.TopicNode(title=resource_filter.string, source_id=source_id)
            self.scrape_resource_list(url + resource_filter['href'], filter_topic)
            topic.add_child(filter_topic)

    def scrape_resource_list(self, url, topic):
        resource_list_page = BeautifulSoup(downloader.read(url), 'html5lib')

        # Go through pages, omitting Previous and Next buttons
        for page in range(len(resource_list_page.find_all('a', {'class': 'page-link'})[1:-1])):
            # Use numbers instead of url as the links on the site are also broken
            resource_list = BeautifulSoup(downloader.read("{}&page={}".format(url, page + 1)), 'html5lib')
            for resource in resource_list.find_all('a', {'class': 'card-link'}):
                resource_file = self.scrape_resource(resource['href'], topic)


    def scrape_resource(self, url, topic):
        resource = BeautifulSoup(downloader.read(url), 'html5lib')
        LOGGER.info('      {}'.format(resource.find('h2').string))
        if 'en_la_agenda_e_participaci_n_ciudadana' not in url:
            return

        filepath = self.download_resource(resource.find('div', {'class': 'decargas'}).find('a')['href'])
        license = None
        author = ''
        for data_section in resource.find('div', {'class': 'datos_generales'}).find_all('h4'):
            if 'Licencia' in data_section.string:
                try:
                    license = LICENSE_MAP[data_section.find_next_sibling('p').string](copyright_holder="Ceibal")
                except KeyError as e:
                    LOGGER.error(str(e))
                    license = licenses.CC_BYLicense
            elif 'Autor' in data_section.string:
                author = data_section.find_next_sibling('p').string
        if filepath:
            topic.add_child(nodes.HTML5AppNode(
                title=resource.find('h2').string,
                source_id=url,
                license=license,
                author=author,
                description=resource.find('form').find_all('p')[1].string,
                thumbnail=resource.find('div', {'class': 'img-recurso'}).find('img')['src'],
                tags = [tag.string for tag in resource.find_all('a', {'class': 'tags'})],
                files=[files.HTMLZipFile(path=filepath)],
            ))
        raise KeyError

    def download_resource(self, endpoint):
        url = '{}{}'.format(BASE_URL, endpoint.lstrip('/'))
        # try:
        contents = BeautifulSoup(downloader.read(url), 'html5lib')

        filename, ext = os.path.splitext(endpoint)
        write_to_path = os.path.sep.join([DOWNLOAD_DIRECTORY, '{}.zip'.format(filename.lstrip('/').replace('/', '-'))])

        # if not os.path.isfile(write_to_path):
        # return None
        with html_writer.HTMLWriter(write_to_path) as zipper:
            try:
                write_zip_page(url, contents, zipper)
            except Exception as e:
                print(str(e))
                import pdb; pdb.set_trace()

        with zipfile.ZipFile(write_to_path, 'r') as zipf:
            zipf.extractall(os.path.join(DOWNLOAD_DIRECTORY, filename.lstrip('/').replace('/', '-')))

        return write_to_path
        # except Exception as e:
        #     LOGGER.error(str(e))
            # import pdb; pdb.set_trace()


def test_page(url):
    contents = BeautifulSoup(downloader.read(url), 'html5lib')
    filename = url.split('/')[-2].split('?')[0]
    write_to_path = os.path.sep.join([DOWNLOAD_DIRECTORY, '{}.zip'.format(filename.lstrip('/').replace('/', '-'))])
    with html_writer.HTMLWriter(write_to_path) as zipper:
        write_zip_page(url, contents, zipper)

    extract_to_path = os.path.join(DOWNLOAD_DIRECTORY, filename.lstrip('/').replace('/', '-'))
    if os.path.exists(extract_to_path):
        shutil.rmtree(extract_to_path)

    with zipfile.ZipFile(write_to_path, 'r') as zipf:
        zipf.extractall(extract_to_path)
    print("Extracted at {}".format(extract_to_path))




def get_relative_url(url, endpoint):
    endpoint = endpoint.replace('%20', ' ').strip()
    if endpoint.strip().startswith('http'):
        return endpoint
    elif endpoint.startswith('//'):
        return 'https:{}'.format(endpoint)
    elif '../' in endpoint:
        jumps = len(list(section for section in endpoint.split('/') if section == '..'))
        url_sections = url.split('/')[:-(jumps + 1)] + endpoint.split('/')[jumps:]
        return '{}'.format('/'.join(url_sections))
    elif endpoint.startswith('/'):
        parsed = urlparse(url)
        return "{}://{}/{}".format(parsed.scheme, parsed.netloc, endpoint.strip('/'))
    return "/".join(url.split('/')[:-1] + [endpoint])


def write_zip_page(url, contents, zipper, filename="index.html", triaged=None, scrape_subpages=True, omit_list=None, pre_process=None, post_process=None):
    if pre_process:
        pre_process(url, contents, zipper)
    triaged = triaged or []
    omit_list = omit_list or []
    omit_list += [
        ('link', {'type': 'image/x-icon'}),
        ('link', {'rel': 'apple-touch-icon'}),
        ('span', {'class': 'external-iframe-src'}),
        ('a', {'class': 'genially-view-logo'}),
        ('div', {'class': 'genially-view-navigation-actions-container'}),  # Genial sources
    ]
    for item in omit_list:
        for element in contents.find_all(*item):
            element.decompose()

    for header in contents.find_all('div', {'class': 'iDevice_header'}) + contents.find_all('header', {'class': 'iDevice_header'}):
        header['style'] = "min-height: 25px;"

    for video in contents.find_all('div', {'class': 'mejs-video'}):
        try:
            new_soup = BeautifulSoup('<div></div>', 'html5lib')
            video_tag = new_soup.new_tag('video')
            video_tag['style'] = 'margin-left: auto; margin-right: auto; width: 500px;'
            video_tag['preload'] = 'auto'
            for source in video.find_all('source'):
                source_tag = new_soup.new_tag('source')
                source_tag['src'] = zipper.write_url(get_relative_url(url, source['src']), source['src'].split('/')[-1], directory="videos")
                video_tag.append(source_tag)
            video.replaceWith(video_tag)
        except:
            LOGGER.warn('Cannot parse video at {}'.format(url.replace('inicio', filename)))

    for audio in contents.find_all('div', {'class': 'mejs-audio'}):
        new_soup = BeautifulSoup('<div></div>', 'html5lib')
        try:
            audio_tag = new_soup.new_tag('audio')
            audio_tag['controls'] = 'controls'
            audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
            source_tag = new_soup.new_tag('source')
            audio_tag.append(source_tag)
            source['src'] = zipper.write_url(get_relative_url(url, audio.find('audio')['src']), audio.find('audio')['src'].split('/')[-1], directory="audio")
            audio.replaceWith(audio_tag)
        except:
            LOGGER.warn('Cannot parse video at {}'.format(url.replace('inicio', filename)))

    # Get style sheets
    for style in contents.find_all('link', {'rel': 'stylesheet'}):
        if 'fonts' in style['href']:  # Omit google fonts
            continue
        try:
            style_url = get_relative_url(url, style['href'])
            css_link = style['href'].split('/')[-1].split('?')
            style_sheet = downloader.read(style_url).decode('utf-8')

            # Parse urls in css
            if style_url not in triaged:
                triaged.append(style_url)
                sheet = cssutils.parseString(style_sheet)  # parseString is significantly faster than parseUrl
                for css_url in cssutils.getUrls(sheet):
                    if not css_url.startswith('data:image'):
                        try:
                            new_url = zipper.write_url(get_relative_url(style_url, css_url), css_url.split('/')[-1].split('?')[0], directory="css")
                            style_sheet = style_sheet.replace(css_url, os.path.basename(new_url))
                        except requests.exceptions.HTTPError as e:
                            LOGGER.warn('Unable to download stylesheet link at {} ({})'.format(url, str(e)))

            style['href'] = zipper.write_contents(css_link[0], style_sheet, directory="css")
            style['href'] += '?' + css_link[1] if len(css_link) > 1 else ''
        except requests.exceptions.HTTPError as e:
            LOGGER.warn('Unable to download stylesheet link at {} ({})'.format(url, str(e)))


    # Get scripts
    for script in contents.find_all('script'):
        if 'skip-scrape' in (script.get('class') or ''):
            continue
        elif script.get('src') and ('google' in script['src'] or 'load.php' in script['src']):
            script.decompose()
        elif script.get('src'):
            script_url = get_relative_url(url, script['src'])
            script_link = script['src'].split('/')[-1].split('?')
            script['src'] = zipper.write_url(script_url, script_link[0], directory="js")
            script['src'] += '?' + script_link[1] if len(script_link) > 1 else ''
        elif 'gtag()' in script.string or 'googletagmanager' in script.string:
            script.decompose()

    # Get images
    for img in contents.find_all('img'):
        if 'skip-scrape' not in (img.get('class') or []) and img.get('src') and not img['src'].startswith('data:image'):
            image_filename = img['src'].split('/')[-1].split('?')[0]
            _fn, ext = os.path.splitext(image_filename)
            if not ext:
                image_filename += '.png'
            img_url = get_relative_url(url, img['src'])
            img['src'] = zipper.write_url(img_url, image_filename, directory="img")


    # Get links
    for link in contents.find_all('a') :
        if not link.get('href'):
            continue
        elif 'javascript:void' in link.get('href') or link['href'].startswith("#"):
            continue
        elif link['href'].endswith('.webm') or link['href'].endswith('.mp4'):
            new_soup = BeautifulSoup('<div></div>', 'html5lib')
            video_tag = new_soup.new_tag('video')
            video_tag['controls'] = 'controls'
            source_tag = new_soup.new_tag('source')
            video_tag.append(source_tag)
            source_tag['src'] = zipper.write_url(get_relative_url(url, link['href']), link['href'].split('/')[-1], directory="videos")
            link.replaceWith(video_tag)
        elif not link['href'].endswith('.html') and not link['href'].endswith('.htm') and os.path.splitext(link['href'])[1] and 'index.php' not in link['href']:
            try:
                link['href'] = zipper.write_url(get_relative_url(url, link['href']), link['href'].split('/')[-1])
            except requests.exceptions.HTTPError as e:
                LOGGER.warn('Resourece not found at {} ({})'.format(url, str(e)))
        elif not scrape_subpages:
            link.replaceWith(link.text)
            link['style'] = 'font-weight: bold;'
        elif link['href'].startswith("http") or 'mailto' in link['href']:
            link.replaceWith(link.text + " ({})".format(link['href']))
        elif link['href'].split('#')[0] not in triaged:
            parts = link['href'].split('#')
            triaged.append(parts[0])
            page = BeautifulSoup(downloader.read(get_relative_url(url, parts[0])), 'html5lib')
            link['href'] = write_zip_page(url, page, zipper, filename=parts[0], triaged=triaged)
            if len(parts) > 1:
                link['href'] += '#' + parts[1]

    # Get iframe embeds
    for iframe in contents.find_all('iframe'):
        if 'youtube' in iframe['src'] or 'vimeo' in iframe['src']:
            download_web_video(iframe, zipper)
        elif re.match(r'https://[^\.]+.google.com/file/d/[^/]+/preview', iframe['src']):
            download_google_drive_file(iframe, zipper)
        elif iframe['src'].endswith('.pdf'):
            download_pdf(iframe, zipper)
        elif 'view.genial.ly' in iframe['src']:
            download_webpage(iframe, zipper)
        elif 'wikipedia' in iframe['src'] or 'wikibooks' in iframe['src']:
            omit_list = [
                ('span', {'class': 'mw-editsection'}),
                ('div', {'id': 'mw-page-base'}),
                ('div', {'id': 'mw-head-base'}),
                ('div', {'id': 'mw-navigation'}),
                ('div', {'id': 'footer'}),
                ('a', {'class': 'mw-jump-link'}),
                ('link', {'rel': 'apple-touch-icon'}),
                ('link', {'rel': 'icon'}),
                ('link', {'rel': 'search'}),
                ('div', {'class': 'printfooter'}),
            ]
            download_webpage(iframe, zipper, omit_list=omit_list)
        elif 'thinglink.com' in iframe['src']:
            def process_thinglink(contents):
                new_soup = BeautifulSoup('<div></div>', 'html5lib')
                style_tag = new_soup.new_tag('style')
                style_tag.string = '.tlExceededViewsLimit, .tlThingText:not(.tlVariantVideoThing) .tlThingClose, .tlSidebar {visibility: hidden;} .tlFourDotsButton, .btnViewOnSS {pointer-events: none;} .tlFourDotsButton .btn, .tlFourDotsButton .arrowRight {display: none !important;}'
                contents.head.append(style_tag)
                for script in contents.find_all('script'):
                    if not script.string or 'skip-scrape' in (script.get('class') or []):
                        continue
                    elif 'preloadImages' in script.string:
                        regex = r"(?:'|\")([^'\"]+)(?:'|\"),"
                        for match in re.finditer(regex, script.string, re.MULTILINE):
                            # script.decompose()
                            image_filename = '-'.join(match.group(1).split('?')[0].split('/')[-3:])
                            _fn, ext = os.path.splitext(image_filename)
                            image_filename = image_filename if ext else image_filename + '.png'
                            new_str = match.group(0).replace(match.group(1), zipper.write_url(match.group(1), image_filename, directory="webimg"))
                            script.string = script.string.replace(match.group(0), new_str)
                    elif 'var url = ' in script.string:
                        regex = r"(?:'|\")(http[^'\"]+)(?:'|\")"
                        for match in re.finditer(regex, script.string, re.MULTILINE):
                            image_filename = '-'.join(match.group(1).split('?')[0].split('/')[-3:])
                            _fn, ext = os.path.splitext(image_filename)
                            image_filename = image_filename if ext else image_filename + '.png'
                            new_str = match.group(0).replace(match.group(1), zipper.write_url(match.group(1), image_filename, directory="webimg"))
                            script.string = script.string.replace(match.group(0), new_str)
                    elif 'doresize' in script.string:
                        match = re.search(r'\$tlJQ\(document\)\.ready\(function\(\) \{\s+(doresize\(\);)', script.string)
                        new_str = match.group(0).replace(match.group(1), 'doresize(); __thinglink.reposition(); __thinglink.rebuild();')
                        script.string = script.string.replace(match.group(0), new_str)

                for nubbin in contents.find_all('div', {'class': 'nubbin'}):
                    for subnubbin in nubbin.find_all('div'):
                        regex = r"\((?:'|\")*(http[^'\"]+)(?:'|\")*\)"
                        for match in re.finditer(regex, subnubbin['style'], re.MULTILINE):
                            image_filename = '-'.join(match.group(1).split('?')[0].split('/')[-3:])
                            _fn, ext = os.path.splitext(image_filename)
                            image_filename = image_filename if ext else image_filename + '.png'
                            subnubbin['style'] = subnubbin['style'].replace(match.group(1), zipper.write_url(match.group(1), image_filename, directory="webimg"))
                # for supernubbin in contents.find_all('div', {'class': 'tagx'}):
                #     if supernubbin.get('href'):

                #          = download_youtube(supernubbin['href'], zipper)
                #         import pdb; pdb.set_trace()



            def preprocess_thinglink(url, contents, zipper):
                thinglink_id = url.split('/')[-1]
                response = requests.get('https://www.thinglink.com/api/tags?url={}'.format(thinglink_id))
                for script in contents.find_all('script'):
                    if script.get('src') and 'embed.js' in script['src']:
                        script_contents = downloader.read(script['src']).decode('utf-8')
                        tag_data = json.loads(response.content)
                        for thing in tag_data[thinglink_id]['things']:
                            if thing['thingUrl']:
                                thing['thingUrl'] = download_youtube(thing['thingUrl'], zipper)
                                thing['contentUrl'] = thing['thingUrl']
                                icon_fn = '-'.join(thing['icon'].split('?')[0].split('/')[-2:])
                                thing['icon'] = zipper.write_url(get_relative_url(thing['icon'], thing['icon']), 'thinglink-{}.jpg'.format(icon_fn), directory="img")
                        script_contents = script_contents.replace('d.ajax({url:A+"/api/tags",data:u,dataType:"jsonp",success:z})', 'z({})'.format(json.dumps(tag_data)))
                        script_contents = script_contents.replace('n.getJSON(A+"/api/internal/logThingAccess?callback=?",{thing:y,sceneId:w,e:"hover",referer:t.referer,dwell:v});', '')
                        script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logThingAccess?callback=?",{time:y,sceneId:v,thing:w,e:"hoverend",referer:t.referer})', '')
                        script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logSceneAccess?callback=?",{time:z,sceneId:w,referer:t.referer,dwell:v,event:"scene.hover"})', '')
                        script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logSceneAccess?callback=?",{sceneId:v,referer:t.referer,event:"scene.view",channelId:b.getChannelId(x)})', '')
                        script_contents = script_contents.replace('n.getJSON(B+"/api/internal/logThingAccess?callback=?",z,C);', '')

                        icon_str = 'k.src=l;return"style=\\"background-image: url(\'"+l+"\') !important;\\"'
                        script_contents = script_contents.replace(icon_str, 'var slices=l.split("/"); l="webimg/"+slices.slice(slices.length-3,slices.length).join("-")+".png";' + icon_str)
                        script['class'] = ['skip-scrape']
                        script['src'] = zipper.write_contents('thinglink-embed.js', script_contents,  directory="js")
            omit_list = [
                ('nav', {'class': 'item-header'}),
            ]
            iframe['height'] = "500px"
            download_webpage(iframe, zipper, omit_list=omit_list, pre_process=preprocess_thinglink, post_process=process_thinglink, loadjs=True)
        elif 'slideshare.net' in iframe['src']:
            download_presentation(iframe, zipper, img_class='slide_image', img_attr='data-normal')
        elif 'easel.ly' in iframe['src']:
            download_image(iframe, zipper, selector={'id': 'thumb'})
        else:
            LOGGER.error('Unrecognized source found at {} ({})'.format(iframe['src'], url.replace('inicio', filename)))
            manage_unrecognized_source(iframe, zipper)

    if post_process:
        post_process(contents)

    return zipper.write_contents(filename, contents.prettify().encode('utf-8-sig'))

def download_image(iframe, zipper, selector=''):
    contents = BeautifulSoup(downloader.read(iframe['src']), 'html5lib')
    new_soup = BeautifulSoup('<div></div>', 'html5lib')
    image = new_soup.new_tag('img')
    filename = '-'.join(contents.find('img', selector)['src'].split('?')[0].split('/')[-3:])
    image['src'] = zipper.write_url(contents.find('img')['src'], filename, directory='webimg')
    iframe.replaceWith(image)

def download_youtube(url, zipper):
    video_id = url.split('/')[-1].replace('?', '-')
    video_path = os.path.join(VIDEO_DIRECTORY, '{}.mp4'.format(video_id))
    dl_settings = {
        'outtmpl': video_path,
        'quiet': True,
        'overwrite': True,
        'format': "mp4",
    }
    if not os.path.exists(video_path):
        with youtube_dl.YoutubeDL(dl_settings) as ydl:
            ydl.download([url])
    return zipper.write_file(video_path, os.path.basename(video_path), directory="videos")

def download_web_video(iframe, zipper):
    new_soup = BeautifulSoup('<div></div>', 'html5lib')
    video_id = iframe['src'].split('/')[-1].split('?')[0]
    video_path = os.path.join(VIDEO_DIRECTORY, '{}.mp4'.format(video_id))
    try:
        video_tag = new_soup.new_tag('video')
        video_tag['controls'] = 'controls'
        video_tag['style'] = iframe.get('style') or 'width: 100%;'
        video_tag['preload'] = 'auto'
        source_tag = new_soup.new_tag('source')
        video_tag.append(source_tag)
        source_tag['src'] = download_youtube(iframe['src'], zipper)
        iframe.replaceWith(video_tag)

    except (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError) as e:
        LOGGER.error(str(e))
        # Replace with image and header
        new_div = new_soup.new_tag('div')
        error_message = new_soup.new_tag('p')
        error_message['style'] = 'color: red;font-weight: bold;font-style: italic; font-size: 9pt;';
        error_message.string = 'Hubo un error al descargar este vídeo'
        new_div.append(error_message)
        try:
            new_thumbnail = new_soup.new_tag('img')
            new_thumbnail['src'] = zipper.write_url('https://i.ytimg.com/vi/{}/sddefault.jpg'.format(video_id), '{}.jpg'.format(video_id), directory="img")
            new_div.append(new_thumbnail)
        except:
            pass
        iframe.replaceWith(new_div)


def download_google_drive_file(iframe, zipper):
    new_soup = BeautifulSoup('<div></div>', 'html5lib')
    file_id = re.search(r'https://[^\.]+.google.com/file/d/([^/]+)/preview', iframe['src']).group(1)
    drive_file = DRIVE.CreateFile({'id': file_id})
    _drivename, ext = os.path.splitext(drive_file['title'])
    filename = '{}{}'.format(file_id, ext)

    write_to_path = os.path.join(DRIVE_DIRECTORY, filename);
    if not os.path.exists(write_to_path):
        drive_file.GetContentFile(write_to_path)

    if ext.endswith('pdf'):
        embed_tag = new_soup.new_tag('embed')
        embed_tag['src'] = zipper.write_file(write_to_path, filename, directory="src")
        iframe.replaceWith(embed_tag)
    elif ext.endswith('png') or ext.endswith('jpg'):
        img_tag = new_soup.new_tag('img')
        img_tag['src'] = zipper.write_file(write_to_path, filename, directory="img")
        iframe.replaceWith(img_tag)
    else:
        LOGGER.error('New google drive file type', iframe['src'])


def download_pdf(iframe, zipper):
    new_soup = BeautifulSoup('<div></div>', 'html5lib')
    embed_tag = new_soup.new_tag('embed')
    embed_tag['src'] = zipper.write_url(iframe['src'], iframe['src'].split('/')[-1].split('?')[0], directory="src")
    embed_tag['width'] = '100%'
    embed_tag['style'] = 'height: 500px;max-height: 100vh;'
    iframe.replaceWith(embed_tag)


def download_webpage(iframe, zipper, omit_list=None, loadjs=False, pre_process=None, post_process=None):
    page = BeautifulSoup(downloader.read(get_relative_url(iframe['src'], iframe['src']), loadjs=loadjs), 'html5lib')
    message = page.new_tag('p')
    message['style'] = 'color: #EA9600;font-weight: bold;font-size: 11pt;'
    message.string = iframe['src'].strip('/')
    filename = "{}.html".format('-'.join(iframe['src'].split('/')[2:]).replace('.html', '')).replace('www.', '')
    iframe['width'] = '100%'
    iframe['src'] = write_zip_page(iframe['src'], page, zipper, filename=filename, scrape_subpages=False, omit_list=omit_list, pre_process=pre_process, post_process=post_process)
    iframe.insert_before(message)


def download_presentation(iframe, zipper, img_class='', img_attr='src'):
    page = BeautifulSoup(downloader.read(get_relative_url(iframe['src'], iframe['src'])), 'html5lib')
    images = []
    for img in page.find_all('img', {'class': img_class}):
        filename = img[img_attr].split('/')[-1].split('?')[0]
        images.append(zipper.write_url(img[img_attr], filename, directory="slides"))
    new_page = BeautifulSoup(downloader.read('img.html').decode('utf-8','ignore'), 'html5lib')
    script_tag = new_page.find('script', {'class': 'insert-list'})
    script_tag.string = 'let images = [{}];'.format(','.join(['\"{}\"'.format(i) for i in images]))
    iframe['src'] = zipper.write_contents('{}.html'.format(iframe['src'].split('/')[-1].split('?')[0]), new_page.prettify())


def manage_unrecognized_source(iframe, zipper):
    new_soup = BeautifulSoup('<div></div>', 'html5lib')
    try:
        response = requests.get(get_relative_url(iframe['src'], iframe['src']))
        response.raise_for_status()
        manage_unscrapable_source(iframe, zipper)
    except requests.exceptions.HTTPError as e:
        # Replace with image and header
        error_message = new_soup.new_tag('p')
        error_message['style'] = 'color: red;font-weight: bold;font-style: italic; font-size: 9pt;';
        error_message.string = 'No se pudo cargar este contenido (mencionado por {})'.format(iframe['src'])
        iframe.replaceWith(error_message)


def manage_unscrapable_source(iframe, zipper):
    new_soup = BeautifulSoup('<div></div>', 'html5lib')
    error_message = new_soup.new_tag('p')
    error_message['style'] = 'color: #EA9600;font-weight: bold;font-size: 11pt;';
    error_message.string = 'No se puedo descargar este contenido. Necesita Internet para ver este elemento (mencionado por {})'.format(iframe['src']);
    try:
        iframe.insert_before(error_message)
    except ValueError:
        import pdb; pdb.set_trace()
        pass
        # DO SOMETHING HERE


def get_source_id(text):
    return "{}{}".format(BASE_URL, text.lstrip('/').lower().replace(' ', '_'))


# CLI
################################################################################
import time
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    # chef = CeibalChef()
    # chef.main()
    print("********** STARTING **********")
    start = time.time()
    test_page('https://rea.ceibal.edu.uy/elp/en_la_agenda_e_participaci_n_ciudadana/inicio')
    print("FINISHED: {}".format(time.time() - start))
