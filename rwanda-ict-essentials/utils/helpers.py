# Helpers useful parsing Rwanda ICT Essentials

def get_units_from_site(page):
    """ 
      Get all the unit names and links from the main page
    """
    units = []
    for div in page.find_all("div", class_= "coursename"):
        link = div.find("a", text = re.compile("Unit"))
        if link:
            units.append({ 'name': link.get_text(), 'link': link.get('href')})
    return units

def parse_unit(writer, name, link):
    """ 
      Parse the elements inside a unit
      Extract sections, and each section would be an independent HTML5App
    """
    content = read(link)
    page = BeautifulSoup(content, 'html.parser')
    PATH.open_folder(folder_name(name))

    sections = page.find_all('li', id = re.compile('section-')) 
    writer.add_folder(str(PATH), name, "", "TODO: Generate Description")
    for section in sections:
        title = generate_html5app_from_section(section)
        print_modules(section)
        writer.add_file(str(PATH), html5app_filename(title), html5app_path_from_title(title), license="TODO", copyright_holder = "TODO")
        os.remove(html5app_path_from_title(title))
    PATH.go_to_parent_folder()
    return 0

def generate_html5app_from_section(section):
    page_title = section.find("h3", class_="sectionname")
    title = "no title"
    if page_title:
        title = page_title.get_text()
    print("\t" + str(title) + " (" + section.get('id') + ")")
    html5app_filename = html5app_path_from_title(title)
    with HTMLWriter(html5app_filename) as html5zip:
        content = section.encode_contents
        html5zip.write_index_contents("<html><head></head><body>{}</body></html>".format(content))   
    return title 

def html5app_filename(title):
    return "{}.zip".format(slugify(title))

def html5app_path_from_title(title):
    return "./{}".format(html5app_filename)

def folder_name(unit_name):
    """ 
    Extract folder name from full unit name

    Example:
    Unit 01 - Example unit

    returns:
    Unit 01 
    """
    return re.search('(.+?) - .*', unit_name).group(1)

def print_modules(section):
    modules = section.find_all("li", id=re.compile('module-'))
    for module in modules:
        titles = module.find_all("img", class_=re.compile("atto_image_button_"))
        for t in titles:
            if is_valid_title(t):
                print("\t\t - " + str(real_title(t) + " " + clasify_module(module)))
                if real_title(t) == "Recommended Time":
                    print("********")
                    print("\t\t\t" + get_recommended_time(t))
                    print("********")
    if len(modules) == 0 :
        print("\t\t Unit Title - " + clasify_module(section))
    return 0 

def clasify_module(module):
    module_type = "( html )"
    video = module.find("iframe", src=re.compile("youtube"))
    if video:
        module_type = "\033[91m ( video ) \033[0m"
    return module_type

def real_title(title):
    filename = title.get("src").split("/")[-1]
    return IMG_LOOKUP[filename]

def get_recommended_time(title):
    if title.parent.get_text():
        return title.parent.get_text()
    else:
      return title.parent.parent.get_text() 

def is_valid_title(title):
    """
    is_valid_title is true if the name of the image contains Unit or Section on it 
    but not contains Quote 
    or Method1 or Method2 
    (because they are extra images on the section)
    """
    pattern1 = re.compile("Unit|Section", re.IGNORECASE)
    pattern2 = re.compile("^.*Quote.*$", re.IGNORECASE)
    pattern3 = re.compile("^.*Method[1|2].*$", re.IGNORECASE)
    filename = title.get("src").split("/")[-1]
    return (pattern1.match(filename) and (not pattern2.match(filename) and (not pattern3.match(filename))))

def download_video(url):
    ydl_options = {
            'outtmpl': '%(title)s-%(id)s.%(ext)s',
            'continuedl': True,
            # 'quiet' : True,
            'restrictfilenames':True, 
        }
    with youtube_dl.YoutubeDL(ydl_options) as ydl:
        try:
            ydl.add_default_info_extractors()
            info = ydl.extract_info(url, download=True)
            print(info['title'])
        except (youtube_dl.utils.DownloadError,youtube_dl.utils.ContentTooShortError,youtube_dl.utils.ExtractorError) as e:
            self.error_occured = True
            self.statusSignal.emit(str(e))
    return 0


