import lxml.html
import login
import json
import index

session = login.session

class NoVideoError(Exception):
    pass

class Page():
    def __init__(self, url):
        self.url = url
        self.response = session.get(url)
        self.root = lxml.html.fromstring(self.response.content)

url_1 = "https://www.aldarayn.com/course/view.php?id=525" # videos
# url_2 = "https://www.aldarayn.com/course/view.php?id=614" # wiz

def is_known(url, known_list):
    results = [item in url for item in known_list]
    return any(results)

def reduce_activities(urls):
    bad_urls = ["/forum/", "/wiziq/"]
    good_urls = ["/mod/page/"]
    reduced_urls = [url for url in urls if not is_known(url, bad_urls)]
    unknown_urls = [url for url in reduced_urls if not is_known(url, good_urls)]
    assert not unknown_urls, unknown_urls

def handle_page(url):
    page = Page(url)
    body, = page.root.xpath("//ul[@class='section img-text']")
    videos = body.xpath(".//video")
    raw_activity_urls = body.xpath("//div[@class='activityinstance']/a/@href")

    if not videos:
        raise NoVideoError("No videos on {}".format(url))

    for video in videos:
        data_setup = video.get("data-setup")
        j_data = json.loads(data_setup)
        #print (j_data['sources'][0]['src'])

for _id, name1, name2, url in index.all_courses():
    #print (name1, name2, url)
    try:
        handle_page(url)
    except NoVideoError as e:
        print (e)
    except:
        print (e, url)


#handle_page(url_1)
#handle_page(url_2)
