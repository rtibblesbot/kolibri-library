#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from git import Repo
from le_utils.constants import licenses, content_kinds, file_formats
import logging
import markdown
import ntpath
import os
from pathlib import Path
import re
import requests

from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
#from urllib.error import URLError, urlencode
from urllib.parse import urljoin
from utils import if_dir_exists, get_name_from_url, clone_repo, build_path
from utils import if_file_exists


BASE_URL = "https://github.com/Laboratoria/"
REPOSITORY_URL = "https://github.com/Laboratoria/curricula-js.git"
DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = ""

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)


sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)


#check if any google docs are avaible
class Menu(object):
    def __init__(self, index):
        self.page = index
        self.subdirs = self.build_list()

    def build_list(self):
        dirs = []
        pattern = re.compile('\d{1,2}\-')
        if self.page.content is None:
            return dirs
        links = self.page.content.find_all(lambda tag: tag.name == "a" and tag.findParent("h3"), href=pattern)
        #ul = ["<ul>"]        
        for a in links:
            dirname = a["href"]
            a["href"] = ""#"{}{}/{}.html".format(self.page.extra_files_path, dirname, "index")
            #print("URL MENU", a["href"])
            #ul.append("<li><a href='{}'>{}</a></li>".format(dirname, a.text))
            dirs.append(dirname)
        #ul.append("</ul>")
        #self.ul = "".join(ul)
        return dirs

    def write_index(self):
        path = [DATA_DIR] + self.page.pwd[2:]
        path = build_path(path)
        with html_writer.HTMLWriter(os.path.join(path, "index.zip"), "w") as zipper:
            zipper.write_index_contents(str(self.page.content))

    def write_images(self):
        path = [DATA_DIR] + self.page.pwd[2:]
        path = build_path(path)
        with html_writer.HTMLWriter(os.path.join(path, "index.zip"), "a") as zipper:
            for img_src, img_filename in self.page.get_images().items():
                try:
                    zipper.write_url(img_src, img_filename, directory=self.page.extra_files_path)
                except (requests.exceptions.HTTPError, requests.exceptions.SSLError):
                    pass

    def write_pdfs(self):
        path = [DATA_DIR] + self.page.pwd[2:]
        path = build_path(path)
        for pdf in self.page.get_pdfs():
            pdf.download(path)
            yield pdf.to_node()

    def to_node(self):
        pass

    #def write_contents(self, filepath):
    #    with html_writer.HTMLWriter(filepath, "a") as zipper:
    #        content = '<html><head><meta charset="UTF-8"></head><body>{}</body></html>'.format(
    #            self.page.to_string())
    #        path = [DATA_DIR] + self.page.pwd[3:]
    #        path = build_path(path)
    #        zipper.write_contents(os.path.join(path, "index.html"), content, directory=self.page.extra_files_path)


class Markdown(object):
    def __init__(self, filepath, extra_files_path=""):
        self.filepath = filepath
        self.copyright = None
        self.extra_files_path = extra_files_path
        self.htmlzip_filepath = None
        self.pwd = self.filepath.split("/")[:-1]
        self.copyright = None

    def exists(self):
        return if_file_exists(self.filepath)

    def load(self):
        self.content = self.parser(self.to_html())
        if self.content is not None:
            self.get_copyright(self.content)

    def to_html(self):
        try:
            with codecs.open(self.filepath, mode="r", encoding="utf-8") as input_file:
                text = input_file.read()
                html = markdown.markdown(text, output_format="html")
        except FileNotFoundError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            return '<html><head><meta charset="UTF-8"></head><body>'+html+'</body></html>'

    def parser(self, document):
        if document is not None:
            return BeautifulSoup(document, 'html.parser')

    def get_images(self):
        images = {}
        for img in self.content.findAll("img"):
            if "src" in img.attrs:
                if img["src"].startswith("/"):
                    img_src = urljoin(BASE_URL, img["src"])
                elif not img["src"].startswith("http"):
                    img_src = urljoin(BASE_URL, "/".join(self.pwd[2:]), img["src"])
                else:
                    img_src = img["src"]
            
                if img_src not in images and img_src:
                    filename = get_name_from_url(img_src)
                    img["src"] = self.extra_files_path+filename
                    images[img_src] = filename
        return images

    def get_pdfs(self):
        unique_urls = set([])
        for a in self.content.findAll(lambda tag: tag.name == "a" and tag.attrs.get("href", "").endswith(".pdf")):
            url = a.get("href", "")
            if url not in unique_urls and url:
                yield File(url, lang="es")
                unique_urls.add(url)

    def read_localdir(self):
        try:
            path = "/".join(self.pwd)
            if if_dir_exists(path):
                return os.listdir(path)
            else:
                return []
        except FileNotFoundError as e:
            LOGGER.info("Error: {}".format(e))
            return []

    def get_copyright(self, content):
        h2 = content.find(lambda tag: tag.name == "h2" and\
            tag.text.find("Copyright") != -1)
        if h2 is not None:
            self.copyright = h2.findNext('p')

    def write(self):
        menu = Menu(self)
        menu.write_index()
        menu.write_images()
        for node in menu.write_pdfs():
            node
        return menu


class File(object):
    def __init__(self, source_id, lang="en", lincese=""):
        self.filename = get_name_from_url(source_id)
        self.source_id = urljoin(BASE_URL, source_id) if source_id.startswith("/") else source_id
        self.filepath = None
        self.lang = lang
        self.license = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def download(self, base_path):
        PDFS_DATA_DIR = build_path([base_path, 'pdfs'])
        try:
            response = sess.get(self.source_id)
            content_type = response.headers.get('content-type')
            if 'application/pdf' in content_type:
                self.filepath = os.path.join(PDFS_DATA_DIR, self.filename)
                with open(self.filepath, 'wb') as f:
                    for chunk in response.iter_content(10000):
                        f.write(chunk)
                LOGGER.info("   - Get file: {}".format(self.filename))
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        except requests.exceptions.ReadTimeout as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))

    def to_node(self):
        if self.filepath is not None:
            node = dict(
                kind=content_kinds.DOCUMENT,
                source_id=self.source_id,
                title=self.filename,
                description='',
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=self.license)
            return node

#def read_markdown(filepath):
#    input_file = codecs.open(filepath, mode="r", encoding="utf-8")
#    text = input_file.read()
#    html = markdown.markdown(text, output_format="html")
#    output_file = codecs.open("/tmp/README.html", "w",
#                          encoding="utf-8",
#                          errors="xmlcharrefreplace")
#    output_file.write(html)


def folder_walker(repo_dir, dirs):
    for directory in dirs:
        print("---", repo_dir, directory)
        readme = Markdown(os.path.join(repo_dir, directory, "README.md"), extra_files_path="files/")
        if readme.exists():
            readme.load()
            menu = readme.write()#base_dir, main_index=False)
            subdirs = menu.subdirs
        else:
            subdirs = readme.read_localdir()
            print("Readme does not exists")
        folder_walker(os.path.join(repo_dir, directory), subdirs)
    

if __name__ == '__main__':
    repo_dir = os.path.join("/tmp/", "curricula-js")
    #clone_repo(REPOSITORY_URL, repo_dir)
    readme = Markdown(os.path.join(repo_dir, "README.md"), extra_files_path="files/")
    readme.load()
    COPYRIGHT_HOLDER = readme.copyright
    base_dir = os.path.join(build_path([DATA_DIR]), "index.zip")
    menu = readme.write()#base_dir, main_index=True)
    #readme.write_images()
    folder_walker(repo_dir, menu.subdirs)
    #for page in menu.subdirs:
    #    print(page)
    #    readme = Markdown(os.path.join(repo_dir, page, "README.md"), extra_files_path="files/")
    #    readme.load()
    #    menu = readme.write_index(base_dir, main_index=False)
    #    print(menu.subdirs)
        #break
