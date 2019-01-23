import lxml.html
import requests
from urllib.parse import urljoin
import re

class Lesson(object):
    def __repr__(self):
        return "\n".join(("Video IDs", str(self.video_ids), "Desc", self.desc, "Resources", str(self.resources)))

def lesson(lesson_url):
    L = Lesson()
    response = requests.get(lesson_url).content
    root = lxml.html.fromstring(response)
    L.video_ids = []
    for script in root.xpath("//script"):
        code = script.text_content()
        if "YouTube" not in code:
            continue
        L.video_ids.extend(re.search("video: '([^']*)',", code).groups(1))
    assert L.video_ids
    bigdesc = root.xpath("//div[@class='video__introduction wysiwyg']")[0].text_content()
    smalldesc = root.xpath("//div[@class='video__body wysiwyg']/p")[0].text_content()
    L.desc = bigdesc + "\n" + smalldesc
    raw_resources = root.xpath("//div[@class='video__body wysiwyg']//a/@href")
    L.resources = [get_resource(urljoin(lesson_url, x)) for x in raw_resources]
    return L

def get_resource(url):
    response = requests.get(url).content
    root = lxml.html.fromstring(response)
    new_url, = root.xpath("//h1[@class='resource__title']/a/@href")
    return new_url

if __name__ == "__main__":
    print (lesson("https://www.careergirls.org/video/performing-arts-careers/?back=60"))
