import requests
from bs4 import BeautifulSoup
import os

session = requests.Session()

LOGIN_URL = "https://accounts.geogebra.org/user/signin"
GGB_URL = "https://www.geogebra.org/material/download/format/file/id/{file_id}"
ZIP_URL = "https://www.geogebra.org/material/download/format/package/id/{file_id}"
OVERVIEW_URL = "https://www.geogebra.org/m/{file_id}"

PASSWORD = os.environ['GEOGEBRA_PASSWORD']
USERNAME = os.environ['GEOGEBRA_USERNAME']
CACHE_DIR = 'cache_dir'

logged_in = False

def login():
    global logged_in
    response = session.get(LOGIN_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    inputs = (soup.find("form", {'id':'form_geogebra_login'}).find_all("input"))
    data = {}
    for i in inputs:
        data[i['name']] = i.get('value')
    data['username'] = USERNAME
    data['password'] = PASSWORD
    post_response = session.post(LOGIN_URL, data=data)
    assert "New Worksheet" in post_response.text
    # we are logged in
    logged_in = True
    print ("Logged in to geogebra")

def get_canonical_id(file_id):
    """for some reason, some have different download IDs than the main page. *sigh*"""
    response = session.get(OVERVIEW_URL.format(file_id=file_id))
    soup = BeautifulSoup(response.content, "html.parser")
    target_url =  (soup.find("a", {'class': 'j-about'}).attrs['href'])
    return target_url.split('/')[-1]

def get_ggb(file_id, save_target=None, cache_ok=True):
    return get_file(file_id, save_target, GGB_URL, cache_ok)

def get_zip(file_id, save_target=None, cache_ok=True):
    return get_file(file_id, save_target, ZIP_URL, cache_ok)

def get_file(file_id, save_target, url_template, cache_ok):
    if cache_ok and save_target==None:
        try:
            os.mkdir(CACHE_DIR)
        except FileExistsError: # TODO proper exception
            pass
        save_target = CACHE_DIR + '/' + file_id + "_" + url_template.split('/')[-3]
        try:
            with open(save_target, "rb") as f:
                print ("loading from cache {}".format(save_target))
                return f.read()
        except FileNotFoundError:
            print ("Not in cache")
            pass # not in cache, will be saved later.
    if not logged_in:
        login()

    canonical_file_id = get_canonical_id(file_id)
    response = session.get(url_template.format(file_id=canonical_file_id))
    response.raise_for_status()
    if save_target:
        with open(save_target, "wb") as f:
            f.write(response.content)
    return response.content

if __name__=="__main__":
    print (get_zip('dZT4v7KZ')[:5])
    print (get_canonical_id('Vxv48Gtz'))
