#!/usr/bin/python3
import obsws_python as obsws
import cv2, base64
import numpy as np
from PIL import Image

class OBSSocket():
    def __init__(self,hostIP,portNum,passWord,inf_source,dst_screenshot):
        self.host = hostIP
        self.port = portNum
        self.passwd = passWord
        self.inf_source = inf_source
        self.dst_screenshot = dst_screenshot
        self.ws = obsws.ReqClient(host=self.host,port=self.port,password=self.passwd)

    def change_scene(self,name:str):
        self.ws.set_current_program_scene(name)

    def get_scenes(self):
        res = self.ws.get_scene_list()
        print(res.scenes)

    def change_text(self, source, text):
        res = self.ws.set_input_settings(source, {'text':text}, True)

    def save_screenshot(self):
        res = self.ws.save_source_screenshot(self.inf_source, 'png', self.dst_screenshot, 1280, 720, 100)

    def save_screenshot_dst(self, dst):
        res = self.ws.save_source_screenshot(self.inf_source, 'png', dst, 1280, 720, 100)

    def get_screenshot(self, source, fmt):
        res = self.ws.get_source_screenshot(source, fmt, 1920, 1080, 100)
        scr = res.image_data
        #img = cv2.imdecode(np.frombuffer(bytes(res.image_data, 'utf-8'), dtype='uint8'), cv2.IMREAD_UNCHANGED)
        #img = Image.open(res.image_data)
        #binary = base64.b64decode(res.image_data + "="*(-len(res.image_data) % 4))
        #png = np.frombuffer(binary, dtype=np.uint8)
        #img = cv2.imdecode(png, cv2.IMREAD_COLOR)
        #return img
        return scr

if __name__ == "__main__":
    a = OBSSocket('localhost', 4455, 'panipaninoakuma')
    a.save_screenshot('メインモニタ', 'png', 'C:\\Users\\katao\\OneDrive\\デスクトップ\\hoge.png')
    #tmp = a.get_screenshot('メインモニタ', 'png')
#    a.change_scene('pksv_battle_end')
#    a.change_text('txtTest', 'unko')
    