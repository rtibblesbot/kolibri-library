import requests
import lxml.html
#import json
import credentials


class Page():
    def __init__(self, url):
        self.url = url
        self.response = session.get(url)
        self.root = lxml.html.fromstring(self.response.content)

session = requests.session()

response = session.post("https://www.aldarayn.com/login/index.php", data = credentials.login)
assert response.url == "https://www.aldarayn.com/my/", response.url

def top_index():
    """Have manually checked: this is complete for categorynames in course_index"""
    page = Page("https://www.aldarayn.com/course/index.php?categoryid=17")
    options = page.root.xpath("//option")
    option_ids = [x.get("value") for x in options]
    option_names = [x.text for x in options]
    return zip(option_ids, option_names)

print (list(top_index()))
exit()

def course_index(course_id):
    page = Page("https://www.aldarayn.com/course/index.php?categoryid={}&perpage=99999999".format(course_id))
    course_tags = page.root.xpath("//*[@class='coursename']/a")
    course_names = [x.text for x in course_tags]
    course_urls = [x.get('href') for x in course_tags]
    for i, j in zip(course_names, course_urls):
        print(i,j)

for i in top_index():
    print (i)
    course_index(i[0])
