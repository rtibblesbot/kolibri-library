import csv
import requests
import re
import requests_cache
requests_cache.install_cache()
from headers import headers

def get_doc_urls(url):
    pass

def docs():
    with open('awa2el.csv', newline='') as csvfile:
        csviter = csv.reader(csvfile, delimiter=',', quotechar='"')
        header = True
        for top_URL, title, b1, b2, b3, b4, p1, p2, p3, p4 in csviter:
            if header:
                assert top_URL = "URL"
                header = False
                continue
            yield p1, p2, p3, p4
            
if __name__ == "__main__":
    print (len(list(videos())))
