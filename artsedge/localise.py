import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib

DOMAIN = "artsedge.kennedy-center.org"
LINK_ATTRIBUTES = ["src", "href"]
DOWNLOAD_FOLDER = "downloads"
sample_url = "https://artsedge.kennedy-center.org/educators/lessons/grade-9-12/Arthur_Miller_and_The_Crucible"

response = requests.get(sample_url)
soup = BeautifulSoup(response.content, "html5lib")

def guess_extension(filename):
    if "." not in filename[-8:]: # arbitarily chosen
        return ""
    else:
        return "." + filename.split(".")[-1]

def get_resources(soup):
    def is_valid_tag(tag):
        if not any(link in tag.attrs for link in LINK_ATTRIBUTES):
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



def make_local(soup, page_url):
     
    resources = get_resources(soup)

    #try:
    #    os.mkdir(DOWNLOAD_FOLDER)
    #except FileExistsError:
    #   pass
    
    
    # note: ensure order of raw_url_list remains the same as other url_lists we later generate.
    # (hopefully there's not two different looking but identical urls -- will lead to duplication)
    raw_url_list = [resource.attrs.get('href') or resource.attrs.get('src') for resource in resources]
    
    full_url_list = [urljoin(page_url, resource_url) for resource_url in raw_url_list]
    hashed_file_list = [hashlib.sha1(resource_url.encode('utf-8')).hexdigest() + guess_extension(resource_url) \
                            for resource_url in full_url_list]
    replacement_list = dict(zip(raw_url_list, hashed_file_list))
    
    # remove items from list if they're non-local links and replace with text explanation.
    
    
    # replace URLs
    for resource in resources:
        for attribute in LINK_ATTRIBUTES:
            attribute_value = resource.attrs.get(attribute)
            if attribute_value in replacement_list.keys():
                if resource.name == "a" and urlparse(attribute_value).netloc not in (DOMAIN, "", "www.kennedy-center.org"):
                    print (urlparse(attribute_value).netloc)
                    print ("rewriting non-local URL {} in {}".format(attribute_value, resource.name))
                    new_tag = soup.new_tag("span")
                    u = soup.new_tag("u")
                    u.insert(0, resource.text)
                    new_tag.insert(0, " (url:\xa0{})".format(resource.attrs['href']))
                    new_tag.insert(0, u)
                    
                    #original_tag.append(new_tag)
                    #tag = Tag(soup, "newTag", [("id", 1)])
                    #tag.insert(0, "Hooray!")
                    resource.replaceWith(new_tag)  # TODO -- this might  mess up the iteration?

                else:
                    resource.attrs[attribute] = replacement_list[attribute_value]

    return soup

    # download content
    for url, filename in zip(full_url_list, hashed_file_list):
        with open(DOWNLOAD_FOLDER+"/"+filename, "wb") as f:
            f.write(session.get(url, verify=False).content)

    with codecs.open(DOWNLOAD_FOLDER+"/index.html", "w", "utf-8") as f:
        f.write(str(soup))
        
    # create zip file
    return shutil.make_archive("__"+DOWNLOAD_FOLDER, "zip", # automatically adds .zip extension!
                        DOWNLOAD_FOLDER)    


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
    f.write(nice_html(make_local(soup, sample_url)))
