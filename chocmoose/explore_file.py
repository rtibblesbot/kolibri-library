import pickle
import os
import pprint
import re

if not os.path.exists('chocmoose_info.pickle'):
    print("error, missing chocmoose_info.pickle, please download and unzip in current dir.")


with open('chocmoose_info.pickle', 'rb') as handle:
    info = pickle.load(handle)

# LOOK AROUND
########################################################################
print(info.keys())

# non-entries keys
keys = ['extractor', 'extractor_key', 'title', '_type', 'webpage_url', 'id', 'webpage_url_basename']
for key in keys:
    print(key, ':', info[key])
            
# number of entries
print("\n\nlen(info['entries'] = ", len(info['entries']) )

# sample entry
pp = pprint.PrettyPrinter()
vinfo=info['entries'][5].copy()
del vinfo['formats']  # to keep from printing 100+ lines
del vinfo['requested_formats']  # to keep from printing 100+ lines
pp.pprint(vinfo)

projects =  [
        { 'pattern': re.compile('.*[EÉI|Ȧŋi]bola.*'),
          'section': "Ebola A Poem For The Living" },
        { 'pattern': re.compile('.*No Excuses.*', re.I),
          'section': "No Excuses domestic violence prevention" },
        { 'pattern': re.compile('.*Solar [Campaign|Camgian].*'),
          'section': "Solar Campaign promoting solar lights" },
        { 'pattern': re.compile('.*buzz-and-bite.*'),
          'section': "Buzz and Bite malaria prevention" },
        { 'pattern': re.compile('.*the-three-amigos.*'),
          'section': "Three Amigos HIV/AIDS prevention" },
        { 'pattern': re.compile('.*Values-.*'),
          'section': "Values For Young Children" },
        { 'pattern': re.compile('.*Zika Prevention.*'),
          'section': "Zika Prevention" },
        { 'pattern': re.compile('.*The Switch Animation.*'),
          'section': "The Switch Animation"},
        { 'pattern': re.compile('.*The Migrant.*'),
          'section': "The Migrant"},
        { 'pattern': re.compile('.*Spot.*'),
          'section': "Rashid Living With Type 1 Diabetes"},
        { 'pattern': re.compile('.*Asbestos.*'),
          'section': "Asbestos"},
        { 'pattern': re.compile('.*[Rape Victims|Congo]+.*', re.I),
          'section': "Rape Victims"},
        { 'pattern': re.compile('.*Coming Together.*'),
          'section': "Coming Together"},
        { 'pattern': re.compile('.*N4A.*'),
          'section': "Nature for All"},
        { 'pattern': re.compile('.*Show You Care, Wear A Pair.*'),
          'section': "Show You Care - Wear A Pair"},
        { 'pattern': re.compile('.*Malawi.*'),
          'section': "Violence Against Children in Malawi"},
        { 'pattern': re.compile('.*Cartoons for Children.*'),
          'section': "Cartoons For Children's Rights"},
        { 'pattern': re.compile('.*Nature For All.*'),
          'section': "Nature For All"},
        { 'pattern': re.compile('.*Biodiver.*'),
          'section': "Biodiversity Is Us"},
        { 'pattern': re.compile('.*cyber-security.*'),
          'section': "UNICEF Cyber Security"},
        { 'pattern': re.compile('.*Preventing.*'),
          'section': "Preventing Violence"},
        { 'pattern': re.compile('.*The Power of Animation.*'),
          'section': "The Power of Animation and Humour"},
        ] 

def section_from_title(title):
    for project in projects:
        if project['pattern'].match(title):
            return project['section'] 

for vid in info['entries']:
    vid['project_name'] = section_from_title(vid['title'])

remaining = 0
for vid in info['entries']:
    project = vid['project_name']
    if not project: 
        remaining += 1
        print(vid['webpage_url'])
        print(vid['title'],'\033[91m', vid['project_name'], '\033[0m')

print("Remaining videos:", remaining)
