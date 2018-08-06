#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import logging
from ricecooker.chefs import SushiChef
from le_utils.constants import licenses
from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode, HTML5AppNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile, YouTubeVideoFile, YouTubeSubtitleFile
import cg_index
from le_utils.constants.languages import getlang

LOGGER = logging.getLogger()


class CareerGirlsChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'careergirls.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'careergirls',         # channel's unique id
        'CHANNEL_TITLE': 'Career Girls',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': "Career Girls is founded on the dream that every girl around the world has access to diverse and accomplished women role models to learn from their experiences and discover their own path to empowerment.",  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        job_node = TopicNode(source_id="jobs", title="Jobs")
        role_node = TopicNode(source_id="roles", title="Role Models")
        
        channel.add_child(job_node)
        channel.add_child(role_node)
        
        for job in cg_index.all_jobs():
            _id = job.url.strip('/').split('/')[-1]
            this_node = TopicNode(source_id = job.url,
                                  title=job.title)
            video_file = YouTubeVideoFile(youtube_id = job.youtube, language=getlang('en').code)
            subtitle_file = YouTubeSubtitleFile(youtube_id = job.youtube, language=getlang('en').code)
            content_node = VideoNode(
                  source_id='video__{}'.format(job.url),
                  title="Video: {}".format(job.title),
                  #author='First Last (author\'s name)',
                  #description='Put file description here',
                  language=getlang('en').code,
                  license=licenses.PUBLIC_DOMAIN,  # TODO - fix!
                  files=[video_file, subtitle_file],
            )            
            
            this_node.add_child(content_node)
            
            try:
                os.mkdir('html')
            except Exception:
                pass
            fn = "html/{}.zip".format(_id)
            with open(fn, "wb") as f:
                f.write(job.app)
            
            app_zip = HTMLZipFile(fn)
            app_node = HTML5AppNode(source_id = "app_{}".format(job.url),
                               title = "Being a {}".format(job.title),
                               license = licenses.PUBLIC_DOMAIN,
                               files=[app_zip])
            
            this_node.add_child(app_node)
            job_node.add_child(this_node)
            
        
        return channel
    
if __name__ == '__main__':
    """
    Set the environment var `CONTENT_CURATION_TOKEN` (or `KOLIBRI_STUDIO_TOKEN`)
    to your Kolibri Studio token, then call this script using:
        python souschef.py  -v --reset
    """
    mychef = CareerGirlsChef()
    if 'KOLIBRI_STUDIO_TOKEN' in os.environ:
        os.environ['CONTENT_CURATION_TOKEN'] = os.environ['KOLIBRI_STUDIO_TOKEN']
    mychef.main( )
