import requests
import requests_cache
import lxml.html
import re
from urllib.parse import urljoin
requests_cache.install_cache()  # WARNING: May cache stale unlogged in data.
session = requests.Session()

rawheaders = """
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Accept-Encoding: gzip, deflate, br
Accept-Language: en-GB,en-US;q=0.9,en;q=0.8
Cache-Control: no-cache
Connection: keep-alive
Cookie: has_js=1
DNT: 1
Host: www.nashmi.net
Origin: https://www.nashmi.net
Pragma: no-cache
X-Referer: https://www.nashmi.net/ar/user
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/71.0.3578.98 Chrome/71.0.3578.98 Safari/537.36
""".strip()

rawheaders_detail = """
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Accept-Encoding: gzip, deflate, br
Accept-Language: en-GB,en-US;q=0.9,en;q=0.8
Cache-Control: no-cache
Connection: keep-alive
Cookie: has_js=1; SSESSb5d96a45fb92cee9b9c59b85294fc5f6=Q-_2p30vSoIw3pjwQQ2iZf3LSzkTgrIi6DojHaZz7Oc
DNT: 1
Host: www.nashmi.net
Pragma: no-cache
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/71.0.3578.98 Chrome/71.0.3578.98 Safari/537.36
""".strip()

le_rawheaders_detail = """
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Accept-Encoding: gzip, deflate, br
Accept-Language: en-GB,en-US;q=0.9,en;q=0.8
Cache-Control: no-cache
Connection: keep-alive
Cookie: has_js=1; SSESSb5d96a45fb92cee9b9c59b85294fc5f6=Mk1k2BmgLd6jNmfyvrSQJnpP73FAATRqsAX9v3QPsXU; SESSb5d96a45fb92cee9b9c59b85294fc5f6=oMKsYHiW0cDQ0DTxwdqTNZCfheEVvqkMiUnPOMFbfnQ
DNT: 1
Host: www.nashmi.net
Pragma: no-cache
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/71.0.3578.98 Chrome/71.0.3578.98 Safari/537.36
""".strip()


headers = dict([[h.partition(': ')[0], h.partition(': ')[2]] for h in rawheaders.split('\n')])
headers_detail = dict([[h.partition(': ')[0], h.partition(': ')[2]] for h in rawheaders_detail.split('\n')])
le_headers_detail = dict([[h.partition(': ')[0], h.partition(': ')[2]] for h in le_rawheaders_detail.split('\n')])


def do_login():
    user_url = "http://nashmi.net/ar/user"
    r = session.get(user_url).content
    root = lxml.html.fromstring(r)
    build_id, = root.xpath("//input[@name='form_build_id']/@value")
    print(build_id)
    p = session.post(user_url,
                     data={
                         "name": "dragon",
                         "pass": 'password',
                         "form_build_id": build_id,
                         "form_id": "user_login",
                         "op": "\u062a\u0633\u062c\u064a\u0644\u0020\u062f\u062e\u0648\u0644"
                     },
                     headers=headers,
                     )

    assert "dragon" in p.url  # logged in test


BASE_URL = "https://www.nashmi.net/ar"
# do_login() -- currently not working for some reason, we have hardcoded cookie instead.

def abs_links(urls):
    return [urljoin(BASE_URL, url) for url in urls]

class Root(object):
    def __init__(self, url):
        self.url = url
        self.response = session.get(self.url, headers=le_headers_detail)
        self.html = self.response.content
        self.root = lxml.html.fromstring(self.html)

top = Root(BASE_URL)
top.children = abs_links(top.root.xpath("//div[@class='views-field views-field-name-1']/a/@href"))
top.childnames = [x.text_content().strip() for x in top.root.xpath("//div[@class='views-field views-field-name-1']/a")]

def get_lectures():
    for cat_url, cat_name in zip(top.children, top.childnames):
        cat = Root(cat_url)
        #cat.title = cat.root.xpath("//h1")[0].text_content().strip()
        cat.title = cat_name
        cat.courses = abs_links(cat.root.xpath("//span[@class='field-content']/a/@href"))
        for course_url in cat.courses:
            course = Root(course_url)
            course.title = course.root.xpath("//h1")[0].text_content().strip()
            course.lectures = abs_links(course.root.xpath("//span[@class='field-content']/a/@href"))
            course.lecturenames = [x.text_content().strip() for x in course.root.xpath("//span[@class='field-content']/a")]
            assert not any("/user?" in x for x in course.lectures)
            # these links appear OK but will redirect to /user? if followed
            lectures = zip(course.lectures, course.lecturenames)
            for lecture in lectures:
                yield (course_url, cat.title, course.title, lecture[1], lecture[0])


if __name__ == "__main__":
    get_lectures()
    exit()

    ###

    lecture_url = "https://www.nashmi.net/ar/content/%D8%A7%D9%84%D9%86%D9%87%D8%A7%D9%8A%D8%A7%D8%AA-%D9%85%D9%86-%D8%AE%D9%84%D8%A7%D9%84-%D8%A7%D9%84%D8%AA%D8%B9%D9%88%D9%8A%D8%B6-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%B4%D8%B1-%D8%AD%D8%B5%D8%A9-1"

    lecture = Root(lecture_url)
    assert "user?" not in lecture.response.url, "should be logged in."
    lecture.scripts = [x.text_content() for x in lecture.root.xpath("//script")]
    lecture.scripts_clean = [x for x in lecture.scripts if '"file"' in x]
    lecture.video_urls = [re.search('{"file":"([^"]+)"}', x).group(1) for x in lecture.scripts_clean]
    print (lecture.video_urls)
