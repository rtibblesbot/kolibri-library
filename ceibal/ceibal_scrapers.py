#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import requests
import re
from ricecooker.utils import downloader
from pages import BasicPageScraper, SlideShareScraper, WikipediaScraper
from tags import ImageTag, MediaTag

######### CUSTOM TAGS #########

class CeibalVideoAudioTag(MediaTag):
    default_ext = '.mp3'
    selector = ('video',)

    def scrape(self):
        if self.link and self.link.endswith('.mp3'):
            audio_tag = self.create_tag('audio')
            audio_tag['controls'] = 'controls'
            audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
            source_tag = self.create_tag('source')
            audio_tag.append(source_tag)
            source_tag['src'] = self.write_url(self.link)
            self.tag.replaceWith(audio_tag)
            self.mark_tag_to_skip(audio_tag)

class CeibalVideoTag(MediaTag):
    default_ext = '.mp4'
    selector = ('div', {'class': 'mejs-video'})

    def scrape(self):
        if self.tag.find('audio'):
            self.tag.replaceWith(self.tag.find('audio'))
            return
        try:
            video_tag = self.create_tag('video')
            video_tag['style'] = 'margin-left: auto; margin-right: auto; width: 500px;'
            video_tag['preload'] = 'auto'
            video_tag['controls'] = 'controls'
            for source in self.tag.find_all('source'):
                source_tag = self.create_tag('source')
                source_tag['src'] = self.write_url(source['src'])
                video_tag.append(source_tag)
            self.tag.replaceWith(video_tag)
        except Exception as e:
            LOGGER.warn('Cannot parse video at {} ({})'.format(self.url, str(e)))

class CeibalAudioTag(MediaTag):
    default_ext = '.mp3'
    selector = ('div', {'class': 'mejs-audio'})


    def scrape(self):
        try:
            audio_tag = self.create_tag('audio')
            audio_tag['controls'] = 'controls'
            audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
            source_tag = self.create_tag('source')
            audio_tag.append(source_tag)
            source['src'] = self.write_url(self.tag.find('audio')['src'])
            self.tag.replaceWith(audio_tag)
        except Exception as e:
            LOGGER.warn('Cannot parse audio at {}'.format(self.url, str(e)))


class ThingLinkTag(ImageTag):
    selector = ('img', {'class': 'alwaysThinglink'})

    def process(self):
        thinglink_id = re.search(r'image/([^/]+)/', self.link).group(1)
        self.tag['src'] = self.write_url(self.link)
        self.tag.insert_before(self.create_copy_link_message('https://www.thinglink.com/scene/{}'.format(thinglink_id)))
        self.mark_tag_to_skip(self.tag)

        # Don't import script to render image
        if self.tag.find_next('script'):
            self.tag.find_next('script').decompose()


######### CUSTOM SCRAPERS #########

class ThingLinkScraper(BasicPageScraper):
    partially_scrapable = True
    loadjs = True
    scrape_subpages = False
    omit_list = [
        ('nav', {'class': 'item-header'}),
    ]

    @classmethod
    def test(self, value):
        return 'thinglink.com' in value

    def preprocess(self, contents):
        thinglink_id = self.url.split('/')[-1]

        for script in contents.find_all('script'):
            if script.get('src') and 'embed.js' in script['src']:
                response = requests.get('https://www.thinglink.com/api/tags?url={}'.format(thinglink_id))
                script_contents = downloader.read(self.get_relative_url(script['src'])).decode('utf-8')
                tag_data = json.loads(response.content)

                if tag_data[thinglink_id].get('image'):
                    tag_data[thinglink_id]['image'] = self.write_url(tag_data[thinglink_id]['image'])

                for thing in tag_data[thinglink_id]['things']:
                    if thing['thingUrl']:
                        try:
                            thing['thingUrl'] = WebVideoScraper(thing['thingUrl'], self.zipper).process()
                            thing['contentUrl'] = thing['thingUrl']
                            thing['icon'] = self.write_url(thing['icon'], default_ext='.png', directory="thinglink")
                        except youtube_dl.utils.DownloadError as e:
                            LOGGER.warning('Youtube download error on thinglink page ({})'.format(str(e)))
                    if thing.get('nubbin'):
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/plain'.format(thing['nubbin']), filename='nubbin-{}-plain.png'.format(thing['nubbin']), directory="thinglink")
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/highlight'.format(thing['nubbin']), filename='nubbin-{}-highlight.png'.format(thing['nubbin']), directory="thinglink")
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/hover'.format(thing['nubbin']), filename='nubbin-{}-hover.png'.format(thing['nubbin']), directory="thinglink")
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/hoverlink'.format(thing['nubbin']), filename='nubbin-{}-hoverlink.png'.format(thing['nubbin']), directory="thinglink")

                script_contents = script_contents.replace('d.ajax({url:A+"/api/tags",data:u,dataType:"jsonp",success:z})', 'z({})'.format(json.dumps(tag_data)))
                script_contents = script_contents.replace('n.getJSON(A+"/api/internal/logThingAccess?callback=?",{thing:y,sceneId:w,e:"hover",referer:t.referer,dwell:v});', '')
                script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logThingAccess?callback=?",{time:y,sceneId:v,thing:w,e:"hoverend",referer:t.referer})', '')
                script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logSceneAccess?callback=?",{time:z,sceneId:w,referer:t.referer,dwell:v,event:"scene.hover"})', '')
                script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logSceneAccess?callback=?",{sceneId:v,referer:t.referer,event:"scene.view",channelId:b.getChannelId(x)})', '')
                script_contents = script_contents.replace('n.getJSON(B+"/api/internal/logThingAccess?callback=?",z,C);', '')

                icon_str = 'k.src=l;return"style=\\"background-image: url(\'"+l+"\') !important;\\"'
                script_contents = script_contents.replace(icon_str, 'var slices=l.split("/"); l="thinglink/"+slices.slice(slices.length-3,slices.length).join("-")+".png";{}'.format(icon_str))
                script['src'] = self.write_contents('thinglink-{}-embed.js'.format(thinglink_id), script_contents, directory="thinglink")
                self.mark_tag_to_skip(script)

    def postprocess(self, contents):
        style_tag = self.create_tag('style')
        style_tag.string = '.tlExceededViewsLimit, .tlThingText:not(.tlVariantVideoThing) .tlThingClose, .tlSidebar, .tlThinglinkSite {visibility: hidden !important;} .tlFourDotsButton, .btnViewOnSS {pointer-events: none;} .tlFourDotsButton .btn, .tlFourDotsButton .arrowRight {display: none !important;}'
        contents.head.append(style_tag)
        for script in contents.find_all('script'):
            if not script.string or 'skip-scrape' in (script.get('class') or []):
                continue
            elif 'preloadImages' in script.string:
                regex = r"(?:'|\")([^'\"]+)(?:'|\"),"
                for match in re.finditer(regex, script.string, re.MULTILINE):
                    new_str = match.group(0).replace(match.group(1), self.write_url(match.group(1), default_ext=".png", directory="thinglink"))
                    script.string = script.text.replace(match.group(0), new_str)
            elif re.search(r"var url\s*=\s*(?:'|\")([^'\"]+)(?:'|\")", script.string, re.MULTILINE):
                regex = r"url\s*=\s*(?:'|\")([^'\"]+)(?:'|\")"
                for match in re.finditer(regex, script.string, re.MULTILINE):
                    new_str = match.group(0).replace(match.group(1), self.write_url(match.group(1), default_ext=".png", directory="thinglink"))
                    script.string = script.text.replace(match.group(0), new_str)
            elif 'doresize' in script.string:
                match = re.search(r'\$tlJQ\(document\)\.ready\(function\(\) \{\s+(doresize\(\);)', script.string)
                new_str = match.group(0).replace(match.group(1), 'doresize(); __thinglink.reposition(); __thinglink.rebuild();')
                script.string = script.text.replace(match.group(0), new_str)

        for nubbin in contents.find_all('div', {'class': 'nubbin'}):
            for subnubbin in nubbin.find_all('div'):
                if not subnubbin.get('style'):
                    continue
                regex = r"\((?:'|\")*(http[^'\"]+)(?:'|\")*\)"
                for match in re.finditer(regex, subnubbin['style'], re.MULTILINE):
                    subnubbin['style'] = subnubbin['style'].replace(match.group(1), self.write_url(match.group(1), default_ext=".png", directory="thinglink"))


########## MAIN SCRAPER ##########

class CeibalPageScraper(BasicPageScraper):
    color = "#2E72B0"
    extra_tags = [CeibalVideoAudioTag, CeibalVideoTag, CeibalAudioTag, ThingLinkTag]
    scrapers = [ThingLinkScraper, SlideShareScraper, WikipediaScraper]

    @classmethod
    def test(self, value):
        return 'rea.ceibal.edu.uy' in value

    def __init__(self, *args, **kwargs):
        super(CeibalPageScraper, self).__init__(*args, **kwargs)
        self.url = self.url.replace('inicio', 'index.html')

    def preprocess(self, contents):
        # Some scripts only load if there's a video on the page
        if 'rea.ceibal.edu.uy' in self.url and contents.find('video'):
            contents = BeautifulSoup(downloader.read(self.url, loadjs=True), 'html5lib')

        for block in contents.find_all('div', {'class': 'iDevice_content'}):
            block['style'] = 'word-break: break-word;'

        for header in contents.find_all('div', {'class': 'iDevice_header'}) + contents.find_all('header', {'class': 'iDevice_header'}):
            header['style'] = "min-height: 25px;"

        for obj in contents.find_all('object'):
            obj.replaceWith(self.create_copy_link_message(self.url))

        for script in contents.find_all('script'):
            if script.string and 'gtag' in script.string:
                script.decompose()
