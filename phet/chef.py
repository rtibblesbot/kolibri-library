import json
import requests
import tempfile
import zipfile

from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from ricecooker.classes.files import HTMLZipFile, VideoFile
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter

from le_utils.constants import licenses

sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)

ID_BLACKLIST = ["html", "by-device", "new", "mathapplications", "mathconcepts", "quantum", "quantum-phenomena", "general"]

def construct_channel(*args, **kwargs):

    channel = ChannelNode(
        source_domain="phet.colorado.edu",
        source_id="phet-html5-simulations",
        title="PhET Interactive Simulations",
    )

    r = sess.get("https://phet.colorado.edu/services/metadata/1.1/simulations?format=json&type=html&locale=en")
    data = json.loads(r.content.decode())
    process_category(channel, "1", data["categories"], {sim["id"]: sim for sim in data["projects"]})

    return channel

def process_category(parent, cat_id, categories, sims):
    """
    Process a category, and add all its sub-categories, and its simulations/videos.
    """

    cat = categories[str(cat_id)]
    
    # loop through all subtopics and recursively add them
    # (reverse order seems to give most rational results)
    for child_id in reversed(cat["childrenIds"]):
        subcat = categories[str(child_id)]
        if subcat["name"] in ID_BLACKLIST:
            continue
        subtopic = TopicNode(
            source_id=subcat["name"],
            title=subcat["name"].replace("-", " ").title()
        )
        parent.add_child(subtopic)
        process_category(subtopic, child_id, categories, sims)
    
    # loop through all sims in this topic and add them
    for sim_id in cat["simulationIds"]:
        if sim_id not in sims:
            continue
        project = sims[sim_id]
        sim = project["simulations"][0]["localizedSimulations"][0]
        process_sim(parent, project, sim)

def process_sim(topic, project, sim):
    """
    Download, zip, and add a node for a sim, as well as any associated video.
    """

    # download the sim and bundle in a zip file
    temppath = tempfile.mkstemp(suffix=".zip")[1]
    with zipfile.ZipFile(temppath, "w") as zf:
        zf.writestr("index.html", sess.get(sim["downloadUrl"]).content)
    zippath = create_predictable_zip(temppath)

    # create a node for the sim
    simnode = HTML5AppNode(
        source_id=project["name"],
        files=[HTMLZipFile(zippath)],
        title=sim["title"],
        license=licenses.CC_BY,
        thumbnail=project["simulations"][0]["media"]["thumbnailUrl"],
    )

    # if there's a video, extract it and put it in the topic right before the sim
    videos = project["simulations"][0]["media"]["vimeoFiles"]
    if videos:
        video_url = [v for v in videos if v.get("height") == 540][0]["link"]

        videonode = VideoNode(
            source_id="%s-video" % project["name"],
            files=[VideoFile(video_url)],
            title="%s (intro video)" % sim["title"],
            license=licenses.CC_BY,
            thumbnail=project["simulations"][0]["media"]["thumbnailUrl"],
        )

        topic.add_child(videonode)

    # add the sim node into the topic
    topic.add_child(simnode)
