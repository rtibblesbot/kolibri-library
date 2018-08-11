import requests
import lxml.html
from lxml.html.clean import Cleaner
import requests_cache
import re
from urllib.parse import urljoin
from zipfile import ZipFile
from io import BytesIO
requests_cache.install_cache()

super_cluster_url = "https://www.careergirls.org/explore-careers/career-clusters/"

html_template = """
<html>
  <head>
    <link rel="stylesheet" type="text/css" href="styles.css">
    <title>Resource</title>
  </head>
  <body>
    {}
  </body>
</html>"""



def clean_html(source):
    "see https://lxml.de/4.1/api/lxml.html.clean.Cleaner-class.html"
    "Note that this mangles the original structure!"
    cleaner = Cleaner(scripts = True,
                      javascript = True,
                      comments = True,
                      style = True, # maybe not 
                      inline_style = True, # maybe not
                      links = True,
                      meta = True,
                      page_structure = False,
                      processing_instructions = True,
                      embedded = True,
                      frames = True,
                      forms = True,
                      annoying_tags = True,
                      remove_tags = ['a', 'div', 'span', 'svg'],
                      kill_tags = [], # also destroys content, unlike remove
                      ## allow_tags = [], # default all
                      remove_unknown_tags = True,
                      safe_attrs_only = True,
                      safe_attrs = [], # default: sane
                      add_nofollow = True,
                      host_whitelist = [],
                      ## whitelist_tags = [], # default: sane
                      )
    new_tree = cleaner.clean_html(source)
    html_text = lxml.html.tostring(new_tree).decode('utf-8')
    html_text = re.sub(" +", " ", html_text)
    html_text = re.sub("[\n ]*\n[\n ]*", "\n", html_text)
    return html_text

#print (clean_html("<html><script>foo</script><b>bar</b></html>"))
#exit()

class Record(object):
    def __init__(self, url):
        self.url = url
        self.response = requests.get(self.url)
        self.root = lxml.html.fromstring(self.response.content)
    
    def __repr__(self):
        return str(self.__dict__)
    
    def keys(self):
        return self.__dict__.keys()

def full_url(link):
    return urljoin(super_cluster_url, link)

def full_urls(_list):
    return [full_url(link) for link in _list]
    
def index_cluster(cluster_url):
    cluster = Record(cluster_url)
    cluster.title = cluster.root.xpath("//h1[@class='cluster__title']/span/text()")
    cluster.description = cluster.root.xpath("//div[@class='cluster__introduction']/p/text()")
    cluster.jobs = full_urls(cluster.root.xpath("//li[@class='career-glossary__title']/a/@href"))
    cluster.skills = cluster.root.xpath("//ul[@class='listing']//a/@href")
    return cluster

def index_job(job_url):
    # TODO -- get job name
    job = Record(job_url)
    job.title = job.root.xpath("//h1[@class='video__title']/text()")[0]
    assert isinstance(job.title, str)
    job.roles = full_urls(job.root.xpath("//div[@class='role-models-related listing-grid listing-container']//a/@href"))
    try:
        job.youtube = re.search("videoId: '([^']+)'", job.response.text).groups()[0]
    except AttributeError:
        job.youtube = None

    raw_accordion = job.root.xpath("//div[@class='career__accordion accordion-wrapper']")[0]  # TODO -- generate HTML 5 app
    
    # replace initial text of <div class="accordion__title">___ with <h3>___</h3>
    accordion_title_tags = raw_accordion.xpath(".//div[@class='accordion__title']")
    for tag in accordion_title_tags:
        h3 = lxml.html.Element("h3")
        h3.text = tag.text
        tag.text=""
        tag.insert(0, h3)
        
    # apparently this'll trash the original structure, but I'm not convinced that's true.
    
    job.html = clean_html(raw_accordion)
    
    io = BytesIO()
    with ZipFile(io, mode="w") as z:
        z.writestr("index.html", html_template.format(job.html))
        z.write("styles.css")
    job.app = io.getvalue()
    return job

def index_skill(skill_url):
    # TODO: add other bits, should we care about this.
    skill = Record(skill_url)
    try:
        skill.youtube = re.search("videoId: '([^']+)'", skill.response.text).groups()[0]
    except AttributeError:
        skill.youtube = None
    return skill    
    
def index_role(role_url):
    # Note, we'll need to do these from the jobs since there doesn't appear to be a master list
    role = Record(role_url)
    role.name = role.root.xpath("//div[@class='role-model__name']")[0].text.strip()
    role.title = role.root.xpath("//h1[@class='role-model__title']")[0].text.strip()
    assert isinstance(role.title, str)
    bio = role.root.xpath("//div[@class='role-model__body wysiwyg']/p")
    if bio:
        role.bio = bio[0].text_content()
    else:
        role.bio = ""
    
    # videos: delete later videos which have the same ID.
    videos = role.root.xpath("//li[@data-video-id]")
    raw_video_names = [video.xpath("./a/text()") for video in videos]
    raw_video_ids = [video.xpath("./@data-video-id") for video in videos]
    role.video_names = []
    role.video_ids = []
    used_ids = []
    for name, _id in zip(raw_video_names, raw_video_ids): 
        if _id not in used_ids:
            role.video_names.append(name)
            role.video_ids.append(_id)
            used_ids.append(_id)
    assert len(role.video_names) == len(role.video_ids)
           
    role.skill_links = [x.split("?")[0] for x in role.root.xpath("//div[@class='role-model__skills slider']//a/@href")]
    role.skill_names = list(map(str.strip, role.root.xpath("//div[@class='role-model__skills slider']//div[@class='listing__title']/text()")))
    assert len(role.skill_names)== len(role.skill_links)
    return role

def all_jobs():
    cluster = index_cluster("https://www.careergirls.org/explore-careers/careers/")
    for job_url in cluster.jobs:
        yield index_job(job_url)
    

if __name__ == "__main__":
    app = index_job("https://www.careergirls.org/career/architect/").app
    with open("app.zip", "wb") as f:
        f.write(app)
    
    response = requests.get(super_cluster_url)
    root = lxml.html.fromstring(response.content)
    hrefs = root.xpath("//a[./div[@class='cluster-listing__title']]/@href")
    hrefs = [full_url(url) for url in hrefs]
    
        
    print (index_role("https://www.careergirls.org/role-model/cultural-anthropologist/").keys())
    
    print(index_skill("https://www.careergirls.org/video/importance-of-math/"))
    
    #for cluster_url in hrefs:
    #    cluster = index_cluster(cluster_url)
    #    print (cluster.jobs)
