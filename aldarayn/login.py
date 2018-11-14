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

course_index = Page("https://www.aldarayn.com/course/index.php")
courses = course_index.root.xpath("//h3[@class='categoryname']/a")
course_names = [x.text for x in courses]
course_urls = [x.get('href') for x in courses]

def get_solo_course(categoryid, page=0):
    data = {"categoryid": categoryid,
            "depth": 9999,  # 1
            "showcourses": 9999, # 15  # increasing doesn't help :(
            "type": 0, # 0
            "limit": 99999} # guesswork!
    
    html = session.post("https://www.aldarayn.com/course/category.ajax.php", data=data).json()
    root = lxml.html.fromstring(html)
    links = root.xpath("//a")
    link_data = ([[x.get('href'), x.text_content()] for x in links])
    
    # split links into different categories 
    categories = [x for x in link_data if "?categoryid=" in x[0] and "&page=" not in x[0]]
    views = [x for x in link_data if "/view.php?" in x[0]]
    info = [x for x in link_data if "/info.php?" in x[0]]  # throw these away
    page_data = [x for x in link_data if "&page=" in x[0]]
    
    missed_links = set(x[0] for x in link_data) - \
                   set(x[0] for x in categories) - \
                   set(x[0] for x in views) - \
                   set(x[0] for x in info) - \
                   set(x[0] for x in page_data)
    
    assert not missed_links, missed_links
    assert len(page_data) <= 1
    if page_data:
        print("newpage?")
        print(page_data)
        newpage = page + 1
        print (categories, views, info)
        triplet = get_solo_course(categoryid, newpage)  # TODO -- get triplet into output values
        
    return categories, views, info
    


def get_course(categoryid, depth=1): # demo=13
    categories, views, info = get_solo_course(categoryid)
    
    for item in views:
        print (" "*depth*2, item)
        
    for cat in categories:
        print (" "*depth*2, cat)
        get_course(cat[0].partition("=")[2], depth=depth+1)

#for item in course_urls:
#    print (item)
#    get_course(item[0].partition("=")[2])

get_course(3)
            

