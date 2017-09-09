# sushi-chef-aflatoun
Script to create a Kolibri channel from the folder structure in aflatoun_tree




Second pass TODOs
-----------------

  - Ask Richard for context
  - understand exercise.json
  - understand perseus questions format

        {"question":
            {"content":"Which of the following is the Aflatoun Motto?\n\n\n[[☃ radio 1]]","images":{},
              "widgets":
                {"radio 1":{"type":"radio","graded":true,
                   "options":{"choices":[
                     {"correct":false,"content":"Explore, Think, Investigate and Play.\n\n"},
                     {"correct":true,"content":"Explore, Think, Investigate and Act.\n"},
                     {"correct":false,"content":"Explore, Think, Investigate and Reflect\n"}],
                    "randomize":true,
                    "multipleSelect":false,
                    "displayCount":null,
                    "hasNoneOfTheAbove":false,
                    "onePerLine":true,
                    "deselectEnabled":false},
              "version":{"major":1,"minor":0}}}},
              "answerArea":{"type":"multiple","options":{"content":"","images":{},"widgets":{}},"calculator":false,"periodicTable":false},
              "itemDataVersion":{"major":0,"minor":1},"hints":[]
            },

  - Notion of `subject` in json e.g. "subject": "Le monde et moi", ?
  - Notion of "related content": "03faafl41.5qr.exercise" in json?



Future work
-----------

  - Implement tags upload in ricecooker
  - ask Jordan to implement Studio side
  - Implement `_keywords_to_tags` that accept str or list of str and returns list of str
      e.g.

          "keywords": [
            "Club",
            "activit\u00e9s"
          ],
      or
          "keywords": "Sociale",


