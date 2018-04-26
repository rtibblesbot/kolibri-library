#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from git import Repo
import logging
import markdown
import ntpath
import os
from pathlib import Path
import re
from ricecooker.utils import downloader, html_writer
from utils import if_dir_exists, get_name_from_url, clone_repo, build_path
from utils import if_file_exists


BASE_URL = "https://github.com/Laboratoria/curricula-js.git"
DATA_DIR = "chefdata"
#COPYRIGHT_HOLDER = "The Open University"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)


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
            a["href"] = "{}{}/{}".format(self.page.extra_files_path, dirname, "index.html")
            #ul.append("<li><a href='{}'>{}</a></li>".format(dirname, a.text))
            dirs.append(dirname)
        #ul.append("</ul>")
        #self.ul = "".join(ul)
        return dirs

    def write_index(self, filepath):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(self.page.to_string())

    def write_contents(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            content = '<html><head><meta charset="UTF-8"></head><body>{}</body></html>'.format(
                self.page.to_string())
            zipper.write_contents(filepath, content, directory=self.page.extra_files_path)


class Markdown(object):
    def __init__(self, filepath, extra_files_path=""):
        self.filepath = filepath
        self.images = {}
        self.copyright = None
        self.extra_files_path = extra_files_path
        self.root = None

    def exists(self):
        return if_file_exists(self.filepath)

    def load(self):
        self.content = self.parser(self.to_html())
        if self.content is not None:
            self.get_copyright(self.content)
            self.get_images(self.content)

    def to_html(self):
        try:
            with codecs.open(self.filepath, mode="r", encoding="utf-8") as input_file:
                text = input_file.read()
                html = markdown.markdown(text, output_format="html")
        except FileNotFoundError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            return '<html><head><meta charset="UTF-8"></head><body>'+html+'</body></html>'

    def to_string(self):
        return str(self.content)

    def parser(self, document):
        if document is not None:
            return BeautifulSoup(document, 'html.parser')

    def get_images(self, content):
        for img in content.findAll("img"):
            if "src" in img.attrs:
                if img["src"].startswith("/"):
                    img_src = urljoin(BASE_URL, img["src"])
                else:
                    img_src = img["src"]
            
                if img_src not in self.images and img_src:
                    filename = get_name_from_url(img_src)
                    img["src"] = self.extra_files_path+filename
                    self.images[img_src] = filename

    def read_localdir(self):
        try:
            directory = self.filepath.split("/")[:-1]
            path = "/".join(directory)
            if if_dir_exists(path):
                return os.listdir(path)
            else:
                return []
        except FileNotFoundError as e:
            LOGGER.info("Error: {}".format(e))
            return []

    def write_images(self):
        with html_writer.HTMLWriter(self.root, "a") as zipper:
            for img_src, img_filename in self.images.items():
                try:
                    zipper.write_url(img_src, img_filename, directory=self.extra_files_path)
                except requests.exceptions.HTTPError:
                    pass

    def get_copyright(self, content):
        h2 = content.find(lambda tag: tag.name == "h2" and\
            tag.text.find("Copyright") != -1)
        if h2 is not None:
            self.copyright = h2.findNext('p')
        else:
            self.copyright = None

    def write_index(self, filepath, main_index=True):
        menu = Menu(self)
        if main_index is True:
            menu.write_index(filepath)
        else:
            menu.write_contents(filepath)
        self.root = filepath
        return menu


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
            menu = readme.write_index(base_dir, main_index=False)
            subdirs = menu.subdirs
        else:
            subdirs = readme.read_localdir()
            print("Readme does not exists")
        folder_walker(os.path.join(repo_dir, directory), subdirs)
    

if __name__ == '__main__':
    repo_dir = os.path.join("/tmp/", "curricula-js")
    #clone_repo(BASE_URL, repo_dir)
    readme = Markdown(os.path.join(repo_dir, "README.md"), extra_files_path="files/")
    readme.load()
    base_dir = os.path.join(build_path([DATA_DIR]), "index.zip")
    menu = readme.write_index(base_dir, main_index=True)
    readme.write_images()
    folder_walker(repo_dir, menu.subdirs)
    #for page in menu.subdirs:
    #    print(page)
    #    readme = Markdown(os.path.join(repo_dir, page, "README.md"), extra_files_path="files/")
    #    readme.load()
    #    menu = readme.write_index(base_dir, main_index=False)
    #    print(menu.subdirs)
        #break
