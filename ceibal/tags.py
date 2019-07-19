#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
from bs4 import BeautifulSoup
import subprocess
from ricecooker.utils import downloader, html_writer
from ricecooker.config import LOGGER              # Use LOGGER to print messages
import cssutils
import requests
import re
from urllib.parse import urlparse
import youtube_dl
import zipfile
import tempfile
import shutil
import json

from pydrive.files import FileNotDownloadableError, ApiRequestError
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

import logging
cssutils.log.setLevel(logging.FATAL)


MESSAGES = {
    'en': {
        'broken_link': 'Could not load content (source: {})',
        'not_supported': 'This content is not able to be viewed from within Kolibri',
        'copy_text': 'Please copy this link in your browser to see the original source',
        'partially_supported': 'Some portion of this content may not be viewable in Kolibri',
        'partially_supported_copy_text': 'If you encounter problems, please copy this link in your browser to see the original source',
        'copy_button': 'Copy',
        'copy_error': 'Failed',
        'copy_success': 'Copied',
        'presentation_source': 'Original at',
        'slide': 'Slide {}',
        'toggle_fullscreen': 'Toggle Fullscreen',
        'next': 'Next',
        'previous': 'Previous',
        'jump_to': 'Jump to...'
    },
    'es': {
        'broken_link': 'No se pudo cargar este contenido (mencionado por {})',
        'not_supported': 'Este contenido no se puede ver dentro de Kolibri',
        'copy_text': 'Copie este enlace en su navegador si desea ver la fuente original',
        'partially_supported': 'Puede haber partes de este contenido que no se puedan ver en Kolibri',
        'partially_supported_copy_text': 'Si tiene problemas copie este enlace en su navegador para ver la fuente original',
        'copy_button': 'Copiar',
        'copy_error': 'Falló',
        'copy_success': 'Copiado',
        'presentation_source': 'Original en',
        'slide': 'Diapositiva {}',
        'toggle_fullscreen': 'Cambiar modo Pantalla Completa',
        'next': 'Siguiente',
        'previous': 'Anterior',
        'jump_to': 'Saltar a ...',

    }
}

class BrokenSourceException(Exception):
    """ BrokenSourceException: raised when a source is broken """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class UnscrapableSourceException(Exception):
    """ UnscrapableSourceException: raised when a source is not scrapable """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

EXCEPTIONS = (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.InvalidURL, BrokenSourceException)


class BasicScraper(object):
    url = ""
    zipper = None
    directory = None
    color = 'rgb(153, 97, 137)'

    def __init__(self, url, html_writer, locale='en', triaged=None):
        """
            url: string                                    # URL to read from
            html_writer: ricecooker.utils.html_writer      # Zip to write files to
            locale: string                                 # Language to use when writing error messages
        """
        self.zipper = html_writer
        self.url = url
        self.triaged = triaged or {}
        self.locale = locale

    def create_tag(self, tag):
        return BeautifulSoup('', 'html.parser').new_tag(tag)

    def get_filename(self, link, default_ext=None):
        filename = link.split('?')[0].split('#')[0]
        filename, ext = os.path.splitext(filename)
        return "{}{}".format("".join(re.findall("[a-zA-Z0-9]+", filename))[-20:], ext or default_ext or self.default_ext)

    def mark_tag_to_skip(self, tag):
        tag['class'] = (tag.get('class') or []) + ['skip-scrape']

    def write_url(self, link, url=None, default_ext=None, filename=None, directory=None):
        return self.zipper.write_url(self.get_relative_url(link, url=url), filename or self.get_filename(link, default_ext=default_ext), directory=directory or self.directory)

    def write_contents(self, filename, contents, directory=None):
        return self.zipper.write_contents(filename, contents, directory=directory or self.directory)

    def write_file(self, filepath, directory=None):
        return self.zipper.write_file(filepath, os.path.basename(filepath), directory=directory or self.directory)

    def get_relative_url(self, endpoint, url=None):
        url = url or self.url
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


    def create_broken_link_message(self, link):
        error_message = self.create_tag('p')
        svg = BeautifulSoup('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'\
            '<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 '\
            '22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="#f44336"/></svg>', 'html.parser').svg
        svg['style'] = 'vertical-align: middle; margin-right: .75rem;'
        error_message.append(svg)

        error_message['style'] = 'background-color: rgba(244,67,54,.12);padding: .75rem 1rem;';
        error_message.append(MESSAGES[self.locale]['broken_link'].format(link))
        return error_message

    def create_copy_link_message(self, link, supported_by_kolibri=False, partially_scrapable=False):
        div = self.create_tag('div')
        div['style'] = 'text-align: center;'


        # Add "This content is not able to be viewed from within Kolibri"
        header = self.create_tag('p')
        header['style'] = 'font-size: 12pt;margin-bottom: 0px;color: {};font-weight: bold;'.format(self.color)
        if partially_scrapable:
            header.string = MESSAGES[self.locale]['partially_supported']
            div.append(header)
        elif not supported_by_kolibri:
            header.string = MESSAGES[self.locale]['not_supported']
            div.append(header)


        # Add "Please copy this link in your browser to see the original source"
        subheader = self.create_tag('p')
        subheader['style'] = 'font-weight: bold;margin-bottom: 10px;color: #555;margin-top:5px;'
        subheader.string = MESSAGES[self.locale]['partially_supported_copy_text' if partially_scrapable else 'copy_text']
        div.append(subheader)

        # Add copy link section
        paragraph = self.create_tag('p')
        div.append(paragraph)
        copytext = self.create_tag('input')
        copytext['type'] = 'text'
        copytext['value'] = link
        copytext['style'] = 'width: 250px; max-width: 100vw;text-align: center;font-size: 12pt;'\
            'background-color: #EDEDED;border: none;padding: 10px;color: #555;outline:none;'
        copytext['readonly'] = 'readonly'
        copytext['id'] = "".join(re.findall(r"[a-zA-Z]+", link))
        paragraph.append(copytext)

        # Add copy button
        copybutton = self.create_tag('button')
        copybutton['style'] = 'display: inline-block;cursor: pointer;min-width: 64px;max-width: 100%;min-height: 36px;padding: 0 16px;margin: 8px;'\
            'overflow: hidden;font-size: 14px;font-weight: bold;line-height: 36px;text-align: center;text-decoration: none;text-transform: uppercase;'\
            'white-space: nowrap;cursor: pointer;user-select: none;border: 0;border-radius: 2px;outline: none;background-color:{};color:white;'.format(self.color)
        copybutton.string = MESSAGES[self.locale]['copy_button']
        copybutton['id'] = 'btn-{}'.format(copytext['id'])
        copybutton['onclick'] = '{}()'.format(copytext['id'])  # Keep unique in case there are other copy buttons on the page
        paragraph.append(copybutton)

        # Add copy script
        copyscript = self.create_tag('script')
        copyscript.string = "function {id}(){{ " \
                            "  let text = document.getElementById('{id}');" \
                            "  let button = document.getElementById('btn-{id}');" \
                            "  text.select();" \
                            "  try {{ document.execCommand('copy'); button.innerHTML = '{success}';}}" \
                            "  catch (e) {{ button.innerHTML = '{failed}'; }}" \
                            "  if (window.getSelection) {{window.getSelection().removeAllRanges();}}"\
                            "  setTimeout(() => {{ button.innerHTML = '{text}';}}, 2500);" \
                            "}}".format(
                                id=copytext['id'],
                                success=MESSAGES[self.locale]['copy_success'],
                                text=MESSAGES[self.locale]['copy_button'],
                                failed=MESSAGES[self.locale]['copy_error']
                            )
        div.append(copyscript)

        return div


class BasicScraperTag(BasicScraper):
    default_attribute = 'src'
    default_ext = None
    directory = None
    config = None # Any additional updates to the tags
    scrape_subpages = True
    selector = None
    extra_scrapers = None

    def __init__(self, tag, url, html_writer, attribute=None, scrape_subpages=True, extra_scrapers=None, color='rgb(153, 97, 137)', **kwargs):
        """
            tag (BeautifulSoup tag): tag to scrape
            attribute (str): tag's attribute where link is found (e.g. 'src' or 'data-src')
        """
        super(BasicScraperTag, self).__init__(url, html_writer, **kwargs)
        self.config = self.config or {}
        self.tag = tag
        self.attribute = attribute or self.default_attribute
        self.link = self.tag.get(self.attribute) and self.get_relative_url(self.tag.get(self.attribute)).strip('%20')
        self.scrape_subpages = scrape_subpages
        self.extra_scrapers = extra_scrapers or []
        self.color = color
        if self.directory and not os.path.exists(self.directory):
            os.makedirs(self.directory)

    def format_url(self, zipper_path):
        if '#' in self.link:
            zipper_path += '#' + self.link.split('#')[-1]
        if '?' in self.link:
            zipper_path += '?' + self.link.split('?')[-1]
        return zipper_path

    def scrape(self):
        if 'skip-scrape' in (self.tag.get('class') or []):
            return
        try:
            for key, value in self.config.items():
                self.tag[key] = value
            return self.process()
        except EXCEPTIONS as e:
            LOGGER.warning('Broken source found at {} ({})'.format(self.url, self.link))
            self.handle_error()
        except UnscrapableSourceException:
            LOGGER.warning('Unscrapable source found at {} ({})'.format(self.url, self.link))
            self.handle_unscrapable()
        except KeyError as e:
            LOGGER.warning('Key error at {} ({})'.format(self.url, str(e)))

    def process(self):
        self.tag[self.attribute] = self.format_url(self.write_url(self.link))
        return self.tag[self.attribute]

    def handle_error(self):
        self.tag.replaceWith(self.create_broken_link_message(self.link))

    def handle_unscrapable(self):
        self.tag.replaceWith(self.create_copy_link_message(self.link))


class ImageTag(BasicScraperTag):
    default_ext = '.png'
    directory = "img"
    selector = ('img',)

    def process(self):
        if self.link and not self.link.startswith('data:image'):
            return super(ImageTag, self).process()

class MediaTag(BasicScraperTag):
    directory = "media"
    config = {
        'controls': 'controls',
        'preload': 'auto'
    }
    def process(self):
        if self.tag.find('source'):
            for source in self.tag.find_all('source'):
                self.source_class(source, self.zipper, self.url)
        else:
            return super(MediaTag, self).process()

class SourceTag(BasicScraperTag):
    selector = ('source',)

    def handle_error(self):
        self.tag.decompose()

class AudioSourceTag(SourceTag):
    default_ext = '.mp3'

class VideoSourceTag(BasicScraperTag):
    default_ext = '.mp4'

class AudioTag(MediaTag):
    default_ext = '.mp3'
    source_class = AudioSourceTag
    selector = ('audio',)

class VideoTag(MediaTag):
    default_ext = '.mp4'
    source_class = VideoSourceTag
    selector = ('video',)

class EmbedTag(BasicScraperTag):
    default_ext = '.pdf'
    directory = 'files'
    config = {
        'style': 'width:100%; height:500px;max-height: 100vh'
    }
    selector = ('embed',)

    def process(self):
        # No good way to tell what's in the tag, so link to page instead
        if not self.tag.get('src'):
            self.tag.replaceWith(self.create_copy_link_message(self.url))
            return

        # Automatically link any flash files
        if self.link.split('?')[0].split('#')[0].endswith('.swf'):
            self.tag.replaceWith(self.create_copy_link_message(self.url))
            return
        return super(EmbedTag, self).process()

class StyleTag(BasicScraperTag):
    default_ext = '.css'
    default_attribute = 'href'
    directory = 'css'
    selector = ('link', {'rel': 'stylesheet'})

    def process(self):
        if 'fonts' in self.link:  # Omit google fonts
            self.tag.decompose()
            return

        # Parse urls in css (using parseString because it is much faster than parseUrl)
        style_sheet = downloader.read(self.link).decode('utf-8-sig', errors='ignore')
        sheet = cssutils.parseString(style_sheet)
        for css_url in cssutils.getUrls(sheet):
            if not css_url.startswith('data:image') and not css_url.startswith('data:application'):
                try:
                    style_sheet = style_sheet.replace(css_url, os.path.basename(self.write_url(css_url, url=self.link, default_ext='.png')))
                except EXCEPTIONS as e:
                    LOGGER.warn('Unable to download stylesheet url at {} ({})'.format(self.url, str(e)))

        self.tag[self.attribute] = self.format_url(self.write_contents(self.get_filename(self.link), style_sheet))
        # if self.link.split('?')[0].endswith('.php'):
        #     import pdb; pdb.set_trace()
        return self.tag[self.attribute]

    def handle_error(self):
        self.tag.decompose()

class ScriptTag(BasicScraperTag):
    directory = 'js'
    default_ext = '.js'
    selector = ('script',)

    def process(self):
        if self.tag.string and 'google' in self.tag.string:
            self.tag.decompose()
        elif not self.link:
            return
        elif 'google' in self.link:
            self.tag.decompose()
        else:
            return super(ScriptTag, self).process()

    def handle_error(self):
        self.tag.decompose()

class LinkTag(BasicScraperTag):
    default_attribute = 'href'
    default_ext = '.html'
    config = {
        '_target': ''
    }
    selector = ('a',)

    def process(self):
        from pages import DEFAULT_PAGE_HANDLERS

        if not self.link or 'javascript:void' in self.link \
            or self.tag[self.attribute].startswith("#") or self.tag[self.attribute] == '/':
            return
        elif 'mailto' in self.link:
            self.tag.replaceWith(self.tag.text)
        elif 'creativecommons.org' in self.link:
            # Some links use the image as the link
            new_text = self.create_tag('b')
            new_text.string = self.tag.find('img').get('alt') if self.tag.find('img') else self.tag.text
            self.tag.replaceWith(new_text)

        elif not self.scrape_subpages:
            self.tag.replaceWith(self.tag.text)
            self.tag['style'] = 'font-weight: bold;'

        elif not self.triaged.get(self.link):
            # self.triaged[self.link] = self.get_filename(self.link)
            _, ext = os.path.splitext(self.link.split('?')[0].split('#')[0])

            # If it's a file that's linked, try to download it
            if ext and not ext.startswith('.htm') and not ext.startswith('.php') and not ext.startswith('.xml'):
                self.tag[self.attribute] =  self.write_url(self.link, directory="files")

            # Otherwise, try to download the page
            else:
                scraped = False
                for handler in (DEFAULT_PAGE_HANDLERS + self.extra_scrapers):
                    if handler.test(self.link):
                        self.triaged[self.link] = self.get_filename(self.link)
                        scraper = handler(self.link, self.zipper, locale=self.locale, triaged=self.triaged)
                        self.tag[self.attribute] = scraper.process(filename=self.get_filename(self.link))
                        scraped = True
                        break

                if not scraped:
                    downloader.read(self.link) # Will raise an error if this is broken
                    raise UnscrapableSourceException
        else:
            self.tag[self.attribute] = self.triaged[self.link]

    def handle_error(self):
        bold_tag = self.create_tag('b')
        bold_tag.string = self.tag.text
        self.tag.replaceWith(bold_tag)

    def handle_unscrapable(self):
        new_tag = self.create_tag('span')
        bold_tag = self.create_tag('b')
        bold_tag.string = self.tag.text
        new_tag.append(bold_tag)
        new_tag.append('({})'.format(self.link))
        self.tag.replaceWith(new_tag)


class IframeTag(BasicScraperTag):
    selector = ('iframe',)
    default_ext = '.html'
    config = {
        'style': 'resize:both;'
    }

    def process(self):
        from pages import DEFAULT_PAGE_HANDLERS

        if not self.link:
            pass
        elif 'googletagmanager' in self.link or 'googleads' in self.link:
            self.tag.decompose()
        else:
            scraped = False
            for handler in (DEFAULT_PAGE_HANDLERS + self.extra_scrapers):
                if handler.test(self.link):
                    scraper = handler(self.link, self.zipper, locale=self.locale, triaged=self.triaged)
                    if handler.standalone:
                        new_tag = scraper.process_tag()
                        self.tag.replaceWith(new_tag)
                        self.tag = new_tag
                    else:
                        self.tag[self.attribute] = scraper.process(filename=self.get_filename(self.link))

                    if scraper.partially_scrapable:
                        self.tag.insert_after(self.create_copy_link_message(self.link, partially_scrapable=True))
                    scraped = True
                    break

            if not scraped:
                downloader.read(self.link)
                raise UnscrapableSourceException


DEFAULT_HANDLERS = [
    ImageTag,
    StyleTag,
    ScriptTag,
    VideoTag,
    AudioTag,
    EmbedTag,
    LinkTag,
    IframeTag,
]
