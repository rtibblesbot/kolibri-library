import csv

CHANNEL_METADATA = {}

with open('titles_taglines_descriptions.csv') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    line_count = 0
    for row in csv_reader:
        if line_count == 0:
            line_count += 1
            continue
        else:
            CHANNEL_METADATA[row[1]] = {'title': row[2], 'tagline': row[3], 'description': row[4]}

import ipdb;ipdb.set_trace()
