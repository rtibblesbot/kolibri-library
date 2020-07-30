#!/usr/bin/env python
import csv
import os
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages
from le_utils.constants.languages import getlang
from le_utils.constants import licenses as le_licenses

# Run constants
################################################################################
CHANNEL_NAME = "TicTacLearn"                             # Name of Kolibri channel
CHANNEL_SOURCE_ID = "tictaclearn"                              # Unique ID for content source
CHANNEL_DOMAIN = "tictaclearn.com"                         # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1

# Additional constants
################################################################################
COLUMN_MAPPING = {
    'id': 'Id',
    'name': 'Name of the Content',
    'description': 'Description of the content in one line – telling about the content',
    'curriculum': 'Board',
    'class': 'Class',
    'lang': 'Medium',
    'subject': 'Subject',
    'topic': 'Topic',
    'copyright': 'Copyright',
    'icon': 'Icon',
    'url': 'File Path',
    'license': 'License'
}


def get_column(row, column_id, default=None):
    if column_id in row:
        return row[column_id].strip()
    elif column_id in COLUMN_MAPPING:
        column = COLUMN_MAPPING[column_id]
        if column in row:
            return row[column].strip()

    return default

# The chef subclass
################################################################################
class TicTacLearnChef(SushiChef):
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
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_TITLE': CHANNEL_NAME,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }
    ASSETS_DIR = os.path.abspath('assets')
    CSVS_DIR = os.path.join(ASSETS_DIR, 'csvs')
    DATA_DIR = os.path.abspath('chefdata')
    DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')
    ARCHIVE_DIR = os.path.join(DOWNLOADS_DIR, 'archive_{}'.format(CONTENT_ARCHIVE_VERSION))
    # Your chef subclass can override/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def build_tree_from_spreadsheet(self):
        """
        Tree structure:
        Language -> Class -> Subject -> Topic (optional) -> Name
        :return:
        """
        channel_tree = {}

        for row in self.math_items:
            lang = get_column(row, 'lang')
            assert lang
            if not lang in channel_tree:
                channel_tree[lang] = {}

            class_name = get_column(row, 'class')
            assert class_name
            if not class_name in channel_tree[lang]:
                channel_tree[lang][class_name] = {}

            subject = get_column(row, 'subject')
            assert subject
            if not subject in channel_tree[lang][class_name]:
                channel_tree[lang][class_name][subject] = {'topics': {}, 'items':[]}

            topic = get_column(row, "topic")
            if topic:
                raise NotImplementedError("No support yet for handling topics")
            else:
                channel_tree[lang][class_name][subject]["items"].append(row)

        return channel_tree

    def load_tree_data(self):
        math_csv = os.path.join(self.CSVS_DIR, 'TTL-45-English-Math.csv')

        self.math_items = []
        with open(math_csv, mode='r') as csv_file:
            rows = csv.DictReader(csv_file)
            counter = 0
            for row in rows:
                # ignore the labels row
                if counter > 0:
                    self.math_items.append(row)
                counter += 1

        self.channel_tree = self.build_tree_from_spreadsheet()

    def download_content(self):
        self.load_tree_data()
        assert self.channel_tree

        def get_filename(url):
            return url.split('/')[-1].split('?')[0]

        for lang in self.channel_tree:
            for class_name in self.channel_tree[lang]:
                for subject in self.channel_tree[lang][class_name]:
                    for item in self.channel_tree[lang][class_name][subject]['items']:
                        url = get_column(item, 'url')
                        url = url.replace('?dl=0', '?dl=1')
                        filename = get_filename(url)
                        if url:
                            download_path = os.path.join(self.ARCHIVE_DIR, lang, class_name, subject, filename)
                            os.makedirs(os.path.dirname(download_path), exist_ok=True)
                            if not os.path.exists(download_path):
                                content = downloader.read(url)
                                with open(download_path, 'wb') as f:
                                    f.write(content)
                            item['file'] = download_path

                        icon = get_column(item, 'icon')
                        icon = icon.replace('?dl=0', '?dl=1')
                        if icon:
                            icon_filename = get_filename(icon)
                            icon_path = os.path.join(self.ARCHIVE_DIR, lang, class_name, subject, icon_filename)
                            content = downloader.read(icon)
                            with open(icon_path, 'wb') as f:
                                f.write(content)
                            item['thumbnail'] = icon_path

    def add_content_to_tree(self, channel):
        tree = self.channel_tree
        lang = 'English'
        lang_obj = getlang("en")
        for class_name in tree[lang]:
            class_obj = tree[lang][class_name]
            class_id = "{}-{}".format(lang, class_name)
            class_node = nodes.TopicNode(source_id=class_name, title=class_name)
            for subject_name in class_obj:
                subject_id = "{}-{}".format(class_id, subject_name)
                subject_node = nodes.TopicNode(source_id=subject_id, title=subject_name)
                subject_obj = class_obj[subject_name]
                for item in subject_obj['items']:
                    item_id = "{}-{}".format(subject_id, get_column(item, 'id'))
                    video = nodes.VideoNode(
                        source_id=item_id,
                        title=get_column(item, 'name'),
                        description=get_column(item, 'description'),
                        files=[
                            files.VideoFile(path=get_column(item, 'file'))
                        ],
                        language=lang_obj,
                        # FIXME: Use the column's license field instead of hardcoding.
                        license=licenses.get_license(le_licenses.CC_BY, copyright_holder=get_column(item, "copyright")),
                        # thumbnail=get_column(item, "thumbnail")
                    )
                    subject_node.add_child(video)

                class_node.add_child(subject_node)


            channel.add_child(class_node)


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

        self.add_content_to_tree(channel)

        return channel


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = TicTacLearnChef()
    chef.main()