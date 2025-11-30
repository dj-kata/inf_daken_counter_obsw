import numpy as np
from winsound import SND_FILENAME,PlaySound
from logging import getLogger
import pickle
from os import rename,remove
from os.path import join,isfile,exists
from PIL import Image

logger_child_name = 'resources'

logger = getLogger().getChild(logger_child_name)
logger.debug(f'loaded resources.py')

from define import define

resources_dirname = 'resources'

sounds_dirname = 'sounds'
images_dirname = 'images'

sounds_dirpath = join(resources_dirname, sounds_dirname)
images_dirpath = join(resources_dirname, images_dirname)

sound_result_filepath = join(sounds_dirpath, 'result.wav')

images_resourcecheck_filepath = join(images_dirpath, 'resourcecheck.png')
images_summaryprocessing_filepath = join(images_dirpath, 'summaryprocessing.png')
images_imagenothing_filepath = join(images_dirpath, 'imagenothing.png')
images_graphnogenerate_filepath = join(images_dirpath, 'graphnogenerate.png')
images_loading_filepath = join(images_dirpath, 'loading.png')
images_stamp_filepath = join(images_dirpath, 'stamp.png')

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
        self.load_resource_notesradar()

        self.imagevalue_musictableinformation = None

        self.image_stamp = Image.open(images_stamp_filepath)
    
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
    
    def load_resource_notesradar(self):
        resourcename = f'notesradar{define.notesradar_version}'
        
        self.notesradar: dict[str, dict[str, list[dict[str, str | int]]]] = load_resource_serialized(resourcename)

class ResourceTimestamp():
    def __init__(self, resourcename):
        self.resourcename = resourcename
        self.filepath = join(resources_dirname, f'{resourcename}.timestamp')
    
    def get_timestamp(self):
        if not exists(self.filepath):
            return None
        with open(self.filepath, 'r') as f:
            timestamp = f.read()

        return timestamp

    def write_timestamp(self, timestamp):
        logger.info(f'Update timestamp {self.resourcename} {timestamp}')
        with open(self.filepath, 'w') as f:
            f.write(timestamp)

def play_sound_result():
    if exists(sound_result_filepath):
        PlaySound(sound_result_filepath, SND_FILENAME)

def load_resource_serialized(resourcename: str) -> dict | None:
    '''リソースファイルをロードする

    もし一時ファイルが存在したら前回のダウンロードが失敗していたということなので、
    対象のファイルを削除して一時ファイルを元に戻す。

    Args:
        resourcename(str): 対象のリソース名
    Returns:
        dict or None: ロードされたリソースデータ
    '''
    filepath = join(resources_dirname, f'{resourcename}.res')
    filepath_tmp = join(resources_dirname, f'{resourcename}.res.tmp')

    if exists(filepath_tmp):
        if exists(filepath):
            remove(filepath)
        rename(filepath_tmp, filepath)
    
    if not isfile(filepath):
        return None
    
    with open(filepath, 'rb') as f:
        value = pickle.load(f)
    
    return value

def load_resource_numpy(resourcename):
    filepath = join(resources_dirname, f'{resourcename}.npy')
    return np.load(filepath)

def get_resource_filepath(filename):
    return join(resources_dirname, filename)

def check_latest(storage, filename) -> bool:
    '''対象のリソースファイルが最新かどうかをチェックする

    ローカルファイルとGCS上のファイルのタイムスタンプを比較して異なればダウンロードを試みる。
    ダウンロード開始前に現在のファイルを一時ファイルとしてファイル名を変更する。
    ダウンロードに成功した場合は、一時ファイルを削除する。
    もしダウンロードに失敗した場合、一時ファイルに戻す。

    Args:
        storage(): 対象のストレージ
        filename(str): 対象のファイル名
    Returns:
        bool: リソースファイルが更新された
    '''
    latest_timestamp: str | None = storage.get_resource_timestamp(filename)
    if latest_timestamp is None:
        return False
    
    filepath = join(resources_dirname, filename)

    timestamp = ResourceTimestamp(filename)
    local_timestamp: str | None = None
    if exists(filepath):
        local_timestamp = timestamp.get_timestamp()

    if local_timestamp == latest_timestamp:
        return False
    
    filepath_tmp = f'{filepath}.tmp'
    if exists(filepath):
        rename(filepath, filepath_tmp)

    if storage.download_resource(filename, filepath):
        logger.info(f'Download {filename}')
        timestamp.write_timestamp(latest_timestamp)

        if exists(filepath_tmp):
            remove(filepath_tmp)

        return True
    else:
        if exists(filepath):
            remove(filepath)
        
        rename(filepath_tmp, filepath)

        return False

resource = Resource()
