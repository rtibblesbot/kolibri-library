import pickle
import os
import pprint
import re
import le_utils
import json
import pkgutil 
from itertools import groupby

if not os.path.exists('chocmoose_info.pickle'):
    print("error, missing chocmoose_info.pickle, please download and unzip in current dir.")

with open('chocmoose_info.pickle', 'rb') as handle:
    info = pickle.load(handle)

# LOOK AROUND
########################################################################
#print(info.keys())

# non-entries keys
keys = ['extractor', 'extractor_key', 'title', '_type', 'webpage_url', 'id', 'webpage_url_basename']
for key in keys:
    print(key, ':', info[key])
            
# number of entries
print("\n\nlen(info['entries']) = ", len(info['entries']) )

# sample entry
#pp = pprint.PrettyPrinter()
#vinfo=info['entries'][5].copy()
#del vinfo['formats']  # to keep from printing 100+ lines
#del vinfo['requested_formats']  # to keep from printing 100+ lines
#pp.pprint(vinfo)

projects =  [
        { 'pattern': re.compile('.*[EÉI|Ȧŋi]bola.*'),
          'section': "Ebola A Poem For The Living" },
        { 'pattern': re.compile('.*Solar [Campaign|Camgian].*'),
          'section': "Solar Campaign promoting solar lights" },
        { 'pattern': re.compile('.*No Excuses.*', re.I),
          'section': "No Excuses domestic violence prevention" },
        { 'pattern': re.compile('.*Preventing.*', re.I),
          'section': "No Excuses domestic violence prevention" },
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
        { 'pattern': re.compile('.*Rape Victims.*', re.I),
          'section': "Rape Victims"},
        { 'pattern': re.compile('.*Congo.*', re.I),
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

LANGS_LOOKUP = [
        { 'pattern': re.compile('.*Mandarin.*'),
          'lang': 'zh'  },
        { 'pattern': re.compile('.*Greek.*'),
          'lang': 'el'  },
        { 'pattern': re.compile('.*Creole.*'),
          'lang': 'ht'  },
        { 'pattern': re.compile('.*Romanian.*'),
          'lang': 'ro'  },
        { 'pattern': re.compile('.*Sotho.*'),
          'lang': 'st'  },
        # From this: https://en.wikipedia.org/wiki/Krio_language
        { 'pattern': re.compile('.*Krio.*'),
          'lang': 'kri'  },
        { 'pattern': re.compile('.*Themne.*'),
          'lang': 'tem'  },
        { 'pattern': re.compile('.*Susu.*'),
          'lang': 'sus'  },
        { 'pattern': re.compile('.*Maninka.*'),
          'lang': 'emk'  },
        { 'pattern': re.compile('.*Mende.*'),
          'lang': 'men'  },
        { 'pattern': re.compile('.*Otetela.*'),
          'lang': 'tll'  },
        { 'pattern': re.compile('.*Mashi.*'),
          'lang': 'mho'  },
        { 'pattern': re.compile('.*Tshiluba.*'),
          'lang': 'lua'  },
        { 'pattern': re.compile('.*Francais.*'),
          'lang': 'fr'  },
        # Note: Just defined by project name  not because the language
        { 'pattern': re.compile('.*Solar.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Preventing.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Cartoons for Children.*'),
          'lang': "en"},
        { 'pattern': re.compile('.*Values-.*'),
          'lang': "en" },
        { 'pattern': re.compile('.*Éloge de la prévention.*'),
          'lang': 'fr'  },
        { 'pattern': re.compile('.*In Praise of Prevention.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Coming Together.*'),
          'lang': 'es'  },
        { 'pattern': re.compile('.*The Migrant.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Show You Care, Wear A Pair.*'),
          'lang': "en"},
        { 'pattern': re.compile('.*The Power of Animation.*'),
          'lang': "en"},
        # Typos
        { 'pattern': re.compile('.*Pigin.*'),
          'lang': 'pcm'  },
        { 'pattern': re.compile('.*Portugese.*'),
          'lang': 'pt'  },
        { 'pattern': re.compile('.*Enlgish.*'),
          'lang': 'en'  },
        ]

langlist = json.loads(pkgutil.get_data('le_utils', 'resources/languagelookup.json').decode('utf-8'))

def section_from_title(title):
    for project in projects:
        if project['pattern'].match(title):
            return project['section'] 

def lang_from_video(vid):
    for k,v in langlist.items():  
        name = v['name']
        native_name = v['native_name']
        if name in vid['title']:
           return k 
        if native_name and (native_name in vid['title']):
           return k 

def manual_lang_tag_from_video(vid):
    for language in LANGS_LOOKUP:
        if language['pattern'].match(vid['title']):
            return language['lang'] 

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


for vid in info['entries']:
    vid['lang_tag'] = lang_from_video(vid)
    if not vid['lang_tag']:
       vid['lang_tag'] = manual_lang_tag_from_video(vid)

remaining = 0
for vid in info['entries']:
    lang = vid['lang_tag']
    if not lang: 
        remaining += 1
        print(vid['webpage_url'])
        print(vid['title'],'\033[91m', vid['project_name'], '\033[0m')

print("Remaining videos without language:", remaining)

#for key, group in groupby(info['eitries'], lambda x: x['lang_tag']):
#    print(key) 
#    print(list(group)[0]['title'])
