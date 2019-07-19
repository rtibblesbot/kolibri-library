#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
from bs4 import BeautifulSoup
from ricecooker.utils import downloader, html_writer
from ricecooker.config import LOGGER              # Use LOGGER to print messages
import cssutils
import requests
import re
from urllib.parse import urlparse
import youtube_dl
import zipfile
import shutil
import tempfile
import json

from tags import EXCEPTIONS, BasicScraper, DEFAULT_HANDLERS, BrokenSourceException, UnscrapableSourceException, MESSAGES


class BasicPageScraper(BasicScraper):
    partially_scrapable = False
    scrape_subpages = True
    default_ext = '.html'
    main_area_selector = None
    omit_list = None
    standalone = False
    loadjs = False
    scrapers = None
    extra_tags = None

    def __init__(self, *args, **kwargs):
        """
            url: string                                    # URL to read from
            html_writer: ricecooker.utils.html_writer      # Zip to write files to
            loadjs: bool                                   # Load js on page read
            locale: string                                 # Language to use when writing error messages
        """
        super(BasicPageScraper, self).__init__(*args, **kwargs)
        self.omit_list = self.omit_list or []
        self.omit_list += [
            ('link', {'type': 'image/x-icon'}),
            ('link', {'rel': 'apple-touch-icon'}),
            ('span', {'class': 'external-iframe-src'}),
            ('link', {'rel': 'icon'}),
        ]
        self.extra_tags = self.extra_tags or []
        self.scrapers = (self.scrapers or []) + [self.__class__]

    @classmethod
    def test(self, value):
        return False


    def preprocess(self, contents):
        # Implement in subclasses
        pass


    def process(self, filename='index.html'):
        filename = filename or self.get_filename(self.url)
        if self.zipper.contains(filename):
            return filename

        contents = BeautifulSoup(downloader.read(self.url, loadjs=self.loadjs), 'html5lib')
        self.preprocess(contents)

        if self.main_area_selector:
            body = self.create_tag('body')
            body.append(contents.find(*self.main_area_selector))
            contents.body.replaceWith(body)

        for item in self.omit_list:
            for element in contents.find_all(*item):
                element.decompose()

        for tag_class in (self.extra_tags + DEFAULT_HANDLERS):
            for tag in contents.find_all(*tag_class.selector):
                scraper = tag_class(tag, self.url, self.zipper, scrape_subpages=self.scrape_subpages, triaged=self.triaged, locale=self.locale, extra_scrapers=self.scrapers, color=self.color)
                scraper.scrape()

        self.postprocess(contents)
        return self.write_contents(filename, contents.prettify().encode('utf-8-sig'))


    def postprocess(self, contents):
        # Implement in subclasses
        pass

    def process_tag(self):
        # Returns tag with scraped link
        return self.create_tag('div')


########## COMMON SCRAPERS ##########
class WebVideoScraper(BasicPageScraper):
    directory = 'media'
    default_ext = '.mp4'
    standalone = True

    def __init__(self, *args, **kwargs):
        super(WebVideoScraper, self).__init__(*args, **kwargs)
        self.video_id = self.url.split('/')[-1].replace('?', '-')

    @classmethod
    def test(self, value):
        return 'youtube' in value or 'vimeo' in value

    def process(self, **kwargs):
        try:
            tempdir = tempfile.mkdtemp()
            video_path = os.path.join(tempdir, '{}{}'.format(self.video_id, self.default_ext))
            dl_settings = {
                'outtmpl': video_path,
                'quiet': True,
                'overwrite': True,
                'format': self.default_ext.split('.')[-1],
            }
            if not os.path.exists(video_path):
                with youtube_dl.YoutubeDL(dl_settings) as ydl:
                    ydl.download([self.url])

            try:
                return self.write_file(video_path)
            except Exception as e:
                LOGGER.warning('Unable to download video {}'.format(self.url))
                raise UnscrapableSourceException(str(e))
        except (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError) as e:
            raise UnscrapableSourceException(str(e))  # Some errors are region-specific, so allow link
        finally:
            shutil.rmtree(tempdir)


    def process_tag(self):
        video = self.create_tag('video')
        video['controls'] = 'controls'
        video['style'] = 'width: 100%;'
        video['preload'] = 'auto'
        source = self.create_tag('source')
        source['src'] = self.process()
        video.append(source)

        return video

class PDFScraper(BasicPageScraper):
    directory = 'pdfs'
    default_ext = '.pdf'
    standalone = True

    @classmethod
    def test(self, value):
        return value.split('?')[0].lower().endswith('.pdf')

    def process(self, **kwargs):
       return self.write_url(self.url)

    def process_tag(self, **kwargs):
        try:
            embed = self.create_tag('embed')
            embed['src'] = self.process()
            embed['width'] = '100%'
            embed['style'] = 'height: 500px;max-height: 100vh;'
            return embed
        except EXCEPTIONS as e:
            LOGGER.error(str(e))
            return self.create_broken_link_message(self.url)

class ImageScraper(BasicPageScraper):
    directory = 'img'
    default_ext = '.png'
    standalone = True

    @classmethod
    def test(self, value):
        return value.lower().endswith('.png') or value.lower().endswith('.jpg')

    def process(self, **kwargs):
       return self.write_url(self.url)

    def process_tag(self, **kwargs):
        try:
            img = self.create_tag('img')
            img['src'] = self.process()
            return img
        except EXCEPTIONS as e:
            LOGGER.error(str(e))
            return self.create_broken_link_message(self.url)

class FlashScraper(BasicPageScraper):
    default_ext = '.swf'
    standalone = True

    @classmethod
    def test(self, value):
        return value.split('?')[0].lower().endswith('.swf')

    def process(self, **kwargs):
        downloader.read(self.url) # Raises broken link error if fails
        raise UnscrapableSourceException('Cannot scrape Flash content')

    def process_tag(self, **kwargs):
        downloader.read(self.url) # Raises broken link error if fails
        raise UnscrapableSourceException('Cannot scrape Flash content')


DEFAULT_PAGE_HANDLERS = [
    WebVideoScraper,
    PDFScraper,
    ImageScraper,
    FlashScraper,
]

########## LESS COMMON SCRAPERS (import as needed) ##########
class GoogleDriveScraper(BasicPageScraper):
    directory = 'gdrive'
    replace = True

    def __init__(self, *args, **kwargs):
        from pydrive.auth import GoogleAuth
        from pydrive.drive import GoogleDrive

        super(GoogleDriveScraper, self).__init__(*args, **kwargs)
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

        self.drive = GoogleDrive(gauth)

    @classmethod
    def test(self, value):
        return re.match(r'https://[^\.]+.google.com/.*file/d/[^/]+/(?:preview|edit)', value)

    def process(self, **kwargs):
        from pydrive.files import FileNotDownloadableError, ApiRequestError
        try:
            file_id = re.search(r'https://[^\.]+.google.com/.*file/d/([^/]+)/(?:preview|edit)', iframe['src']).group(1)
            drive_file = self.drive.CreateFile({'id': file_id})
            _drivename, ext = os.path.splitext(drive_file.get('title') or '')
            filename = '{}{}'.format(file_id, ext)

            write_to_path = os.path.join(DRIVE_DIRECTORY, filename);
            if not os.path.exists(write_to_path):
                drive_file.GetContentFile(write_to_path)

            return self.write_file(write_to_path)
        except (FileNotDownloadableError, ApiRequestError) as e:
            LOGGER.error(str(e))
            raise BrokenSourceException(str(e))


    def process_tag(self, **kwargs):
        if ext.endswith('pdf'):
            embed_tag = self.create_tag('embed')
            embed_tag['style'] = 'width: 100%;min-height: 500px;'
            embed_tag['src'] = self.process()
            return embed_tag
        elif ext.endswith('png') or ext.endswith('jpg'):
            img_tag = self.create_tag('img')
            img_tag['src'] = self.process()
            return img_tag
        else:
            raise NotImplementedError('Unhandled google drive file type at {}'.format(self.link))


class GeniallyScraper(BasicPageScraper):
    scrape_subpages = False
    directory = 'genially'
    partially_scrapable = True

    @classmethod
    def test(self, value):
        return 'genial.ly' in value

    def preprocess(self, contents):
        # Hide certain elements from the page
        style_tag = self.create_tag('style')
        style_tag.string = '.genially-view-logo { pointer-events: none;} .genially-view-navigation-actions,'\
            ' .genially-view-navigation-actions-toggle-button{display: none !important; pointer-events:none;}'
        contents.find('head').append(style_tag)


        # Prefetch API response and replace script content accordingly
        genial_id = self.url.split('/')[-1]
        response = requests.get('https://view.genial.ly/api/view/{}'.format(genial_id))
        for script in contents.find_all('script'):
            if script.get('src') and 'main' in script['src']:
                script_contents = downloader.read(self.get_relative_url(script['src'])).decode('utf-8')
                genial_data = json.loads(response.content)

                if len(genial_data['Videos']) or len(genial_data['Audios']):
                    LOGGER.error('Unhandled genial.ly video or audio at {}'.format(url))

                if genial_data['Genially']['ImageRender']:
                    genial_data['Genially']['ImageRender'] = self.write_url(genial_data['Genially']['ImageRender'])
                for image in genial_data['Images']:
                    image['Source'] = self.write_url(image['Source'])
                for slide in genial_data['Slides']:
                    slide['Background'] = self.write_url(slide['Background'])
                for code in genial_data['Contents']:
                    code_contents = BeautifulSoup(code['HtmlCode'], 'html.parser')
                    for img in code_contents.find_all('img'):
                        try:
                            img['src'] = self.write_url(img['src'])
                        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
                            LOGGER.warning("Error processing genial.ly at {} ({})".format(self.url, str(e)))
                    code['HtmlCode'] = code_contents.prettify()
                script_contents = script_contents.replace('r.a.get(c).then(function(e){return n(e.data)})', 'n({})'.format(json.dumps(genial_data)))
                self.mark_tag_to_skip(script)
                script['src'] = zipper.write_contents('genial-{}-embed.js'.format(genial_id), script_contents,  directory="js")

class PresentationScraper(BasicPageScraper):
    thumbnail = None
    source = ""
    img_selector = ('img',)
    img_attr='src'
    directory='slides'

    @classmethod
    def test(self, value):
        return False

    def process(self, **kwargs):
        contents = BeautifulSoup(downloader.read(self.url, loadjs=self.loadjs), 'html5lib')
        images = []
        for img  in contents.find_all(*self.img_selector):
            images.append(os.path.basename(self.write_url(img[self.img_attr], default_ext=".png")))
        return self.write_contents(self.get_filename(self.url), self.generate_slideshow(images))

    def generate_slideshow(self, images):
        # <body>
        page = BeautifulSoup('', 'html5lib')
        page.body['style'] = 'background-color: black; height: 100vh; margin: 0px;'
        page.body['class'] = ['collapsed']
        page.body['onclick'] = 'closeDropdown()'

        # <style>
        style = self.create_tag('style')
        style.string = '#gallery {width: 100vw;}\n'\
                    '#progress, #navigation, .wrapper, #gallery {max-width: 900px;}\n'\
                    'button {cursor: pointer}\n'\
                    'button:disabled { cursor: not-allowed; opacity: 0.5; }\n'\
                    'body.fullscreen .wrapper {max-width: 100%;}\n'\
                    'body.fullscreen #gallery, body.fullscreen #navigation, body.fullscreen #progress {max-width: 100%;}\n'\
                    '#counter::after { content: "▲"; padding-left: 10px; font-size: 7pt; vertical-align: middle; }\n'\
                    '#navigation-menu {list-style: none; padding: 0px; overflow-y: auto; overflow-x: none; height: 250px; max-height: 100vh;background: '\
                        'white; width: max-content; margin: 0 auto; margin-top: -275px; border: 1px solid #ddd; display: none; position: relative;}\n'\
                    '#navigation-menu li:not(:first-child) {border-top: 1px solid #ddd; }'\
                    '#navigation-menu li:hover { background-color: #ddd; }\n'\
                    '#progressbar { height: 10px; background-color: rgb(153, 97, 137); transition: width 0.5s; }'

        page.head.append(style)

        # <div class="wrapper">
        wrapper = self.create_tag('div')
        wrapper['style'] = 'width: max-content; margin: 0 auto; text-align: center;'
        page.body.append(wrapper)

        # <img id="gallery"/>
        gallery = self.create_tag('img')
        gallery['id'] = 'gallery'
        gallery['style'] = 'cursor:pointer; height: auto; max-height: calc(100vh - 45px); object-fit: contain; color: white; font-family: sans-serif;'
        gallery['onclick'] = 'updateImage(1)'
        gallery['src'] = images[0]
        wrapper.append(gallery)

        # <div id="progress">
        progress = self.create_tag('div')
        progress['id'] = 'progress'
        progress['style'] = 'background-color: #4E4E4E; width: 100vw; height: 10px;'
        wrapper.append(progress)

        # <div id="progressbar">
        progressbar = self.create_tag('div')
        progressbar['id'] = 'progressbar'
        progress.append(progressbar)

        # <div id="navigation">
        navigation = self.create_tag('div')
        navigation['id'] = 'navigation'
        navigation['style'] = 'background-color:#353535; text-align:center; height: 33px; width: 100vw;'
        wrapper.append(navigation)

        # <button id="next-btn">
        nextbutton = self.create_tag('button')
        nextbutton['id'] = 'next-btn'
        nextbutton.string = '🡒'
        nextbutton['style'] = 'float:right; background-color: transparent; border: none; font-size: 17pt; color: white; width:75px; font-size:16pt;'
        nextbutton['onclick'] = 'updateImage(1)'
        nextbutton['title'] = MESSAGES[self.locale]['next']
        navigation.append(nextbutton)

        # <a id="fullscreen">
        fullscreentoggle = self.create_tag('a')
        fullscreentoggle['id'] = 'fullscreen'
        fullscreentoggle['style'] = 'float:right; color: white; font-size: 15pt; padding: 5px; cursor: pointer;'
        fullscreentoggle['onclick'] = 'toggleFullScreen()'
        fullscreentoggle['title'] = MESSAGES[self.locale]['toggle_fullscreen']
        fullscreentoggle.string = '⤢'
        navigation.append(fullscreentoggle)

        # <button id="prev-btn">
        prevbutton = self.create_tag('button')
        prevbutton['id'] = 'prev-btn'
        prevbutton.string = '🡐'
        prevbutton['style'] = 'float:left; background-color: transparent; border: none; font-size: 17pt; color: white; width:75px; font-size:16pt;'
        prevbutton['onclick'] = 'updateImage(-1)'
        prevbutton['title'] = MESSAGES[self.locale]['previous']
        navigation.append(prevbutton)

        # <div id="attribution">
        if self.source:
            attribution = self.create_tag('div')
            attribution['id'] = 'attribution'
            attribution['style'] = 'float:left; margin-top:3px;'
            navigation.append(attribution)

            # <img id="sourceLogo">
            if self.thumbnail:
                source_logo = self.create_tag('img')
                source_logo['id'] = 'sourceLogo'
                source_logo['src'] = os.path.basename(self.write_url(self.thumbnail, default_ext=".png"))
                source_logo['style'] = 'width: 24px; height: auto; margin-right: 5px;'
                attribution.append(source_logo)

            # <div id="created">
            created = self.create_tag('div')
            created['style'] = 'text-align: left; color: white; font-family: sans-serif; font-size: 7pt; display: inline-block;'
            created['id'] = 'created'
            created.string = MESSAGES[self.locale]['presentation_source']
            attribution.append(created)

            # <div id="sourceText">
            source_text = self.create_tag('div')
            source_text.string = self.source
            source_text['style'] = 'font-size: 12pt;'
            created.append(source_text)

        # <div id='center'>
        center_nav = self.create_tag('div')
        navigation.append(center_nav)

        # <div id='counter'>
        counter = self.create_tag('div')
        counter['id'] = 'counter'
        counter['style'] = 'padding-top: 5px; color: white; cursor: pointer; font-family: sans-serif;'
        counter['onclick'] = 'openDropdown(event)'
        center_nav.append(counter)

        # <ul id="navigation-menu">
        navmenu = self.create_tag('ul')
        navmenu['id'] = 'navigation-menu'
        center_nav.append(navmenu)

        for index, img  in enumerate(images):
            # <li>
            navmenuitem = self.create_tag('li')
            navmenuitem['style'] = 'font-family: sans-serif; text-align: left; padding: 10px 25px; cursor: pointer;'
            navmenuitem['onclick'] = 'jumpToImage({})'.format(index)
            navmenu.append(navmenuitem)

            # <img class="slide"> Slide #
            slideimg = self.create_tag('img')
            slideimg['class'] = ['slide']
            slideimg['src'] = img
            slideimg['style'] = 'width: 150px; vertical-align: middle; font-size: 12pt; margin-right: 20px;'
            navmenuitem.append(slideimg)
            navmenuitem.append(MESSAGES[self.locale]['slide'].format(index + 1))

        # <script>
        script = self.create_tag('script')
        script.string = "let images = [{images}]; \n"\
            "let index = 0;\n"\
            "let menuExpanded = false;\n"\
            "let img = document.getElementById('gallery');\n"\
            "let prevbutton = document.getElementById('prev-btn');\n"\
            "let nextbutton = document.getElementById('next-btn');\n"\
            "let countText = document.getElementById('counter');\n"\
            "let progress = document.getElementById('progress');\n"\
            "let menu = document.getElementById('navigation-menu');"\
            .format(images=','.join(['\"{}\"'.format(i) for i in images]))

        script.string += "function updateImage(step) {\n"\
            "  if(index + step >= 0 && index + step < images.length)\n"\
            "    index += step;\n"\
            "  jumpToImage(index);\n"\
            "}"

        script.string += "function jumpToImage(step) {\n"\
            "  index = step;\n"\
            "  countText.innerHTML = index + 1 + ' / ' + images.length;\n"\
            "  img.setAttribute('src', images[index]);\n"\
            "  countText.innerHTML = index + 1 + ' / ' + images.length;\n"\
            "  img.setAttribute('src', images[index]);\n"\
            "  (index === 0)? prevbutton.setAttribute('disabled', 'disabled') : prevbutton.removeAttribute('disabled');\n"\
            "  (index === images.length - 1)? nextbutton.setAttribute('disabled', 'disabled') : nextbutton.removeAttribute('disabled');\n"\
            "  progress.children[0].setAttribute('style', 'width:' + ((index + 1) / images.length * 100) + '%;')\n"\
            "}\n"

        script.string += "function toggleFullScreen() {\n"\
            "if ((document.fullScreenElement && document.fullScreenElement !== null) ||(!document.mozFullScreen && !document.webkitIsFullScreen)) {\n"\
            "document.body.setAttribute('class', 'fullscreen');\n"\
            "if (document.documentElement.requestFullScreen) { document.documentElement.requestFullScreen();} \n"\
            "else if (document.documentElement.mozRequestFullScreen) { document.documentElement.mozRequestFullScreen(); } \n"\
            "else if (document.documentElement.webkitRequestFullScreen) { document.documentElement.webkitRequestFullScreen(Element.ALLOW_KEYBOARD_INPUT); }\n"\
            "} else {\n"\
            "document.body.setAttribute('class', 'collapsed');\n"\
            "if (document.cancelFullScreen) { document.cancelFullScreen(); }\n"\
            "else if (document.mozCancelFullScreen) { document.mozCancelFullScreen(); }\n"\
            "else if (document.webkitCancelFullScreen) { document.webkitCancelFullScreen(); }\n"\
            "}\n"\
            "}\n"

        script.string += "function closeDropdown() {\n"\
            "menu.setAttribute('style', 'display: none;');\n"\
            "menuExpanded = false;\n"\
            "}\n"

        script.string += "function openDropdown(event) {\n"\
            "event.stopPropagation();\n"\
            "menu.setAttribute('style', (menuExpanded)? 'display:none;' : 'display:block;');\n"\
            "menuExpanded = !menuExpanded;\n"\
            "}\n"

        script.string += 'updateImage(0);'

        page.body.append(script)

        return page.prettify()

class SlideShareScraper(PresentationScraper):
    thumbnail = "https://is1-ssl.mzstatic.com/image/thumb/Purple113/v4/03/df/99/03df99d1-48c0-d976-c0f3-3ad4a6af5b90/source/200x200bb.jpg"
    source = "SlideShare"
    img_selector = ('img', {'class': 'slide_image'})
    img_attr='data-normal'

    @classmethod
    def test(self, value):
        return 'slideshare.net' in value


class WikipediaScraper(BasicPageScraper):
    scrape_subpages = False
    main_area_selector = ('div', {'id': "content"})
    partially_scrapable = True
    omit_list = [
        ('span', {'class': 'mw-editsection'}),
        ('a', {'class': 'mw-jump-link'}),
    ]

    @classmethod
    def test(self, value):
        return 'wikipedia' in value or 'wikibooks' in value
