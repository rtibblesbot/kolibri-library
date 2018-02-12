import requests
from bs4 import BeautifulSoup

sample_url = "https://artsedge.kennedy-center.org/educators/lessons/grade-9-12/Arthur_Miller_and_The_Crucible"

response = requests.get(sample_url)
soup = BeautifulSoup(response.content, "html5lib")


def nice_html(soup):
    # TODO: download urls, mangle p.printTabHeadline to h2, mangle urls
    prefix = b"""
    <html>
    <head>
      <link rel="stylesheet" type="text/css" href="resources/main.css">
      <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    </head>
    <body>
      <div class="main">
      <div class="wrap">
      <div class="content">
    """
    
    suffix = b"""
    </div></div></div>
    </body>
    </html>"""
    
    output = []
    output.append(prefix)
    for tab in soup.find_all("div", {'class': 'tabscontent'}):
        output.append(str(tab).encode('utf-8'))
    output.append(suffix)
    return b"\n\n<!-- dragon -->\n\n".join(output)
        
        
    
    
    
with open("output.html", "wb") as f:
    f.write(nice_html(soup))