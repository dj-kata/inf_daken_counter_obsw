import ctypes
from ctypes import windll,wintypes,create_string_buffer
from datetime import datetime
from PIL import Image
from logging import getLogger
from os.path import exists,basename
import numpy as np

logger_child_name = 'screenshot'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded screenshot.py')

from define import define
from resources import load_resource_serialized

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
PW_CLIENTONLY = 1

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]

class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ('rgbRed', ctypes.c_byte),
        ('rgbGreen', ctypes.c_byte),
        ('rgbBlue', ctypes.c_byte),
        ('rgbReserved', ctypes.c_byte),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', ctypes.POINTER(RGBQUAD))
    ]

class Screen:
    def __init__(self, np_value, filename):
        self.np_value = np_value

        self.original = Image.fromarray(np_value)
        self.filename = filename

class Capture:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.bmi = BITMAPINFO()
        self.bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bmi.bmiHeader.biWidth = self.width
        self.bmi.bmiHeader.biHeight = self.height
        self.bmi.bmiHeader.biPlanes = 1
        self.bmi.bmiHeader.biBitCount = 24
        self.bmi.bmiHeader.biCompression = 0
        self.bmi.bmiHeader.biSizeImage = 0

        self.screen = windll.gdi32.CreateDCW("DISPLAY", None, None, None)
        self.screen_copy = windll.gdi32.CreateCompatibleDC(self.screen)
        self.bitmap = windll.gdi32.CreateCompatibleBitmap(self.screen, self.width, self.height)

        windll.gdi32.SelectObject(self.screen_copy, self.bitmap)

        self.buffer = create_string_buffer(self.height * self.width * 3)
    
    def shot(self, left, top):
        windll.gdi32.BitBlt(self.screen_copy, 0, 0, self.width, self.height, self.screen, left, top, SRCCOPY)
        windll.gdi32.GetDIBits(self.screen_copy, self.bitmap, 0, self.height, ctypes.pointer(self.buffer), ctypes.pointer(self.bmi), DIB_RGB_COLORS)

        return np.array(bytearray(self.buffer)).reshape(self.height, self.width, 3)

    def __del__(self):
        windll.gdi32.DeleteObject(self.bitmap)
        windll.gdi32.DeleteDC(self.screen_copy)
        windll.gdi32.DeleteDC(self.screen)

        logger.debug('Called Screenshot destuctor.')

class Screenshot:
    xy = None
    screentable = load_resource_serialized('get_screen')
    np_value = None

    def __init__(self):
        self.checkloading = Capture(define.get_screen_area['width'], define.get_screen_area['height'])
        self.capture = Capture(define.width, define.height)

    def __del__(self):
        del self.checkloading
        del self.capture

    def get_screen(self):
        if self.xy is None:
            return None
        
        x = self.xy[0] + define.get_screen_area['left']
        y = self.xy[1] + define.get_screen_area['top']
        np_value = self.checkloading.shot(x, y)
        key = np.sum(np_value)

        if not key:
            return 'black'

        if key in self.screentable.keys():
            return self.screentable[key]

        return None

    def shot(self):
        if self.xy is None:
            return False
        
        self.np_value = self.capture.shot(self.xy[0], self.xy[1])[::-1, :, ::-1]
        return True

    def get_image(self):
        if self.np_value is None:
            return None
        
        return Image.fromarray(self.np_value)

    def get_resultscreen(self):
        now = datetime.now()
        filename = f"{now.strftime('%Y%m%d-%H%M%S-%f')}.png"

        return Screen(self.np_value, filename)

def open_screenimage(filepath):
    if not exists(filepath):
        return None
    
    image = Image.open(filepath).convert('RGB')
    filename = basename(filepath)

    return Screen(np.array(image), filename)
