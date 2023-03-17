#!/usr/bin/python3
import obsws_python as obsws
#import base64
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
        self.active = True
        self.ev = obsws.EventClient(host=self.host,port=self.port,password=self.passwd)
        self.ev.callback.register([self.on_exit_started,])

    def close(self):
        del self.ws

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

    def on_exit_started(self, _):
        print("OBS closing!")
        self.active = False
        self.ev.unsubscribe()

if __name__ == "__main__":
    a = OBSSocket('localhost', 4455, 'panipaninoakuma','INFINITAS','')
    #a.save_screenshot('メインモニタ', 'png', 'C:\\Users\\katao\\OneDrive\\デスクトップ\\hoge.png')
    #tmp = a.get_screenshot('メインモニタ', 'png')
#    a.change_scene('pksv_battle_end')
#    a.change_text('txtTest', 'unko')
    