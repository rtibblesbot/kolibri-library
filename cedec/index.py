import requests
import lxml.html
import subprocess
from subprocess import PIPE
from pathlib import Path
import os
import requests_cache
import zipfile

requests_cache.install_cache()
ELP = Path("elp/")
ZIP = Path("zip/")

my_env = os.environ.copy()
my_env["PYTHONIOENCODING"] = "utf-8"

ns={'exe': 'http://www.exelearning.org/content/v0.3'}

def elp_metadata(elp_filename):
    def query(s):
        response, = root.xpath("/exe:instance/exe:dictionary/exe:string[@value='"+s+"']/following-sibling::exe:unicode[1]/@value", namespaces=ns)
        return response

    with zipfile.ZipFile(elp_filename, "r") as zf:
        with zf.open("contentv3.xml") as xml:
            data = xml.read()
            root = lxml.etree.fromstring(data)
            print ("T",query('_title'))
            print ("A",query('_author'))
            print ("D", query('_description'))


def elp_to_zip(elp_url):
    print()
    print(elp_url)
    filename = elp_url.partition("cedec")[2].replace("/", "_")
    try:
        os.mkdir(ELP)
    except FileExistsError:
        pass
    try:
        os.mkdir(ZIP)
    except FileExistsError:
        pass
    zipfilename = filename + ".zip"
    if os.path.isfile(ELP/filename):
        print (f"WARNING: {ELP/filename} exists")
    if not os.path.isfile(ZIP/zipfilename):
        with open(ELP/filename, "wb") as f:
            f.write(requests.get(elp_url).content)
        invocation = ["exe_do", "--export", "webzip", str(ELP/filename), str(ZIP/zipfilename)]
        output = subprocess.run(invocation,
                stdout = PIPE,
                stderr = PIPE,
                env = my_env)

        stdout = output.stdout.decode('utf-8')
        stderr = output.stderr.decode('utf-8')
        print(stdout)
        print(stderr)
        assert not output.returncode
        assert "error was" not in stdout
    elp_metadata(ELP/filename)
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
    elps = root.xpath("//a")

    for elp in elps:
        elp_url = elp.attrib['href']
        if not elp_url.endswith(".elp"):
            continue
        try:
            grouping, = elp.xpath("./preceding::h2[1]")
            print (grouping.text_content().strip())
    #        title, = elp.xpath("./preceding::strong[1]")
    #        title, = elp.xpath("./preceding::a[contains(@href, '.html') and text()][1]")
            #title, = elp.xpath("./preceding::td[@class='column-1']//a[1]")
            #print (title.text_content().strip())
        except:
            print (link)
            raise
        elp_to_zip(elp_url)
    print()
