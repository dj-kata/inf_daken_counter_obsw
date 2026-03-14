import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob

from src.screen_reader import ScreenReader
from src.logger import get_logger
from src.result import *
from src.result_database import ResultDatabase
from src.classes import *
from src.config import Config
from src.funcs import *
logger = get_logger('veri_result')

if __name__ == '__main__':
    logger.info('start')
    config = Config()
    # rdb = ResultDatabase(config = config)
    reader = ScreenReader()
    for f in glob.glob('debug/result/*.png'):
        # logger.info(f'file={f}')
        reader.update_screen_from_file(f)
        if reader.is_result():
            r = reader.read_result_screen()
            if r:
                # logger.info(f'[RESULT] {r}')
                r.result.timestamp = os.path.getmtime(f)
                print(r, r.result)
