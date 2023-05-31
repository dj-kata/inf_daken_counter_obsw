from datetime import datetime
import os
from logging import getLogger
from PIL import Image
import re

logger_child_name = 'result'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded result.py')

from filter import filter
from gui.general import get_imagevalue

results_basepath = 'results'
filtereds_basepath = 'filtered'

adjust_length = 94

class ResultInformations():
    def __init__(self, play_mode, difficulty, level, notes, music):
        self.play_mode = play_mode
        self.difficulty = difficulty
        self.level = level
        self.notes = notes
        self.music = music

class ResultValues():
    def __init__(self, best, current, new):
        self.best = best
        self.current = current
        self.new = new

class ResultDetails():
    def __init__(self, graphtype, options, clear_type, dj_level, score, miss_count, graphtarget):
        self.graphtype = graphtype
        self.options = options
        self.clear_type = clear_type
        self.dj_level = dj_level
        self.score = score
        self.miss_count = miss_count
        self.graphtarget = graphtarget

class ResultOptions():
    def __init__(self, arrange, flip, assist, battle):
        self.arrange = arrange
        self.flip = flip
        self.assist = assist
        self.battle = battle
        self.special = (arrange is not None and 'H-RAN' in arrange) or self.battle

class Result():
    def __init__(self, image, informations, play_side, rival, dead, details):
        self.image = image
        self.saved = False
        self.filtered = None
        self.informations = informations
        self.play_side = play_side
        self.rival = rival
        self.dead = dead
        self.details = details

        now = datetime.now()
        self.timestamp = f"{now.strftime('%Y%m%d-%H%M%S')}"
        self.filename = generate_resultfilename(self.informations.music, self.timestamp)
    
    def has_new_record(self):
        return any([
            self.details.clear_type.new,
            self.details.dj_level.new,
            self.details.score.new,
            self.details.miss_count.new
        ])
    
    def save(self):
        if not os.path.exists(results_basepath):
            os.mkdir(results_basepath)

        filepath = os.path.join(results_basepath, self.filename)
        if os.path.exists(filepath):
            return False
        
        self.image.save(filepath)
        self.saved = True

        return True
    
    def filter(self):
        self.filtered = filter(self)
    
    def save_filtered(self):
        if not os.path.exists(filtereds_basepath):
            os.mkdir(filtereds_basepath)

        filepath = os.path.join(filtereds_basepath, self.filename)
        if os.path.exists(filepath):
            return False

        self.filtered.save(filepath)

        return True

def generate_resultfilename(music, timestamp):
    if music is None:
        return f"{timestamp}.jpg"

    music_convert=re.sub(r'[\\|/|:|*|?|.|"|<|>|/|]', '', music)
    adjustmented = music_convert if len(music_convert) < adjust_length else f'{music_convert[:adjust_length]}..'
    return f"{adjustmented}_{timestamp}.jpg"

def get_resultimagevalue(music, timestamp):
    filepath = os.path.join(results_basepath, generate_resultfilename(music, timestamp))
    if not os.path.exists(filepath):
        filepath = os.path.join(results_basepath, generate_resultfilename(None, timestamp))
        if not os.path.exists(filepath):
            return None
    
    image = Image.open(filepath)

    return get_imagevalue(image)

def get_filteredimagevalue(music, timestamp):
    filepath = os.path.join(filtereds_basepath, generate_resultfilename(music, timestamp))
    if not os.path.exists(filepath):
        filepath = os.path.join(filtereds_basepath, generate_resultfilename(None, timestamp))
        if not os.path.exists(filepath):
            return None
    
    image = Image.open(filepath)

    return get_imagevalue(image)
