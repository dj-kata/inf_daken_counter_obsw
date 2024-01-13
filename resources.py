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

resources_dirname = 'resources'

sounds_dirname = 'sounds'

sounds_dirpath = os.path.join(resources_dirname, sounds_dirname)

sound_result_filepath = os.path.join(sounds_dirpath, 'result.wav')

class Resource():
    def __init__(self):
        self.is_savable = load_resource_serialized('is_savable')
        self.play_side = load_resource_numpy('play_side')
        self.dead = load_resource_numpy('dead')
        self.rival = load_resource_numpy('rival')

        self.load_resource_informations()
        self.load_resource_details()
        self.load_resource_musictable()
        self.load_resource_musicselect()
    
    def load_resource_informations(self):
        resourcename = f'informations{define.informations_recognition_version}'
        
        self.informations = load_resource_serialized(resourcename)

    def load_resource_details(self):
        resourcename = f'details{define.details_recognition_version}'
        
        self.details = load_resource_serialized(resourcename)

    def load_resource_musictable(self):
        resourcename = f'musictable{define.musictable_version}'
        
        self.musictable = load_resource_serialized(resourcename)

    def load_resource_musicselect(self):
        resourcename = f'musicselect{define.musicselect_recognition_version}'
        
        self.musicselect = load_resource_serialized(resourcename)

class ResourceTimestamp():
    def __init__(self, resourcename):
        self.resourcename = resourcename
        self.filepath = os.path.join(resources_dirname, f'{resourcename}.timestamp')
    
    def get_timestamp(self):
        if not os.path.exists(self.filepath):
            return None
        with open(self.filepath, 'r') as f:
            timestamp = f.read()

        return timestamp

    def write_timestamp(self, timestamp):
        logger.info(f'Update timestamp {self.resourcename} {timestamp}')
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
        logger.info(f'Download {filename}')
        timestamp.write_timestamp(latest_timestamp)
        return True

resource = Resource()
