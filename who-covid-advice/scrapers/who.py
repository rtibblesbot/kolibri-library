import os

from bs4 import BeautifulSoup
from le_utils.constants import content_kinds
from ricecooker.classes import nodes, files
from webmixer.scrapers.pages.base import PDFScraper, HTMLPageScraper, VideoScraper, WebVideoScraper
from webmixer.scrapers.pages.fullscreen import FullscreenPageScraper
from webmixer.scrapers.tags import LinkTag
from webmixer.utils import get_absolute_url


class ContentNodeMixin:
    def to_contentnode(self, title, directory=None, *args, **kwargs):
        filepath = self.to_file(directory=directory)
        if self.kind == content_kinds.HTML5:
            return nodes.HTML5AppNode(
                source_id=self.url,
                title=title,
                files=[files.HTMLZipFile(filepath)],
                **kwargs
            )
        elif self.kind == content_kinds.VIDEO:
            return nodes.VideoNode(
                source_id=self.url,
                title=title,
                files=[files.VideoFile(filepath)],
                **kwargs
            )


class ThumbnailTag(LinkTag):
    default_ext = '.png'
    directory = "img"
    selector = ('div', {'class': 'sf-image'})
    extra_scrapers = [FullscreenPageScraper]
    scrape_subpages = False

    def format_url(self, url):
        return get_absolute_url('https://www.who.int', url).replace('https://web-prod', 'https://www')

    def get_link(self):
        # Try to use the image if possible
        img = self.tag.find('img')
        if img:
            link = img.get('src') or img.get('data-src') or ''
        else:
            link = self.tag.find('a') or self.tag.find_parent('a')
            link = link and link['href']
        return self.format_url(link)

    def process(self):
        self.link = self.get_link()
        if 'sf-image' in self.tag['class']:
            div_tag = self.create_preview_tag(self.tag.find('img'))
            if self.tag.parent.name == 'a':
                self.tag.parent.replaceWith(div_tag)
            else:
                self.tag.replaceWith(div_tag)


    def create_preview_tag(self, img):
        # Some links might point to pdfs, so pass in img
        div_tag = self.create_tag('div')
        link_tag = self.get_scraper().to_tag()
        img_url = img.get('data-src') or img.get('src')
        if not img_url.startswith('img'):
            img['src'] = self.write_url(self.format_url(img_url), directory='img')
        img['style'] = []
        self.mark_tag_to_skip(img)
        link_tag.append(img)
        div_tag.append(link_tag)
        return div_tag


class HighlightWidgetTag(ThumbnailTag):
    default_ext = '.png'
    directory = "img"
    selector = ('div', {'class': 'highlight-widget'})
    extra_scrapers = [FullscreenPageScraper]
    scrape_subpages = False

    def get_link(self):
        link = self.tag.find('a') or self.tag.find_parent('a')
        return link and link['href'].replace('https://web-prod', 'https://www')

    def process(self):
        if not self.tag.find('a'):
            self.tag.decompose()
            return

        self.link = self.get_link()

        # Don't scrape main title
        if 'horizontal-title-only' in self.tag['class']:
            self.tag.decompose()

        # Links to other pages
        elif 'image-on-top' in self.tag['class']:
            self.create_external_link_tag()

        # Infographics
        elif 'title-only' in self.tag['class']:
            img = self.tag.parent.find('img')
            # Not all image links have available thumbnails, so make one
            if not img:
                img = self.create_tag('img')
                img['src'] = self.link
                preview_tag = self.create_preview_tag(img)
                self.tag.replaceWith(preview_tag)
            elif self.link.split('?')[0].endswith('.pdf'):
                preview_tag = self.create_preview_tag(img)
                self.tag.replaceWith(preview_tag)
            else:
                self.tag.decompose()

    def create_external_link_tag(self):
        # Create header
        div = self.create_tag('div')
        div['style'] = 'margin-bottom: 48px;text-align: center;'
        h3 = self.create_tag('h3')
        h3.string = self.tag.text.strip()
        div.append(h3)

        # Add image
        if self.tag.find('div', {'class': 'background-image'}):
            img = self.create_tag('img')
            img_url = self.tag.find('div', {'class': 'background-image'})['data-image']
            img['src'] = self.write_url(img_url, directory="img")
            img['style'] = 'max-width: 450px; width: 100%;'
            self.mark_tag_to_skip(img)
            div.append(img)

        # Add broken link copy
        copy = self.create_copy_link_message(self.link)
        div.append(copy)
        self.tag.parent['class'] = []
        self.tag.replaceWith(div)


class FigureTag(HighlightWidgetTag):
    selector = ('div', {'class': 'sf-multimedia-item__infographic'})

    def process(self):
        self.link = self.get_link()
        img = self.create_tag('img')
        img['src'] = self.link
        preview_tag = self.create_preview_tag(img)
        self.tag.replaceWith(preview_tag)


class ExternalLinkTag(LinkTag):
    def process(self):
        if self.link:
            self.tag.replaceWith(self.create_copy_link_message(self.link))


class WHOPageScraper(HTMLPageScraper, ContentNodeMixin):
    color = "#008DC9"
    scrape_subpages = False
    extra_tags = [FigureTag, ThumbnailTag, HighlightWidgetTag, ExternalLinkTag]
    omit_list = [
        ('script',),
        ('header',),
        ('ul', {'class': 'sf-breadscrumb'}),
        ('footer', {'id': 'sf-footer'}),
        ('input', {'type': 'hidden'}),
    ]

    @classmethod
    def test(self, url):
        return 'www.who.int' in url

    def preprocess(self, contents):
        # Remove side navigation
        navigation = contents.find('div', {'class': 'left-navigation--wrapper'})
        navigation.parent.decompose()

        # Make sure styling is applied
        main_row = contents.find('div', {'class': 'row'})
        main_row['class'].append('sf-body')

    def to_tag(self, *args):
        return self.create_tag('div')

class WHOVideoScraper(VideoScraper, ContentNodeMixin):
    pass

class WHOWebVideoScraper(WebVideoScraper, ContentNodeMixin):
    pass
