import requests
import json
from bs4 import BeautifulSoup
from io import BytesIO
from zipfile import ZipFile
#import lxml.html
#from lxml.html.clean import Cleaner

html_template = """
<html>
  <head>
    <meta charset="utf-8">
    <link rel="stylesheet" type="text/css" href="styles.css">
    <title>{title}</title>
  </head>
  <body>
  <h1>{title}</h1>
  <p><img src="{img}"></p>
    {body}
  </body>
</html>"""

def make_zip(body, title, img):
    io = BytesIO()
    with ZipFile(io, mode="w") as z:
        z.writestr("index.html", html_template.format(body=body, title=title, img=img))
        z.write("styles.css")
    return io.getvalue()

def ap(o):
    # take a string-like object and render awkward characters as lower-case gibberish
    # avoids problems like ligatures and rtl text not rendering correctly 
    def bowdler(char):
        if ord(char)<256:
            return char
        return chr(ord(char) % 26 + 96)
    
    text = str(o)
    print (''.join([bowdler(i) for i in text]))

url = "https://www.nok6a.net/wp-admin/admin-ajax.php"
r = requests.post(url, data={'action': 'load_posts',
                             'next_page': 2,
                             'cat': 34,
                             'tag': ''})
j = json.loads(r.text)
## print (j.keys())  ## note there is a max_pages response!
soup = BeautifulSoup(j['html'], "html5lib")
for panel in soup.findAll("div", {"class": "panel"}):
    h2 = panel.find("h2")
    a = h2.find("a")
    ap("*"+ a['href'])
    break

video_url = "https://www.nok6a.net/%D9%85%D8%A7-%D9%87%D9%8A-%D8%AA%D9%82%D9%86%D9%8A%D8%A9-%D9%87%D8%A7%D9%8A%D8%A8%D8%B1%D9%84%D9%88%D8%A8%D8%9F-%D9%83%D9%8A%D9%81-%D8%AA%D8%B9%D9%85%D9%84%D8%9F-%D9%87%D9%84-%D8%B3%D8%AA%D8%BA%D9%8A/"
r = requests.get(video_url)
soup = BeautifulSoup(r.text, "html5lib")

#block = soup.find("div", {"class": "post-block"})
#
#
#block.decompose()
for _class in ["post-block", "post-views-label", "post-views-icon", "post-views-count", "shareaholic-canvas", "post-views"]:
    tag = soup.find(None, {"class": _class})
    if tag:
        tag.decompose()
        
for tagname in ["ins", "script"]:
    tags = soup.findAll(tagname)
    for tag in tags:
        tag.decompose()
    
        
body = soup.find("div", {"class": "post-text"})       
#ap(body)
title = soup.find("h1", {"class": "post-title"}).text
#ap(title)
img = soup.find("div", {"class": "post-img"}).find("img")['src']
#ap(img)
with open("zipdemo.zip", "wb") as f:
    f.write(make_zip(body, title, img))


## //div[@class='post-text'] -- bulk of text
##/div[@class='post-block'] -- kill this, it's in post-text but take
##/h1[@class='post-title']  -- outside of post-text, is title.
## //div[@class='post-img']/img/@src -- start image [outside]



