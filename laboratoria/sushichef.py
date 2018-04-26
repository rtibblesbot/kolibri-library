#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from git import Repo
import markdown
import ntpath
import os
from pathlib import Path
import re
from ricecooker.utils import downloader, html_writer
from utils import if_dir_exists, get_name_from_url, clone_repo


BASE_URL = "https://github.com/Laboratoria/curricula-js.git"
DATA_DIR = "chefdata"
#COPYRIGHT_HOLDER = "The Open University"


#check if any google docs are avaible
class Menu(object):
    def __init__(self, index):
        self.page = index
        self.subdirs = self.build_list()

    def build_list(self):
        pattern = re.compile('\d{1,2}\-')
        links = self.page.content.find_all(lambda tag: tag.name == "a" and tag.findParent("h3"), href=pattern)
        #ul = ["<ul>"]
        dirs = []
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

    def write_content(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            content = '<html><head><meta charset="UTF-8"></head><body>{}</body></html>'.format(
                content)
            zipper.write_contents(filepath, content, directory=directory)


class Markdown(object):
    def __init__(self, filepath, extra_files_path=""):
        self.filepath = filepath
        self.images = {}
        self.copyright = None
        self.extra_files_path = extra_files_path
        self.root = None

    def load(self):
        self.content = self.parser(self.to_html())
        self.get_copyright(self.content)
        self.get_images(self.content)

    def to_html(self):
        with codecs.open(self.filepath, mode="r", encoding="utf-8") as input_file:
            text = input_file.read()
            html = markdown.markdown(text, output_format="html")
        return "<html><body>"+html+"</body></html>"

    def to_string(self):
        return str(self.content)

    def parser(self, document):
        return BeautifulSoup(document, 'html.parser')

    def get_images(self, content):
        for img in content.findAll("img"):
            if img["src"].startswith("/"):
                img_src = urljoin(BASE_URL, img["src"])
            else:
                img_src = img["src"]
            
            if img_src not in self.images and img_src:
                filename = get_name_from_url(img_src)
                img["src"] = self.extra_files_path+filename
                self.images[img_src] = filename

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


def get_models_path(base_path, dirname):
    #_, c, files = next(os.walk(path))
    return os.listdir(os.path.join(base_path, dirname))


if __name__ == '__main__':
    repo_dir = os.path.join("/tmp/", "curricula-js")
    #clone_repo(BASE_URL, repo_dir)
    readme = Markdown(os.path.join(repo_dir, "README.md"), extra_files_path="files/")
    readme.load()
    menu = readme.write_index("/tmp/index.zip", main_index=True)
    readme.write_images()
    for page in menu.subdirs:
        readme = Markdown(os.path.join(repo_dir, page, "README.md"), extra_files_path="files/")
        readme.load()
        menu = readme.write_index("/tmp/index.zip", main_index=False)
        print(menu.subdirs)
        break
    #content = readme.parser(readme.to_html())
    #readme.copyright(content)
    #readme.get_images(content)
