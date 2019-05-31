import requests
import requests_cache
import lxml.html

requests_cache.install_cache()

base_url = "https://global-asp.github.io/storybooks-minnesota/stories/{}"

languages = {
    "en": "English",
    "am": "Amharic",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "zh": "Mandarin",
    "nb": "Norwegian",
    "om": "Oromo",
    "so": "Somali",
    "es": "Spanish",
}

for lang in languages:
    html = requests.get(base_url.format(lang)).content
    root = lxml.html.fromstring(html)
    urls = set(root.xpath("//a[@class='btn-link']/@href"))
    print (urls)

