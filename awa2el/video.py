import csv
import requests

def get_video(url):
    r = requests.get(url)


with open('nashmi.csv', newline='') as csvfile:
    csviter = csv.reader(csvfile, delimiter=',', quotechar='"')
    for top_URL, topname, middle, lower, url in csviter:
        get_video(url)
