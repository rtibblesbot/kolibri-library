from le_utils.constants.labels import levels
from le_utils.constants.labels import subjects

METADATA_BY_SLUG = {
    'elementary school': {'grade_levels': [levels.LOWER_PRIMARY], 'categories': []},
    'middle school': {'grade_levels': [levels.LOWER_SECONDARY], 'categories': []},
    'high school': {'grade_levels': [levels.UPPER_PRIMARY], 'categories': []},
    'university': {'grade_levels': [levels.PROFESSIONAL], 'categories': []},
    'mathconcepts': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'math concepts': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'mathapplications': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'math applications': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'light & radiation': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'electricity, magnets & circuits': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'biology': {'grade_levels': [], 'categories': [subjects.BIOLOGY]},
    'chemistry': {'grade_levels': [], 'categories': [subjects.CHEMISTRY]},
    'earth-science': {'grade_levels': [], 'categories': [subjects.EARTH_SCIENCE]},
    'earth science': {'grade_levels': [], 'categories': [subjects.EARTH_SCIENCE]},
    'math': {'grade_levels': [], 'categories': [subjects.MATHEMATICS]},
    'general': {'grade_levels': [], 'categories': [subjects.CHEMISTRY]},
    'physics': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'motion': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'sound & waves': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'work-energy-and-power': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'work, energy & power': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'heat-and-thermodynamics': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'quantum-phenomena': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'heat & thermo': {'grade_levels': [], 'categories': [subjects.PHYSICS]},
    'quantum phenomena': {'grade_levels': [], 'categories': [subjects.CHEMISTRY]},
    'University': {'grade_levels': [levels.PROFESSIONAL], 'categories':[]}
}
