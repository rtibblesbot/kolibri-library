#!/usr/bin/env python

import json
import os
import sys
import tempfile
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from ricecooker.utils.downloader import download_static_assets
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages


# Run constants
################################################################################
CHANNEL_NAME = "Concord Consortium Science Simulations"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-concord-consortium"    # Channel's unique id
CHANNEL_DOMAIN = "learn.concord.org"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################



# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Concord Consortium Science Simulations channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }
    # Your chef subclass can ovverdie/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in during upload_channel (currently None)
          - kwargs: extra argumens and options not handled by `uploadchannel`.
            For example, add the command line option   lang="fr"  and the string
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        models = get_all_resources()['models']

        preview_urls = list(map(lambda x: x['preview_url'], models))
        resolved_urls = list(map(lambda x: requests.get(x).url, preview_urls))
        parsed_urls = list(map(lambda x: urlparse(x), resolved_urls))

        # Narrow down to just embeddable models for now
        embeddable_parsed_urls = list(filter(lambda x: x.path == '/embeddable.html', parsed_urls))
        embeddable_base_urls = list(map(lambda x: x.scheme + '://' + x.netloc, embeddable_parsed_urls))
        embeddable_fragments = list(map(lambda x: x.fragment, embeddable_parsed_urls))

        # Make parent directory ('temp') for all randomly-named temp dirs
        temp_dir = get_temp_dir()
        print(temp_dir)
        print(os.path.basename(temp_dir))

        # Download static assets for embeddable models into temp directory
        soups = [get_soup(e.geturl()) for e in embeddable_parsed_urls]
        for i, soup in enumerate(soups):
            temp_subdir = temp_dir + os.sep + str(i)
            os.makedirs(temp_subdir)

            print('\nDOWNLOADING STATIC ASSETS FOR SOUP', i)
            print('embeddable:', embeddable_parsed_urls[i].geturl())

            stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            doc = download_static_assets(soup, temp_subdir, embeddable_base_urls[i],
                    url_blacklist=['analytics.js']) #TODO add ga.js to blacklist
            sys.stdout.close()
            sys.stdout = stdout

            with open(temp_subdir + os.sep + 'embeddable.html', 'w') as f:
                fragment = embeddable_parsed_urls[i].fragment
                f.write(str(doc).replace('document.location.hash', "'#" + fragment + "'"))

            # Save model json responses
            embeddable_fragment = embeddable_fragments[i]
            fragment_file_dir = temp_subdir + os.sep + os.path.dirname(embeddable_fragment)
            fragment_filename = os.path.basename(embeddable_fragment)
            os.makedirs(fragment_file_dir)

            fragment_url = embeddable_base_urls[i] + os.sep + embeddable_fragment
            fragment_json = json.loads(requests.get(fragment_url).text)
            model_paths = []
            with open(fragment_file_dir + os.sep + fragment_filename, 'w') as f:
                f.write(json.dumps(fragment_json))
                if fragment_json.get('models'):
                    for model in fragment_json['models']:
                        if model.get('url'):
                            model_paths.append(model['url'])

            for j, model_path in enumerate(model_paths):
                model_url = embeddable_base_urls[i] + os.sep + model_paths[j]
                model_json = json.loads(requests.get(model_url).text)

                os.makedirs(temp_subdir + os.sep + os.path.dirname(model_path), exist_ok=True)
                with open(temp_subdir + os.sep + model_path, 'w') as g:
                    g.write(json.dumps(model_json))

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel


def get_temp_dir():
    os.makedirs('temp', exist_ok=True)
    temp_dir_prefix = os.getcwd() + os.sep + 'temp' + os.sep
    temp_dir = tempfile.mkdtemp(prefix=temp_dir_prefix)
    return temp_dir


def get_all_resources():
    api_search_url = 'https://learn.concord.org/api/v1/search/search?search_term=&sort_order=Newest&material_types%5B%5D=Investigation&material_types%5B%5D=Activity&material_types%5B%5D=Interactive&include_official=1&investigation_page=1&activity_page=1&interactive_page=1&per_page=1000'
    api_response = requests.get(api_search_url)
    all_resources = json.loads(api_response.text)

    all_resources_new_format = {
        'activities': [],
        'models': [],
        'sequences': []
    }

    for result in all_resources['results']:
        if result['type'] == 'interactives':
            all_resources_new_format['models'] = result['materials']
        if result['type'] == 'investigations':
            all_resources_new_format['sequences'] = result['materials']
        if result['type'] == 'activities':
            all_resources_new_format['activities'] = result['materials']

    return all_resources_new_format


def get_soup(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html5lib')
    return soup


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
