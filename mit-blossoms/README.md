Sushi Chef for MIT Blossoms
===========================
Import content from https://blossoms.mit.edu into kolibri format.


TODOs
-----

* Make HTMLZipFile paths names repeatable (so won't re-upload every time)
* Add manual override steps: \[3h\]
  * Fix videos with multiple languages in "Video Summary" (manual override) e.g. [https://blossoms.mit.edu/videos/lessons/flu\_math\_games](https://blossoms.mit.edu/videos/lessons/flu_math_games)
* Remove links from Additional Resources
  * remove href
* Style sheet for Additional Resources?
* Stretch goal: extract text from transcript and add as VideoNode description \[?\]
  * Not fasible because transcript not available in all languages
* Disable permanent caches so channel will update if new content posted



Install
-------
To install

    virtualenv -p python3  venv
    source venv/bin/activate
    pip install -r requirements.txt


Running locally for testing
---------------------------

    source venv/bin/activate
    export CONTENTWORKSHOP_URL="http://127.0.0.1:9003"
    export CONTENT_CURATION_TOKEN="a92a8ff947c8423ed0cd11c6ce33ad6b95b6564e"
    ./mitblossoms_chef.py --steps all   --pruned


Running for real
----------------

    source venv/bin/activate
    ./mitblossoms_chef.py  --steps all   --token=<your_ccserver_token>


Sushi Bar integration
---------------------
The remote progress reporting and logging will be enabled if the environment
variable `SUSHI_BAR_URL` exists. This is how to use remote reporting:

    pip install -r requirements.txt
    export SUSHI_BAR_URL="leq.sidewayspass.com"
    ./mitblossoms_chef.py --steps all --token=2727372372732727273723727327

Note `SUSHI_BAR_URL` must not have the `http://` prefix or a trailing slash.

Adding the extra argument `--daemon` will start the chef in daemon mode.
(Not implemented yet). TODO
