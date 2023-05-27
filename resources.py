import os
import numpy as np
from winsound import SND_FILENAME,PlaySound
from logging import getLogger
import pickle
from os.path import isfile

logger_child_name = 'resources'

logger = getLogger().getChild(logger_child_name)
logger.debug(f'loaded resources.py')

from define import define
from mask import Mask

resources_dirname = 'resources'

masks_dirname = 'masks'
sounds_dirname = 'sounds'

masks_dirpath = os.path.join(resources_dirname, masks_dirname)
sounds_dirpath = os.path.join(resources_dirname, sounds_dirname)

recog_musics_filename = f'musics{define.music_recognition_vesion}.json'
recog_musics_filepath = os.path.join(resources_dirname, recog_musics_filename)

sound_result_filepath = os.path.join(sounds_dirpath, 'result.wav')

class ResourceTimestamp():
    def __init__(self, resourcename):
        self.filepath = os.path.join(resources_dirname, f'{resourcename}.timestamp')
    
    def get_timestamp(self):
        if not os.path.exists(self.filepath):
            return None
        with open(self.filepath, 'r') as f:
            timestamp = f.read()

        return timestamp

    def write_timestamp(self, timestamp):
        with open(self.filepath, 'w') as f:
            f.write(timestamp)

def play_sound_result():
    if os.path.exists(sound_result_filepath):
        PlaySound(sound_result_filepath, SND_FILENAME)

def load_resource_serialized(resourcename):
    filepath = os.path.join(resources_dirname, f'{resourcename}.res')
    if not isfile(filepath):
        return None
    
    with open(filepath, 'rb') as f:
        value = pickle.load(f)
    
    return value

def load_resource_numpy(resourcename):
    filepath = os.path.join(resources_dirname, f'{resourcename}.npy')
    return np.load(filepath)

def get_resource_filepath(filename):
    return os.path.join(resources_dirname, filename)

def check_latest(storage, filename):
    timestamp = ResourceTimestamp(filename)

    latest_timestamp = storage.get_resource_timestamp(filename)
    if latest_timestamp is None:
        return False
    
    local_timestamp = timestamp.get_timestamp()

    if local_timestamp == latest_timestamp:
        return False
    
    filepath = os.path.join(resources_dirname, filename)
    if storage.download_resource(filename, filepath):
        timestamp.write_timestamp(latest_timestamp)
        return True

masks = {}
for filename in os.listdir(masks_dirpath):
    key = filename.split('.')[0]
    filepath = os.path.join(masks_dirpath, filename)
    masks[key] = Mask(key, np.load(filepath))
