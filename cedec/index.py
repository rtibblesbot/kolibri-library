import requests
import lxml.html
import subprocess
from subprocess import PIPE
from pathlib import Path
import os
import requests_cache
requests_cache.install_cache()
ELP = Path("elp/")
ZIP = Path("zip/")

def elp_to_zip(elp_url):
    filename = elp_url.split("/")[-1]
    try:
        os.mkdir(ELP)
    except FileExistsError:
        pass
    try:
        os.mkdir(ZIP)
    except FileExistsError:
        pass
    zipfilename = filename + ".zip"
    if os.path.isfile(ZIP/zipfilename):
        return zipfilename
    with open(ELP/filename, "wb") as f:
        f.write(requests.get(elp_url).content)
    invocation = ["exe_do", "--export", "webzip", str(ELP/filename), str(ZIP/zipfilename)]
    print (repr(" ".join(invocation)))
    output = subprocess.run(invocation,
            stdout = PIPE,
            stderr = PIPE)
    stderr = output.stderr

    print (filename)
    print (stderr.decode('utf-8'))
    exit()
    return zipfilename

# TODO - fix encoding
BASE_URL = "http://cedec.intef.es/recursos/"

html = requests.get(BASE_URL).content
root = lxml.html.fromstring(html)
root.make_links_absolute(BASE_URL)
links = root.xpath("//div[@id='icon']/a/@href")
print (links)

for link in links:
    html = requests.get(link).content
    root = lxml.html.fromstring(html)
    root.make_links_absolute(link)
    elps = root.xpath("//td[@class='column-4']/a")
    for elp in elps:
        grouping, = elp.xpath("./preceding::h2[1]")
        print (grouping.text_content().strip())
        title, = elp.xpath("./preceding::strong[1]")
        print (title.text_content().strip())
        elp_url = elp.attrib['href']
        elp_to_zip(elp_url)
    print()
