#!/usr/bin/env python
import os
import sys
from ricecooker.utils import html_writer, zip
from ricecooker.utils.downloader import archive_page, read
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages

from utils import *
import requests
from bs4 import BeautifulSoup

import uuid
import glob
import shutil


# Run constants
################################################################################
CHANNEL_ID = "7f07b95a5f3f4440b05181105f8401fc"             # UUID of channel
CHANNEL_NAME = "Sesamath"                                   # Name of Kolibri channel
CHANNEL_SOURCE_ID = "sesamath"                              # Unique ID for content source
CHANNEL_DOMAIN = "https://mathenpoche.sesamath.net/"        # Who is providing the content
CHANNEL_LANGUAGE = "fr"                                     # Language of channel
CHANNEL_DESCRIPTION = 'Avec ce site, Sésamath a pour ambition de proposer aux familles un maximum de ressources de tout type : cours, exercices, aides animées, QCM et devoirs pour s’entraîner mais aussi de l’entraînement au calcul mental, des jeux logiques'                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = SESAMATH_THUMBNAIL_PATH                                    # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1   


# Additional constants
################################################################################



# The chef subclass
################################################################################
class SesamathChef(SushiChef):
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
    DATA_DIR = os.path.abspath('chefdata')
    DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')
    ARCHIVE_DIR = os.path.join(DOWNLOADS_DIR, 'archive_{}'.format(CONTENT_ARCHIVE_VERSION))

    # Your chef subclass can override/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments
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
        count = 0
        for url in GRADE_MAP:
          response = requests.get(url, timeout=10)
          sesamath_response = BeautifulSoup(response.content, 'html.parser')

          # Grade Node Name:
          grade = sesamath_response.find('h1', {'class': 'logo'}).get_text(strip=True)

          # Create topic Node
          grade_source_id = 'Sesamath-{0}'.format(grade)
          grade_node = nodes.TopicNode(
            title = grade,
            source_id = grade_source_id,
            author = 'Sesamath',
            provider = 'Sesamath',
            # TODO check to see if ok to leave blank
            description = '',               
            language = 'fr'
          )
          # Get Topics
          visible_N2 = sesamath_response.find_all('li', {'class': 'n2' } )
          for element_in_visible_N2 in visible_N2:
            topic_name = element_in_visible_N2.find('h2').get_text(strip=True)

            visible_N3 = element_in_visible_N2.find_all('li', {'class': 'n3'})
            
            topic_source_id = 'Sesamath-{0}-{1}'.format(grade, topic_name)
            topic_node = nodes.TopicNode(
              title = topic_name,
              source_id = topic_source_id,
              author = 'Sesamath',
              provider = 'Sesamath',
              description = '',
              language = 'fr'
            )

            grade_node.add_child(topic_node)

            for element_in_visible_N3 in visible_N3:
              sub_topic_name = element_in_visible_N3.find('a').get_text(strip=True)

              # Add subjects to sub_topics
              sub_topic_source_id = 'Sesamath-{0}-{1}-{2}'.format(grade, topic_name, sub_topic_name)
              sub_topic = nodes.TopicNode(
                title = sub_topic_name,
                source_id = sub_topic_source_id,
                author = 'Sesamath',
                provider = 'Sesamath',
                description = '',
                language = 'fr'
              )

              topic_node.add_child(sub_topic)

              # Get Subject Nodes
              visible_N4 = element_in_visible_N3.find_all('li', {'class': 'n4'})
              for element_in_visible_N4 in visible_N4:
                subject = element_in_visible_N4.find('a')
                subject_name = subject.get_text(strip=True)
                subject_href = subject['href']

                subject_source_id = 'Sesamath-{0}-{1}-{2}-{3}'.format(grade, topic_name, sub_topic_name, subject_name)
                subject_node = nodes.TopicNode(
                  title = subject_name,
                  source_id = subject_source_id,
                  author = 'Sesamath',
                  provider = 'Sesamath',
                  description = '',
                  language= 'fr'
                )

                sub_topic.add_child(subject_node)

                # Get Exercises in Subjects
                
                link_to_exercise_page = url + subject_href

                subject_node_arr = add_exercises(link_to_exercise_page, url, grade)
                for node in subject_node_arr:
                  subject_node.add_child(node)

          # Add to channel here
          channel.add_child(grade_node)

        return channel

# Get all exercises from url and add them to subject node
def add_exercises(url, base_url, grade):
  print(url)
  try:
    content = read(url, loadjs = True)
  except:
    print('Timeout error')
    return []

  nodes_arr = []
  page_soup = BeautifulSoup(content[0], 'html.parser')
  # Get all ress_ato and ress_j3p exercises
  visible_ress_ato = page_soup.find_all('a', {'class': 'ress_ato'})
  visible_ress_j3p = page_soup.find_all('a', {'class': 'ress_j3p'})

  for element in visible_ress_ato:
    attempts = 1
    while attempts in range(11):
      try:
        content = read('{0}{1}'.format(base_url, element['href']), loadjs = True)
        ress_ato_soup = BeautifulSoup(content[0], 'html.parser')
        visible_iframe = ress_ato_soup.find('iframe')
        initial_iframe_source = visible_iframe['src']
      except:
        print('Error getting iframe for ress_ato element at {0}{1}. Attempt: {2}'.format(base_url, element['href'], attempts))
        attempts +=1
        continue
      break
    # move to next element in visible_ress_ato if attempts > 10
    if attempts >= 10:
      continue
    
    attempts = 1
    while attempts in range(11):
      try:
        content = read(initial_iframe_source, loadjs = True)
        iframe_soup = BeautifulSoup(content[0], 'html.parser')
        visible_iframe_ato = iframe_soup.find('iframe')
        iframe_source_ato = visible_iframe_ato['src']
      except:
        print('Error getting iframe for ress_ato element at {0}{1}. Attempt: {2}'.format(base_url, element['href'], attempts))
        attempts +=1
        continue
      break
    if attempts >= 10:
      continue
    nodes_arr = scrape_iframe(element, grade, iframe_source_ato, nodes_arr)

  for element in visible_ress_j3p:
    attempts = 1
    while attempts in range(11):
      try:
        content = read('{0}{1}'.format(base_url, element['href']), loadjs = True)
        ress_j3p_soup = BeautifulSoup(content[0], 'html.parser')
        visible_iframe_j3p = ress_j3p_soup.find('iframe')
        # getting iframe
        iframe_source_j3p = visible_iframe_j3p['src']
      except:
        print('Error getting iframe for ress_ato element at {0}{1}. Attempt: {2}'.format(base_url, element['href'], attempts))
        attempts +=1
        continue
      break
    if attempts >=10:
      continue

    # # getting iframe
    nodes_arr = scrape_iframe(element, grade, iframe_source_j3p, nodes_arr)

  return nodes_arr


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = SesamathChef()
    chef.main()