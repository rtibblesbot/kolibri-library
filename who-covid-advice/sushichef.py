#!/usr/bin/env python
import json
import os

from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages

from scrapers import who


# Run constants
################################################################################
CHANNEL_NAME = "WHO Covid Advice"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "who-covid-advice"                      # Unique ID for content source
CHANNEL_DOMAIN = "who.int"                                  # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################



# The chef subclass
################################################################################
class WhoCovidAdviceChef(SushiChef):
    """
    This class converts content from the content source into the format required by Kolibri,
    then uploads the {channel_name} channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://ricecooker.readthedocs.io
    """
    CONTENT_ARCHIVE_VERSION = 1
    DATA_DIR = os.path.abspath('chefdata')
    DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')

    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_TITLE': CHANNEL_NAME,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }

    # Since this is a multi-lingual site but pages can't be scraped in a consistent fashion, we use page IDs
    # so that we can logically refer to specific pages in the scraping code without relying on language specific
    # names, etc.
    page_data = {
        'covid_advice': {
            'url': 'https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public',
        },
        'face_masks': {
            'url': 'https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/when-and-how-to-use-masks'
        },
        'mythbusters': {
            'url': 'https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/myth-busters'
        },
        'videos': {
            'url': 'https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/videos'
        },
        'advocacy': {
            'url': 'https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/healthy-parenting'
        }
    }

    tree_structure = [
        {
            'covid_advice': [
                {
                    'face_masks': []
                },
                {
                    'mythbusters': []
                },
                {
                    'videos': []
                },
                {
                    'advocacy': []
                }
            ]
        }
    ]

    def download_content(self):
        self.CONTENT_DIR = os.path.join(self.DOWNLOADS_DIR, 'archive_{}'.format(self.CONTENT_ARCHIVE_VERSION))

        archive_data_filename = os.path.join(self.CONTENT_DIR, 'archive_data.json')
        if os.path.exists(archive_data_filename):
            archive_data = json.load(open(archive_data_filename))
            self.page_data = archive_data

        for page_id in self.page_data:
            url = self.page_data[page_id]['url']
            # don't re-download if we've already got a successful download.
            if not 'download_info' in self.page_data[page_id]:
                self.page_data[page_id]['download_info'] = downloader.archive_page(url, self.CONTENT_DIR)

        with open(archive_data_filename, 'w') as f:
            archive_data = json.dumps(self.page_data, indent=4)
            f.write(archive_data)

    def page_to_topic(self, page_id):
        """
        Because each page uses a different structure and format, we can't reuse a lot of the scraping logic.
        This function checks page_id and redirects to the appropriate scraping code for that page.
        :param page_id:
        :return:
        """

        scraper = who.WHOCovidAdvicePageScraper(self.page_data[page_id]['url'], self.page_data[page_id]['download_info']['index_path'])
        return scraper.get_ricecooker_node()

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        # FIXME: this should use the tree_structure instead, this is just for testing the conversion.
        for page_id in self.page_data:
            print("Converting page {} to topic".format(page_id))
            self.page_to_topic(page_id)

        return channel



# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = WhoCovidAdviceChef()
    chef.main()