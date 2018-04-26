from git import Repo
import ntpath
from pathlib import Path


def if_dir_exists(filepath):
    file_ = Path(filepath)
    return file_.is_dir()


def remove_links(content):
    if content is not None:
        for link in content.find_all("a"):
            link.replaceWithChildren()


def get_name_from_url(url):
    head, tail = ntpath.split(url)
    params_index = tail.find("&")
    if params_index != -1:
        tail = tail[:params_index]
    params_index = tail.find("?")
    if params_index != -1:
        tail = tail[:params_index]

    basename = ntpath.basename(url)
    params_b_index = basename.find("&")
    if params_b_index != -1:
        basename = basename[:params_b_index]
    return tail or basename


def clone_repo(git_url, repo_dir):
    if not if_dir_exists(repo_dir):
        Repo.clone_from(git_url, repo_dir)
