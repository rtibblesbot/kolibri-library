#!/usr/bin/env python
import os
import sys
from bs4 import BeautifulSoup
import subprocess
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages


# Run constants
################################################################################
CHANNEL_NAME = "Ceibal"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-ceibal-es"    # Channel's unique id
CHANNEL_DOMAIN = "rea.ceibal.edu.uy"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = "Plan Ceibal se creó en 2007 como un plan de inclusión"\
                    " e igualdad de oportunidades con el objetivo de apoyar "\
                    "con tecnología las políticas educativas uruguayas. Desde "\
                    "su implementación, cada niño que ingresa al sistema "\
                    "educativo público en todo el país accede a una computadora "\
                    "para su uso personal con conexión a Internet gratuita desde "\
                    "el centro educativo. Además, Plan Ceibal provee un conjunto "\
                    "de programas, recursos educativos y capacitación docente que "\
                    "transforma las maneras de enseñar y aprender.\nEl repositorio "\
                    "de Recursos educativos abiertos (REA) de Ceibal es una plataforma "\
                    "que alberga los REA construidos por los contenidistas de Ceibal "\
                    "y por la comunidad educativa; su misión no solamente es hacer de "\
                    "depósito, sino el ser un espacio para el intercambio de recursos y "\
                    "materiales pedagógicos facilitando la adaptación de estos y la interacción "\
                    "entre distintas comunidades de práctica."
CHANNEL_THUMBNAIL = "https://yt3.ggpht.com/a/AGF-l78Li2_W_X6fyV3lu6etxgfcFmb1xr73FCao6A=s900-mo-c-c0xffffffff-rj-k-no"

# Additional constants
################################################################################
BASE_URL = "https://rea.ceibal.edu.uy/"
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# Determines which topics to scrape. In case we decide to scrape the whole channel,
# we can just get rid of the logic around this
TOPICS_TO_INCLUDE = ['educacion_socio_emocional', 'comunicacion_y_tecnologia']
LICENSE_MAP = {
    'BY-NC': licenses.CC_BY_NCLicense,
    'BY-NC-SA':licenses.CC_BY_NC_SALicense,
    'BY': licenses.CC_BYLicense
}


# The chef subclass
################################################################################
class CeibalChef(SushiChef):
    """
    This class uploads the Ceibal channel to Kolibri Studio.
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
    # Your chef subclass can override/extend the following method:
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

        LOGGER.info('Scraping Ceibal channel...')
        self.scrape_channel(channel)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction
        LOGGER.info('DONE')
        raise KeyError

        return channel

    def scrape_channel(self, channel):
        # Read from Categorias dropdown menu
        page = BeautifulSoup(downloader.read(BASE_URL), 'html5lib')
        dropdown = page.find('a', {'id': 'btn-categorias'}).find_next_sibling('ul')

        # Go through dropdown and generate topics and subtopics
        for category_list in dropdown.find_all('li', {'class': 'has-children'}):

            # Parse categories
            for category in category_list.find_all('li', {'class': 'has-children'}):
                category_name = category.find('a').string
                topic = nodes.TopicNode(title=category_name, source_id=get_source_id(category_name))
                LOGGER.info(category_name)

                # Parse subcategories
                add_topic_to_tree = False
                for subcategory in category.find_all('li'):
                    if not subcategory.attrs.get('class') or 'go-back' not in subcategory.attrs['class']:
                        add_topic_to_tree = True
                        # Get rid of this check to scrape entire site
                        if subcategory.find('a')['href'].split('/')[-1] in TOPICS_TO_INCLUDE:
                            subcategory_name = subcategory.find('a').string
                            subcategory_link = subcategory.find('a')['href']
                            LOGGER.info('  {}'.format(subcategory_name))
                            subtopic = nodes.TopicNode(title=subcategory_name, source_id=get_source_id(subcategory_link))

                            # Parse resources
                            self.scrape_subcategory(subcategory_link, subtopic)

                if add_topic_to_tree:
                    channel.add_child(topic)

    def scrape_subcategory(self, link, topic):
        url = "{}{}".format(BASE_URL, link.lstrip("/"))
        resource_page = BeautifulSoup(downloader.read(url), 'html5lib')

        # Skip "All" category
        for resource_filter in resource_page.find('div', {'class': 'menu-filtro'}).find_all('a')[1:]:
            print('    {}'.format(resource_filter.string))
            param = resource_page.find('li', {'id': 'inicial-primaria'}).find('a')['href']
            source_id = get_source_id('{}/{}'.format(topic.title, resource_filter.string))
            filter_topic = nodes.TopicNode(title=resource_filter.string, source_id=source_id)
            self.scrape_resource_list(url + param, filter_topic)
            topic.add_child(filter_topic)

    def scrape_resource_list(self, url, topic):
        resource_list_page = BeautifulSoup(downloader.read(url), 'html5lib')

        # Go through pages, omitting Previous and Next buttons
        for page in resource_list_page.find_all('a', {'class': 'page-link'})[1:-1]:
            resource_list = BeautifulSoup(downloader.read(page['href']), 'html5lib')
            for resource in resource_list.find_all('a', {'class': 'card-link'}):
                self.scrape_resource(resource['href'], topic)


    def scrape_resource(self, url, topic):
        resource = BeautifulSoup(downloader.read(url), 'html5lib')
        print('      {}'.format(resource.find('h2').string))
        title = resource.find('h2').string
        source_id = url
        description = resource.find('form').find_all('p')[1].string
        thumbnail = resource.find('div', {'class': 'img-recurso'}).find('img')['src']

        for data_section in resource.find('div', {'class': 'datos_generales'}).find_all('h4'):
            if 'Licencia' in data_section.string:
                license = LICENSE_MAP[data_section.find_next_sibling('p').string]()
            elif 'Autor' in data_section.string:
                author = data_section.find_next_sibling('p').string

        tags = [tag.string for tag in resource.find_all('a', {'class': 'tags'})]
        file = self.download_resource(resource.find('div', {'class': 'decargas'}).find('input')['value'])


    def download_resource(self, url):
        filename = url.split('/')[-1]
        filename, ext = os.path.splitext(filename)
        elp_write_path = os.path.sep.join([DOWNLOAD_DIRECTORY, '{}.elp'.format(filename)])
        if not os.path.isfile(elp_write_path):
            with open(elp_write_path, 'wb') as fobj:
                fobj.write(downloader.read(url))

        zip_write_path = os.path.join(DOWNLOAD_DIRECTORY, '{}.zip'.format(filename))
        subprocess.run(["exe_do", "--export", "webzip", elp_write_path, zip_write_path])





def get_source_id(text):
    return "{}{}".format(BASE_URL, text.lstrip('/').lower().replace(' ', '_'))

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = CeibalChef()
    chef.main()
