import pandas
import os
import json
FAILED_IMAGES_JSON = os.path.join("chefdata", "failed_links", "failed_image_links.json")
def read_videos_xls(xls):
    """
    Build dict for channel structure
    Dict structure:
        Language > Grade > Subject > Chapter > Topic Name > Content Type > Content
    """
    data_from_xls = pandas.read_excel(xls, keep_default_na=False, na_values='')
    data_dict = {}
    # building dict row by row
    for index, row in data_from_xls.iterrows():
        # Skip any content that does not have a link and all assessments
        # as we will be getting assessment data from a separate xls
        if row["Link to Content"] == "N/A" or row["Content Type"] == "Assessment":
            continue
        # adding language keys to dict
        # converting strings to lower due to inconsistent naming convention in xls
        language = row["Language"].lower().strip()
        if language not in data_dict:
            data_dict[language] = {}
        
        # addingggrade keys to dict
        grade = row["Grade"]
        if grade not in data_dict[language]:
            data_dict[language][grade] = {}

        subject = row["Subject"].lower().strip()
        if subject not in data_dict[language][grade]:
            data_dict[language][grade][subject] = {}

        chapter_num = row["Chapter No"]
        chapter_name = row["Chapter Name"].lower().strip()
        chapter = "{} - {}".format(chapter_num, chapter_name)

        if chapter not in data_dict[language][grade][subject]:
            data_dict[language][grade][subject][chapter] = {}



        topic_name = row["Topic Name"].lower().strip()
        if topic_name not in data_dict[language][grade][subject][chapter]:
            data_dict[language][grade][subject][chapter][topic_name] = {}

        # adding chapter assessment
        # data_dict[language][grade][subject][chapter][topic_name]["chapter assessment"] = {}
        
        # Assessment = Exercise, Video = Video
        content_type = row["Content Type"].lower().strip()
        if content_type not in data_dict[language][grade][subject][chapter][topic_name]:
            data_dict[language][grade][subject][chapter][topic_name][content_type] = {}

        link = row["Link to Content"].lower().strip()
        if link not in data_dict[language][grade][subject][chapter][topic_name][content_type]:
            data_dict[language][grade][subject][chapter][topic_name][content_type][link] = {
                "title": row["Video/Assessment Title"],
                "copyright": row["Copyright"],
                "license": row["License"],
                "icon": row["Icon"]
            }
    return data_dict


def read_assessment_xls(xls, data):
    data_from_xls = pandas.read_excel(xls, keep_default_na=False, na_values = '')
    # to map to correct option given which is the right answer
    for index, row in data_from_xls.iterrows():
        question_parts = [x.strip() for x in row["Question Set Name"].split("|")]
        topic = None
        chapter_title = None

        if len(question_parts) == 4:
            # if length === 4, then chapter assessment
            # if chapter assessment, chapter is located at str_parts[0]
            chapter_title = question_parts[0]
        elif len(question_parts) == 5:
            # if normal assessment, chapter is located at str_parts[1] and topic is located at str_parts[0]
            topic = question_parts[0].lower()
            chapter_title = question_parts[1].strip()
        else:
            print("Error: Question Set Name not in correct format")
            # self.add_to_failed(row["Medium"], row["Question Set Name"], row["QuestionText"])
            continue

        language = row["Medium"].lower()
        grade = row["Class"]
        if row["Subject"] == "Math" or row["Subject"] == "Maths":
            # provided xls from TTL has Subject listed as mathematics on videos.xls and math/maths in assessments.xls
            subject = 'mathematics'
        else:
            subject = row["Subject"].lower()
        
        chapter = "{} - {}".format(row["ChapterNo"], chapter_title).lower()
        content_type = "assessment"
        
        # some questions only have an image with no text
        question_text = row["QuestionText"] if not pandas.isnull(row["QuestionText"]) else None
        
        question_id = row["QuestionId"]


        question_image = None    # None if no associate question image
        # will remain None if there is no option (ex: yes or no question will only have 2 options)
        option_one = None
        option_two = None
        option_three = None
        option_four = None
        # holds all available answers
        answers = []
        # query which column the options are located in and if there is a question Image
        if not pandas.isnull(row["QuestionImage"]):
            question_image = "![]({})".format(get_image_path(row["QuestionImage"]))
            
        
        if (not pandas.isnull(row["Option1"])) or (not pandas.isnull(row["Option1Image"])):
            option_one = row["Option1"] if not pandas.isnull(row["Option1"]) else "![]({})".format(get_image_path(row["Option1Image"]))
            answers.append(option_one)

        if (not pandas.isnull(row["Option2"])) or (not pandas.isnull(row["Option2Image"])):
            option_two = row["Option2"] if not pandas.isnull(row["Option2"]) else "![]({})".format(get_image_path(row["Option2Image"]))
            answers.append(option_two)

        if (not pandas.isnull(row["Option3"])) or (not pandas.isnull(row["Option3Image"])):
            option_three = row["Option3"] if not pandas.isnull(row["Option3"]) else "![]({})".format(get_image_path(row["Option3Image"]))
            answers.append(option_three)

        if (not pandas.isnull(row["Option4"])) or (not pandas.isnull(row["Option4Image"])):
            option_four = row["Option4"] if not pandas.isnull(row["Option4"]) else "![]({})".format(get_image_path(row["Option4Image"]))
            answers.append(option_four)

        answer_key = {
            1: option_one,
            2: option_two,
            3: option_three,
            4: option_four,
        }
        
        answer = answer_key[row["AnswerNo"]]

        if len(answers) > 4:
            print(answers)
        
        question_metadata = {
            "question": question_text,
            "question_image": question_image,
            "correct_answer": answer,
            "all_answers": answers
        }

        # check if chapter exists as some chapters only appear on assessment excel
        if chapter not in data[language][grade][subject]:
            data[language][grade][subject][chapter] = {}

        # have to check if topic exists
        if topic:
            if topic not in data[language][grade][subject][chapter]:
                data[language][grade][subject][chapter][topic] = {}
                # add in assessment array. array will hold each question's metadata
            if content_type not in data[language][grade][subject][chapter][topic]:
                data[language][grade][subject][chapter][topic][content_type] = {}
            data[language][grade][subject][chapter][topic][content_type][question_id] = question_metadata
            # print(data[language][grade][subject][chapter][topic][content_type])
        else:
            chapter_assessment = "Chapter Assessment"
            if chapter_assessment not in data[language][grade][subject][chapter]:
                data[language][grade][subject][chapter][chapter_assessment] = {}
            data[language][grade][subject][chapter][chapter_assessment][question_id] = question_metadata
            # print(data[language][grade][subject][chapter][chapter_assessment])


        # location where to add question objects

    return data

def get_image_path(imageString):
    path_arr = imageString.replace(" ", "").split('/')
    path = os.path.join('files', *path_arr)
    if not os.path.isfile(path):
        add_to_failed(path_arr)
    return path


def add_to_failed(path_arr):
    grade = path_arr[1]
    chapter = path_arr[2]
    image_name = path_arr[3]
    with open(FAILED_IMAGES_JSON, encoding = 'utf-8') as f:
        try:
            data = json.loads(f.read())
        except:
            # no data in json file
            print('no data in json file')
            with open(FAILED_IMAGES_JSON, 'w', encoding='utf-8') as json_file:
                dict_failed = {}
                dict_failed[grade] = {}
                dict_failed[grade][chapter] = []
                dict_failed[grade][chapter].append(image_name)
                json.dump(dict_failed, json_file, indent = 4, ensure_ascii=False)
                return
        
        with open(FAILED_IMAGES_JSON, 'w', encoding = 'utf-8') as json_file:
            if grade not in data:
                data[grade] = {}
            if chapter not in data[grade]:
                data[grade][chapter] = []
            data[grade][chapter].append(image_name)
            json.dump(data, json_file, indent=4, ensure_ascii=False)
            return