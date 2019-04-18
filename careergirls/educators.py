import requests
import re
import lxml.html
import cg_index
from urllib.parse  import urljoin
urls = {
"/educators-parents-mentors/teachers/": "Teachers",
"/educators-parents-mentors/school-counselors/": "School Counselors",
"/educators-parents-mentors/librarians/": "Librarians",
"/educators-parents-mentors/group-leaders/": "Group Leaders",
"/educators-parents-mentors/mentors/": "Mentors",
"/educators-parents-mentors/parents/": "Parents"
}

top_url = "https://www.careergirls.org/educators-parents-mentors/"


# get resources
resources = []
resource_data = {"Empowerment Lessons": 38,
             "Inspirational Freebies": 34,
             "Printable Activities": 36,
             "Ready-to-Use Scripts": 33,
             "Toolkits and Guides": 37}

for resource_title, resource_id in resource_data.items():
    r = requests.get("https://www.careergirls.org/educators-parents-mentors/?filter_educator={}".format(resource_id)).content
    root = lxml.html.fromstring(r)
    resource_urls =  [urljoin(top_url, x) for x in root.xpath("//h2[@class='resource-listing__title']/a/@href")]
    resource_titles =  [x.text_content().strip() for x in root.xpath("//h2[@class='resource-listing__title']/a")]
    resources.append([resource_title, zip(resource_titles, resource_urls)])

for url in urls: 
