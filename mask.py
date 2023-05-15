import numpy as np
from logging import getLogger

logger_child_name = 'mask'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded mask.py')

class Mask():
    def __init__(self, key, value):
        self.key = key
        self.value = value
    
    def eval(self, target):
        if not hasattr(self, 'value'):
            return False

        if np.all((self.value==0)|(target==self.value)):
            return True
        else:
            return False
