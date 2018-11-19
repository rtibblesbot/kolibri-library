import csv
import hashlib
from itertools import groupby
import json
import logging
from operator import itemgetter
import os
import re
import requests

from ricecooker.config import LOGGER




# STRUCTURE = CSV EXPORT of the Google Sheet titled "Aldarayn structure spec"
# https://docs.google.com/spreadsheets/d/1QKXvXxLS1dByxrcYHTT2Y2e-eglvDMhkXvSVvFppq20/edit#gid=0
################################################################################
GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
ALDARAYN_SHEET_ID = '1QKXvXxLS1dByxrcYHTT2Y2e-eglvDMhkXvSVvFppq20'
ALDARAYN_STRUCTURE_SHEET_GID = '0'
ALDARAYN_SHEET_CSV_URL = GSHEETS_BASE + ALDARAYN_SHEET_ID + '/export?format=csv&gid=' + ALDARAYN_STRUCTURE_SHEET_GID
ALDARAYN_SHEET_CSV_PATH = 'chefdata/aldarayn_structure.csv'

L1_KEY = 'Level 1 Topic *'
L2_KEY = 'Level 2 Topic *'
L3_KEY = 'Level 3 Topic'
L4_KEY = 'Level 4 Topic'
TITLE_KEY = 'Title *'
SEPARATOR_KEY = '-'
WEBSITE_CAT1_KEY = 'Website Category Level 1 *'
WEBSITE_CAT2_KEY = 'Website Category Level 2'
WEBSITE_TITLE_KEY = 'Website Course Title *'
WEBSITE_URL_KEY = 'Course URL *'
WEBSITE_CATID_KEY = 'Category ID *'
CATEGORY_TRANS_KEY = 'Combined Category Trans'
COURSE_TRANS_KEY = 'Course Trans'

ALDARAYN_SHEET_CSV_FILEDNAMES = [
    L1_KEY,
    L2_KEY,
    L3_KEY,
    L4_KEY,
    TITLE_KEY,
    SEPARATOR_KEY,
    WEBSITE_CAT1_KEY,
    WEBSITE_CAT2_KEY,
    WEBSITE_TITLE_KEY,
    WEBSITE_URL_KEY,
    WEBSITE_CATID_KEY,
    CATEGORY_TRANS_KEY,
    COURSE_TRANS_KEY
]


def download_structure_csv():
    response = requests.get(ALDARAYN_SHEET_CSV_URL)
    csv_data = response.content.decode('utf-8')
    with open(ALDARAYN_SHEET_CSV_PATH, 'w') as csvfile:
        csvfile.write(csv_data)
        LOGGER.info('Succesfully saved ' + ALDARAYN_SHEET_CSV_PATH)
    return ALDARAYN_SHEET_CSV_PATH


def _clean_dict(row):
    """
    Transform empty strings values of dict `row` to None.
    """
    row_cleaned = {}
    for key, val in row.items():
        if val is None or val == '':
            row_cleaned[key] = None
        else:
            row_cleaned[key] = val.strip()
    return row_cleaned

def load_aldarayn_structure():
    csv_path = download_structure_csv()
    struct_list = []
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=ALDARAYN_SHEET_CSV_FILEDNAMES)
        next(reader)  # Skip Headers row
        for row in reader:
            clean_row = _clean_dict(row)
            if clean_row[L1_KEY] is not None and clean_row[L2_KEY] is not None:                # @Dave: you can add other sanity checks here
                struct_list.append(clean_row)
            else:
                LOGGER.warning('Unrecognized structure row {}'.format(str(clean_row)))
    return struct_list


# ALDARAYN_STRUCT_LIST = load_aldarayn_structure()



# STRUCTURE LIST TO STRUCTURE TREE
################################################################################



