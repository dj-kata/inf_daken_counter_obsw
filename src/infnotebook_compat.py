"""infnotebookのバージョン差分を吸収する小さな互換レイヤー"""

from pathlib import Path
import sys

import numpy as np
from PIL import Image

sys.path.append('infnotebook')

try:
    from capture import Screen
except ImportError:
    Screen = None


def open_screenimage(filepath: str):
    """旧infnotebook.screenshot.open_screenimage相当のScreenを作る"""
    if Screen is None:
        raise ImportError('infnotebook capture.Screen is not available')

    image = Image.open(filepath).convert('RGB')
    return Screen(np.array(image), Path(filepath).name)


class Screenshot:
    """旧API互換用のダミー。現状本アプリでは直接使用しない。"""

    pass
