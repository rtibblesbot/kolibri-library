from bs4 import BeautifulSoup, NavigableString
from bs4.element import Tag
from urllib.parse import urlsplit
from itertools import zip_longest
from localise import requests
import hashlib
import shutil
import os
import add_file

DOWNLOAD_FOLDER = "carousel_downloads"

filenames = """
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/youre-invited-to-a-ceili-exploring-irish-dance.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_dance.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_dance.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish-dancers.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish-shoes.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_2.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_3.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_4.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/stolen-child.ashx
""".strip().split("\n")

filenames = [x.strip() for x in filenames]
captions = filenames

            #if not urlparse(url).netloc:
                #url = urljoin(url, urlparse(base_url).netloc)
            #if not urlparse(url).scheme:
                #url = urljoin(url, urlparse(base_url).scheme)


def get_url(url, filename):
    r = requests.get(url, verify=False)
    content = r.content
    #try:
        #content_type = r.headers['Content-Type'].split(";")[0].strip()
    #except KeyError:
        #content_type = ""
    #extension = ext_from_mime_type(content_type)
    #filename = hashed_url(attribute_value)+extension
    
    with open(filename, "wb") as f:
        try:
            f.write(content)
        except requests.exceptions.InvalidURL:
            pass    
    
def create_carousel_zip(filenames, captions=[]):
    # download files and get disk filenames
    
    def hash_url(url):  
        return hashlib.sha1((url).encode('utf-8')).hexdigest() + ".jpg"
    
    hashed_filenames = [hash_url(filename) for filename in filenames]
    hashed_pathnames = [DOWNLOAD_FOLDER + "/" + x for x in hashed_filenames]

    # copy over js/css
    # has to go first because it needs DOWNLOAD_FOLDER to not exist
    assert "downloads" in DOWNLOAD_FOLDER
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except: # ignore if not present
        pass 
    
    
    shutil.copytree("html", DOWNLOAD_FOLDER)
    
    # shouldn't be necessary any more
    #try:
    #    os.mkdir(DOWNLOAD_FOLDER)
    #except FileExistsError:
    #    pass
    
    # create html/index.html
    create_carousel(hashed_filenames, captions)
    
    for url, path in zip(filenames, hashed_pathnames):
        get_url(url, path) # TODO - write function
    
    #shutil.copy("html", DOWNLOAD_FOLDER)
    
    # create zip file
    ziphash = hash_url(str(filenames))
    zipfile_name = shutil.make_archive("__"+DOWNLOAD_FOLDER+"/"+ziphash, "zip", # automatically adds .zip extension!
                        DOWNLOAD_FOLDER)

    # delete contents of downloadfolder
    assert "downloads" in DOWNLOAD_FOLDER
    shutil.rmtree(DOWNLOAD_FOLDER)

    return zipfile_name    

def create_carousel_soup(filenames, captions=[]):
    """Take a list of filenames and create a HTML5App.
       It is not the job of this function to convert URLs to filenames!"""

    with open("play_template.html", "rb") as f:
        html_bytes = f.read()

    if captions:
        assert len(captions) == len(filenames), "Mismatch between filenames and captions length"

    combined_data = list(zip_longest(reversed(filenames), reversed(captions)))
    soup = BeautifulSoup(html_bytes, "html5lib")
    # note: this just uses the order in the HTML document -- not very stable
    small_slick_replace, large_slick_replace = soup.findAll("divreplace")

    def add_image(parent_tag, imgsrc, caption=None, thumbnail=False):
        div_tag = soup.new_tag("div")
        img_tag = soup.new_tag("img")
        img_tag.attrs['src'] = imgsrc
        if thumbnail:
            img_tag.attrs['width'] = 100
            img_tag.attrs['height'] = 100
        div_tag.insert(0, img_tag)
        if not thumbnail and caption:
            div_tag.insert(0, NavigableString(caption))
            img_tag.attrs['alt'] = caption
        parent_tag.insert(0, div_tag)

    large_slick = soup.new_tag("placeholder")
    small_slick = soup.new_tag("placeholder")

    fake_images = 6-len(filenames)
    if fake_images == 5: fake_images = 0  # ignore single image case
    for i in range(fake_images):
        add_image(large_slick, "")
        add_image(small_slick, "")


    # this could probably be tidied to remove the <placeholder> tag.
    for filename, caption in combined_data:
        add_image(large_slick, filename, caption)

    for filename, caption in combined_data:
        add_image(small_slick, filename, caption, thumbnail=True)

    large_slick_replace.replace_with(large_slick)
    small_slick_replace.replace_with(small_slick)
    large_slick.replaceWithChildren()
    small_slick.replaceWithChildren()

    return soup

def create_carousel(filenames, captions=[]):
    soup = create_carousel_soup(filenames, captions)
    with open(DOWNLOAD_FOLDER+"/index.html", "w") as f:
        f.write(soup.prettify())

def create_carousel_node(filenames, captions=[], **metadata):
    zip_filename = create_carousel_zip(filenames, captions)
    print(zip_filename)
    return add_file.create_node(add_file.HTMLZipFile, filename=zip_filename, **metadata)


if __name__ == "main":
    create_carousel_zip(filenames, captions)
    #create_carousel(filenames, captions)
