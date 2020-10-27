#!/usr/bin/env python
import os
import sys
from ricecooker.chefs import YouTubeSushiChef
from ricecooker.classes import licenses

from googleapiclient.discovery import build


# Run constants
################################################################################
CHANNEL_ID = "04deda9bf5b5489689191d4f2bcbaf74"             # UUID of channel
CHANNEL_NAME = "Chicken N Chips"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "chicken-n-chips"                              # Unique ID for content source
CHANNEL_DOMAIN = "youtube.com"                         # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = 'Chicken & Chips is a weekly pop culture magazine, that focuses on relationships and combines music, journalism, puppetry and animation to create the freshest blend of edutainment in Uganda. Airs every Sunday at 1:30pm on NTV Uganda'                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = os.path.join('files', 'logo.png')       # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1                                 # Increment this whenever you update downloaded content


# Additional constants
################################################################################
# Add GOOGLE API key here. Will need access to Youtube API v3
GOOGLE_API_KEY = None
CHICKEN_N_CHIPS_CHANNEL_ID = 'UCIGQCJIF4fdTrqxnvcwTYxg'


# The chef subclass
################################################################################
class ChickenNChipsChef(YouTubeSushiChef):
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
    channel_info = {
        'CHANNEL_ID': CHANNEL_ID,
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_TITLE': CHANNEL_NAME,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = ChickenNChipsChef()
    chef.main()
