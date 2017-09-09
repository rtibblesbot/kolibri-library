#!/usr/bin/env python

import json
import logging
import os

from le_utils.constants import content_kinds, licenses
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes
from ricecooker.classes import files
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ChannelNode
from ricecooker.config import LOGGER
from ricecooker.exceptions import UnknownFileTypeError, raise_for_invalid_channel



# Aflatoun settings
################################################################################
AFLATOUN_LICENSE = get_license(licenses.ALL_RIGHTS_RESERVED, copyright_holder='Aflatoun', description='Materials © 2015 Aflatoun')
AFLATOUN_AUTHOR = 'Aflatoun'
AFLATOUN_CONTENT_BASE_DIR = 'content/aflatoun_tree/aflatoun'
AFLATOUN_CONTENT_DIR_DEPTH = 4
LANGUAGE_FOLDER_LOOKUP = dict(
    en = 'English',
    fr = 'French',
)
CONTENT_FOLDERS_FOR_LANG = dict(
    en = ['Aflatoun Series',
          'Teacher Refresher Modules',
          'Training Manual'],
    fr = ['Les Séries Aflatoun',
          'Manuel de Formation',
          'Modules de support pour la formation continue'],
)
DIR_EXCLUDE_PATTERNS = ['Unzipped Files']
FILE_EXCLUDE_EXTENTIONS = ['.DS_Store', '.json']
FILE_SKIP_PATTENRS = ['exercise.zip']


# Chef settings
################################################################################
DATA_DIR = 'chefdata'
TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
RICECOOKER_JSON_TREE_TPL = 'ricecooker_json_tree_{}.json'


# LOGGING SETTINGS
################################################################################
logging.getLogger("cachecontrol.controller").setLevel(logging.WARNING)
logging.getLogger("requests.packages").setLevel(logging.WARNING)
LOGGER.setLevel(logging.DEBUG)



# HELPER FUNCTIONS
################################################################################

def get_metadata_file_path(path):
    if path.endswith('exercise.zip'):
        return path.repalce('exercise.zip', 'exercise.json')
    else:
        return path + '.json'

def get_metadata(path):
    """
    Find the json metadata file associated with content at `path` (dir or file).
    """
    metadata_filename = get_metadata_file_path(path)
    if not os.path.exists(metadata_filename):
        return {}
    with open(metadata_filename, 'r') as json_file:
        return json.load(json_file)

def get_path_as_list(path):
    """
    Convert raw_path form os.walk tuple format to a list of subdirectories.
    Returns a list of dirs after the first AFLATOUN_CONTENT_DIR_DEPTH dirs, e.g.,
    >>> get_path_as_list('content/aflatoun_tree/aflatoun/French/Topic1/Subtopic2/SubSubtopic3')
    ['Topic1', 'Subtopic2', 'SubSubtopic3']
    """
    full_path = path.split(os.path.sep)
    path_without_channel = full_path[AFLATOUN_CONTENT_DIR_DEPTH:]
    return path_without_channel

def get_node_for_path(channel, path_as_list):
    """
    Returns the TopicNode dict at the given path inside channel.
    """
    current = channel
    for subtopic in path_as_list:
        current = list(filter(lambda d: d['dirname'] == subtopic, current['children']))[0]
    return current

def source_id_from_path(path):
    return path.replace('content/aflatoun_tree/aflatoun/', 'aflotoun:', 1)




# BUILD JSON TREE
################################################################################

def filter_filenames(filenames):
    filenames_cleaned = []
    for filename in filenames:
        keep = True
        for pattern in FILE_EXCLUDE_EXTENTIONS:
            if filename.endswith(pattern):
                keep = False
        for pattern in FILE_SKIP_PATTENRS:   # This will reject exercises...
            if pattern in filename:
                keep = False
        if keep:
            filenames_cleaned.append(filename)
    return filenames_cleaned

def process_folder(channel, raw_path, subfolders, filenames, lang):
    """
    Create `ContentNode`s from each file in this folder and the node to `channel`
    under the path `raw_path`.
    """
    path_as_list = get_path_as_list(raw_path)

    # A. TOPIC
    dirname = path_as_list.pop()
    parent_node = get_node_for_path(channel, path_as_list)

    # read topic metadata to get title and description
    folder_metadata = get_metadata(raw_path)

    # create topic
    topic = dict(
        kind='TopicNode',
        dirname=dirname,
        source_id=source_id_from_path(raw_path),
        title=folder_metadata.get('title', dirname),
        description=folder_metadata.get('Description', None),
        language=lang,
        children=[],
    )
    # topic.update(folder_metadata)
    parent_node['children'].append(topic)

    # filter filenames
    filenames_cleaned = filter_filenames(filenames)

    # B. PROCESS FILES
    for filename in filenames_cleaned:
        file_metadata = get_metadata(os.path.join(raw_path, filename))
        node = make_content_node(raw_path, filename, file_metadata, lang)
        # attach content node to containing topic
        topic['children'].append(node)


def filter_subfolders(subfolders):
    subfolders_cleaned = []
    for subfolder in subfolders:
        keep = True
        for pattern in DIR_EXCLUDE_PATTERNS:
            if pattern in subfolder:
                keep = False
        if keep:
            subfolders_cleaned.append(subfolder)
    return subfolders_cleaned

def build_ricecooker_json_tree(args, options):
    """
    Download all categories, subpages, modules, and resources from open.edu.
    """
    LOGGER.info('Starting to build the ricecooker_json_tree')
    lang = options['lang']
    lang_dir = LANGUAGE_FOLDER_LOOKUP[lang]

    # Ricecooker tree
    ricecooker_json_tree = dict(
        kind='ChannelNode',
        title='NOT USED',
        language='NOT USED',
        children=[],
    )
    channel_base_dir = os.path.join(AFLATOUN_CONTENT_BASE_DIR, lang_dir)
    content_folders = list(os.walk(channel_base_dir))

    # MAIN PROCESSING OF os.walk OUTPUT
    ############################################################################
    _ = content_folders.pop(0)  # Skip over channel folder because handled above
    for raw_path, subfolders, filenames in content_folders:
        subfolders_cleaned = filter_subfolders(subfolders)
        LOGGER.info('processing folder ' + str(raw_path))
        process_folder(ricecooker_json_tree, raw_path, subfolders_cleaned, filenames, lang)

    # Write out ricecooker_json_tree.json
    json_file_name = os.path.join(TREES_DATA_DIR, RICECOOKER_JSON_TREE_TPL.format(lang))
    with open(json_file_name, 'w') as json_file:
        json.dump(ricecooker_json_tree, json_file, indent=2)
        LOGGER.info('Folder hierarchy walk result stored in ' + json_file_name)


def make_content_node(raw_path, filename, metadata, lang):
    """
    Create ContentNode based on the file extention and metadata provided.
    """
    file_key, file_ext = os.path.splitext(filename)
    ext = file_ext[1:]

    kind = None
    if ext in content_kinds.MAPPING:
        kind = content_kinds.MAPPING[ext]
    else:
        raise ValueError('Could not find kind for extension ' + str(ext) + ' in content_kinds.MAPPING')

    filepath = os.path.abspath(os.path.join(raw_path, filename))
    source_id = source_id_from_path(os.path.join(raw_path, filename))
    title = metadata.get('title', filename)
    description = metadata.get('Description', None)
    # tags = keywords_to_tags(metadata['keywords'])   # TODO
    # related_content = TODO

    if kind == content_kinds.VIDEO:
        content_node = dict(
            kind='VideoNode',
            source_id=source_id,
            title=title,
            author=AFLATOUN_AUTHOR,
            description=description,
            language=lang,
            derive_thumbnail=True,  # video-specific option
            files=[{'file_type':'VideoFile', 'path':filepath, 'language':lang}], # ffmpeg_settings={"crf": 24},
        )

    elif kind == content_kinds.AUDIO:
        content_node = dict(
            kind='AudioNode',
            source_id=source_id,
            title=title,
            author=AFLATOUN_AUTHOR,
            description=description,
            language=lang,
            files=[{'file_type':'AudioFile', 'path':filepath, 'language':lang}],
        )

    elif kind == content_kinds.DOCUMENT:
        content_node = dict(
            kind='DocumentNode',
            source_id=source_id,
            title=title,
            author=AFLATOUN_AUTHOR,
            description=description,
            language=lang,
            files=[{'file_type':'DocumentFile', 'path':filepath, 'language':lang}],
        )

    else:
        raise ValueError('Not implemented case for kind ' + str(kind))

    return content_node






# CONSTRUCT CHANNEL FROM RICECOOKER JSON TREE
################################################################################
# Note: the functions below are used in several chefs so might become part of `ricecooker`

def build_tree(parent_node, sourcetree):
    """
    Parse nodes given in `sourcetree` list and add as children of `parent_node`.
    """
    EXPECTED_NODE_TYPES = ['TopicNode', 'AudioNode', 'DocumentNode', 'VideoNode', 'HTML5AppNode']

    for source_node in sourcetree:
        kind = source_node['kind']
        if kind not in EXPECTED_NODE_TYPES:
            LOGGER.critical('Unexpected Node type found: ' + kind)
            raise NotImplementedError('Unexpected Node type found in channel json.')

        if kind == 'TopicNode':
            child_node = nodes.TopicNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                author=source_node.get("author"),
                description=source_node.get("description"),
                thumbnail=source_node.get("thumbnail"),
            )
            parent_node.add_child(child_node)
            source_tree_children = source_node.get("children", [])
            build_tree(child_node, source_tree_children)

        elif kind == 'AudioNode':
            child_node = nodes.AudioNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=AFLATOUN_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                thumbnail=source_node.get('thumbnail'),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        elif kind == 'VideoNode':
            child_node = nodes.VideoNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=AFLATOUN_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                derive_thumbnail=True,                   # video-specific option
                thumbnail=source_node.get('thumbnail'),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        elif kind == 'DocumentNode':
            child_node = nodes.DocumentNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=AFLATOUN_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                thumbnail=source_node.get("thumbnail"),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        elif kind == 'HTML5AppNode':
            child_node = nodes.HTML5AppNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=AFLATOUN_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                thumbnail=source_node.get("thumbnail"),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        else:
            LOGGER.critical("Encountered an unknown kind: " + str(source_node))
            continue

    return parent_node


def add_files(node, file_list):
    EXPECTED_FILE_TYPES = ['AudioFile', 'VideoFile', 'ThumbnailFile', 'HTMLZipFile', 'DocumentFile']
    for f in file_list:
        file_type = f.get('file_type')
        if file_type not in EXPECTED_FILE_TYPES:
            LOGGER.critical(file_type)
            raise NotImplementedError('Unexpected File type found in channel json.')
        path = f.get('path')  # usually a URL, not a local path
        # handle different types of files
        if file_type == 'AudioFile':
            node.add_file(files.AudioFile(
                path=f['path'],
                language=f.get('language'))
            )
        elif file_type == 'VideoFile':
            node.add_file(files.VideoFile(
                path=f['path'],
                language=f.get('language'),
                ffmpeg_settings=f.get('ffmpeg_settings'))
            )
        elif file_type == 'ThumbnailFile':
            node.add_file(files.ThumbnailFile(
                path=path)
            )
        elif file_type == 'HTMLZipFile':
            node.add_file(files.HTMLZipFile(
                path=path,
                language=f.get('language'))
            )
        elif file_type == 'DocumentFile':
            node.add_file(files.DocumentFile(
                path=path,
                language=f.get('language'))
            )
        else:
            raise UnknownFileTypeError("Unrecognized file type '{0}'".format(f['path']))



# CHEF
################################################################################

class AflatounChef(SushiChef):
    """
    This sushi chef uses os.walk to import the content in `afaltoun_tree` folder:
      - (directory structure + json metadata files) --> `TopicNode`s
      - (files + json metadata files) --> `ContentNode`s and `File`s
    """

    def get_channel(self, **kwargs):
        """
        Returns a ChannelNode that contains all required channel metadata.
        """
        if 'lang' not in kwargs:
            raise ValueError('Must specify lang=?? on the command line. Supported languages are `en` and `fr`')
        lang = kwargs['lang']
        channel = ChannelNode(
            source_domain = 'aflatoun.org',
            source_id = 'aflatoun-{}'.format(lang),
            title = 'Aflatoun Academy ({})'.format(lang.upper()),
            thumbnail = './content/images/aflatoun_logo.jpg',
            description = 'Aflatoun International offers social and financial'
                          ' education to millions of children and young people'
                          ' worldwide, empowering them to make a positive change'
                          ' for a more equitable world.',
            language = lang,
        )
        return channel

    def pre_run(self, args, options):
        """
        This function is called before `run` in order to build the json tree.
        """
        build_ricecooker_json_tree(args, options)

    def construct_channel(self, **kwargs):
        """
        Build the channel tree by adding TopicNodes and ContentNode children.
        """
        if 'lang' not in kwargs:
            raise ValueError('Must specify lang=?? on the command line. Supported languages are `en` and `fr`')
        lang = kwargs['lang']

        channel = self.get_channel(**kwargs)

        # Load ricecooker json tree data for language `lang`
        with open(os.path.join(TREES_DATA_DIR, RICECOOKER_JSON_TREE_TPL.format(lang))) as infile:
            json_tree = json.load(infile)
            if json_tree is None:
                raise ValueError('Could not find ricecooker json tree')
            build_tree(channel, json_tree['children'])

        raise_for_invalid_channel(channel)
        return channel


# CLI
################################################################################

if __name__ == '__main__':
    chef = AflatounChef()
    chef.main()
