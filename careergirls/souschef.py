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

def make_youtube_video(tubeid, name, _id):
    video_file = YouTubeVideoFile(youtube_id = tubeid, language=getlang('en').code)
    subtitle_file = YouTubeSubtitleFile(youtube_id = tubeid, language=getlang('en').code)
    if not isinstance(_id, str):
        print (_id, type(_id))
    content_node = VideoNode(
          source_id= str(_id),
          title= name,
          #author='First Last (author\'s name)',
          #description='Put file description here',
          language=getlang('en').code,
          license=licenses.PUBLIC_DOMAIN,  # TODO - fix!
          files=[video_file, subtitle_file],
    )
    return content_node
    
    


class CareerGirlsChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'careergirls.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'careergirls',         # channel's unique id
        'CHANNEL_TITLE': 'Career Girls',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': "CareerGirls.org is a comprehensive video-based career exploration tool for girls. It contains the largest online collection of career guidance videos focusing exclusively on diverse and accomplished women. The Career Girls collection includes video clips featuring women role models who work in hundreds of wide-ranging careers with an emphasis on Science, Technology, Engineering, and Math (STEM).",  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
  
        def get_things(all_things, parent_node):
            for thing in all_things:
                _id = thing.url.strip('/').split('/')[-1] # TODO hash
                this_node = TopicNode(source_id = thing.url,
                                      title=thing.title)
                content_node = make_youtube_video(thing.youtube, "Video: {}".format(thing.title), "video__{}".format(thing.url)) # TODO hash
                this_node.add_child(content_node)
               
                try:
                    os.mkdir('html')
                except Exception:
                    pass
                fn = "html/{}.zip".format(_id)
                with open(fn, "wb") as f:
                    f.write(thing.app)
                app_zip = HTMLZipFile(fn)
                app_node = HTML5AppNode(source_id = "app_{}".format(thing.url),
                                        title = "Being a {}".format(thing.title),
                                        license = licenses.PUBLIC_DOMAIN,
                                        files=[app_zip])
            
                this_node.add_child(app_node)
                parent_node.add_child(this_node)
 
        video_list = []
        video_set = set()
        channel = self.get_channel(**kwargs)
        job_node = TopicNode(source_id="jobs", title="Jobs")
        role_node = TopicNode(source_id="roles", title="Role Models")
        life_skill_node = TopicNode(source_id="lifeskills", title="Life Skills")
        
        channel.add_child(job_node)
        channel.add_child(role_node)
        
        all_jobs = list(cg_index.all_jobs())
        get_things(all_jobs, job_node)

        all_life_skills = list(cg_index.all_life_skills())
        get_things(all_life_skills, life_skill_node)

        # role models
        role_urls = set()
        for job in all_jobs:
            for role in job.roles:
                role_urls.add(role)
        
        for role_url in role_urls:
            _id = role_url.strip('/').split('/')[-1]
            role = cg_index.index_role(role_url)
            this_role = TopicNode(source_id = "role__{}".format(_id),
                                  title="{}, {}".format(role.title, role.name),
                                  description = role.bio)
            for v_id, v_name in zip(role.video_ids, role.video_names):
                if v_id is not None:
                    video_node = make_youtube_video(v_id[0], v_name[0], v_id[0])
                    this_role.add_child(video_node)
                    video_list.append(v_id[0])
                    video_set.add(v_id[0])
                            
            role_node.add_child(this_role)
        
        print ("DONE")
            
            # todo? : role.skill_links, role.skill_names
                        
            
            
        
            
        
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
