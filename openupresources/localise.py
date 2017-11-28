import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import os
import codecs
from io import BytesIO
from zipfile import ZipFile
import geogebra
import re
session = requests.Session()

DOWNLOAD_FOLDER = "foo"
LINK_ATTRIBUTES = ['href', 'src']
IGNORE_COMBOS = [['a', 'href']]

# TODO: handle bad [Are you ready for more?] section icon

def create_folder_name(url):
    return (urlparse(url).path.strip('/').replace("/", "_").replace(".html", ""))
  
def get_resources(soup):
    def is_valid_tag(tag):
        if not any(link in tag.attrs for link in LINK_ATTRIBUTES):
            return False
        # ig
        for combo in IGNORE_COMBOS:
            if tag.name==combo[0] and combo[1] in tag.attrs:
                return False
        # do not rewrite self-links
        href = tag.attrs.get("href")
        if href and href[0]== "#":
            return False
        return True
            
    resources = set()
    for attribute in LINK_ATTRIBUTES:
        l = soup.find_all(lambda tag: is_valid_tag(tag))
        resources.update(l)
    return resources

def handle_geogebra_tag(geo_tag):
    """Given a tag in the webpage, download the relevant standalone geogebra app,
    modify that app's html page to remove headers etc and insert it into an iframe.
    Used by make_local"""
    geo_id = geo_tag.attrs['data-ggb_id']
    print ("downloading {}".format(geo_id))
    data = geogebra.get_zip(geo_id)
    print ("handling {}".format(geo_id))
    geo_zip = BytesIO(data)
    with ZipFile(geo_zip) as zip_file:
        # extract all files
        zip_file.extractall(DOWNLOAD_FOLDER+'/geogebra')
        # re-write html file...
        html_filename, = [filename for filename in zip_file.namelist() if '/' not in filename and filename.endswith('.html')]
        zip_soup = BeautifulSoup(zip_file.read(html_filename), 'html.parser')
    all_tags = zip_soup.find("body").find_all()
    wanted_tags =  zip_soup.find("body").find_all(lambda tag: tag.name == "script" or ('class' in tag.attrs and 'applet_container' in tag.attrs.get('class')))
    
    for tag in all_tags:   # ditch everything in the body, including the script and applet tags, to allow nice flat HTML structure
        tag.extract()
    
    for tag in wanted_tags:  # reinstate bits we want
        zip_soup.find("body").append(tag)
        
    # put html file back into directory
    revised_html = str(zip_soup)
    with open(DOWNLOAD_FOLDER+"/geogebra/_"+html_filename, "wb") as f:
        f.write(revised_html.encode('utf-8'))
    
        
    # one of these script tags has the height and width we want:
    # "width":"580","height":"630"
    
    width = None
    height = None
    for tag in wanted_tags:
        if '"width"' in tag.text:
            assert width==None
            width = re.search('"width":"(\d*)"', tag.text).groups()[0]
            height = re.search('"height":"(\d*)"', tag.text).groups()[0]
        
    # create iframe loading this page
    # TODO: remove old tag
    geo_tag.name = "iframe"
    geo_tag.attrs['src'] = 'geogebra/{filename}'.format(filename="_"+html_filename)
    geo_tag.attrs['width'] = width
    geo_tag.attrs['height'] = height
    geo_tag.attrs['scrolling'] = 'no'
    print ("handled {}".format(geo_id))        

def make_local(page_url):
    
    # TODO 404 handling etc.
    try:
        os.mkdir(DOWNLOAD_FOLDER)
    except FileExistsError:
        pass
    
    html_response = session.get(page_url)
    
    soup = BeautifulSoup(html_response.content, 'html.parser')
    resources = get_resources(soup)
    # replace mathjax
    # TODO: actually install it
    mathjax, = [resource for resource in resources if 'src' in resource.attrs and "MathJax.js" in resource.attrs.get('src')]
    resources.remove(mathjax)
    mathjax.attrs['src'] = 'mathjax/MathJax.js'
    
    # replace geogebra
    """<div class="geogebra-embed-wrapper" data-ggb_id="Vxv48Gtz">...</div>"""
    geos = soup.find_all("div", {'class': 'geogebra-embed-wrapper'})
    for geo in geos:
        handle_geogebra_tag(geo)
        
    # remove headers, footers
    tags = soup.find_all(lambda tag: tag.name in ["header", "footer"])
    for tag in tags:
        if 'global-footer' in tag.attrs['class'] or \
           'lesson-footer' in tag.attrs['class'] or \
           'math-header'   in tag.attrs['class'] or \
           'global-header' in tag.attrs['class']:
            tag.extract()  # delete it
        
    # note: ensure order of raw_url_list remains the same as other url_lists we later generate.
    # (hopefully there's not two different looking but identical urls -- will lead to duplication)
    raw_url_list = [resource.attrs.get('href') or resource.attrs.get('src') for resource in resources]
    full_url_list = [urljoin(page_url, resource_url) for resource_url in raw_url_list]
    # TODO: add extensions to filenames
    hashed_file_list = [hashlib.sha1(resource_url.encode('utf-8')).hexdigest() for resource_url in full_url_list]
    replacement_list = dict(zip(raw_url_list, hashed_file_list))
    for resource in resources:
        for attribute in LINK_ATTRIBUTES:
            attribute_value = resource.attrs.get(attribute)
            if attribute_value in replacement_list.keys():
                resource.attrs[attribute] = replacement_list[attribute_value]
    
    for url, filename in zip(full_url_list, hashed_file_list):
        #print (url)
        with open(DOWNLOAD_FOLDER+"/"+filename, "wb") as f:
            f.write(session.get(url, verify=False).content)
            
    with codecs.open(DOWNLOAD_FOLDER+"/index.html", "w", "utf-8") as f:
        f.write(str(soup))
    
grades = [6,7,8]
units = [1,2,3,4,5,6,7,8]
subunits = [1,2,3,4,5,6]

# 7 5 3
placeholder_url = "https://im.openupresources.org/{}/students/{}/{}.html"
for grade in grades:
    for unit in units:
        for subunit in subunits:
            target_url = placeholder_url.format(grade, unit, subunit)
            DOWNLOAD_FOLDER = create_folder_name(target_url)
            try:
                make_local(target_url)
            except Exception as e:
                print ("*** FAILURE ON {}, {}".format(target_url, str(e)))
                with open("fail.log", "a") as f:
                    f.write("{}:{}".format(target_url, str(e)))
                
print("END") 

