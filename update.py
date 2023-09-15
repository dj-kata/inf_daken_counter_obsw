import PySimpleGUI as sg
import os, re, sys
import urllib.request
from typing import Optional
import zipfile
import shutil
from glob import glob
from bs4 import BeautifulSoup
import urllib, requests
import threading
import logging, logging.handlers
import traceback

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    './dbg.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

sg.theme('SystemDefault1')
try:
    with open('version.txt', 'r') as f:
        SWVER = f.readline().strip()
except Exception:
    SWVER = "v0.0.0"

class Updater:
    def get_latest_version(self):
        self.ico=self.ico_path('icon.ico')
        ret = None
        url = 'https://github.com/dj-kata/inf_daken_counter_obsw/tags'
        r = requests.get(url)
        soup = BeautifulSoup(r.text,features="html.parser")
        for tag in soup.find_all('a'):
            if 'releases/tag/v.' in tag['href']:
                ret = tag['href'].split('/')[-1]
                break # 1番上が最新なので即break
        return ret

    def update_from_url(self, url):
        filename = 'tmp/tmp.zip'
        self.window['txt_info'].update('ファイルDL中')

        def _progress(block_count: int, block_size: int, total_size: int):
            percent = int((block_size*block_count*100)/total_size)
            self.window['prog'].update(percent)

        # zipファイルのDL
        logger.debug('now downloading...')
        os.makedirs('tmp', exist_ok=True)
        urllib.request.urlretrieve(url, filename, _progress)

        # zipファイルの解凍
        logger.debug('now extracting...')
        self.window['txt_info'].update('zipファイル解凍中')
        shutil.unpack_archive(filename, 'tmp')

        zp = zipfile.ZipFile(filename, 'r')

        target_dir = '.'
        logger.debug('now moving...')
        for query in ('*', '*/*', '*/*/*'):
            for f in glob('tmp/inf_daken_counter/'+query):
                if os.path.isfile(f):
                    try:
                        base = re.sub('.*inf_daken_counter.', '', f)
                        shutil.move(f, target_dir+'/'+base)
                        logger.debug(f'{f} -> {target_dir}/{base}')
                    except:
                        logger.debug(f"error! ({f})")
                        logger.debug(traceback.format_exc())
        shutil.rmtree('tmp/inf_daken_counter')
        self.window.write_event_value('-FINISH-', '')

    # icon用
    def ico_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def gui(self):
        layout = [
            [sg.Text('', key='txt_info')],
            [sg.ProgressBar(100, key='prog', size=(30, 15))],
        ]
        self.window = sg.Window('infdc update manager', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico)

    def main(self, url):
        self.gui()
        th = threading.Thread(target=self.update_from_url, args=(url,), daemon=True)
        th.start()
        while True:
            ev,val = self.window.read()
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-'):
                value = sg.popup_yes_no(f'アップデートをキャンセルしますか？', icon=self.ico)
                if value == 'Yes':
                    break
            elif ev == '-FINISH-':
                sg.popup_ok('アップデート完了！', icon=self.ico)
                break

if __name__ == '__main__':
    app = Updater()
    ver = app.get_latest_version()
    url = f'https://github.com/dj-kata/inf_daken_counter_obsw/releases/download/{ver}/inf_daken_counter.zip'
    if re.findall('\d+', SWVER) == re.findall('\d+', ver):
        print('最新版がインストールされています。')
        sg.popup_ok('最新版がインストールされています。',icon=app.ico)
    else:
        value = sg.popup_ok_cancel(f'利用可能なアップデートがあります。\n\n{SWVER} -> {ver}\n\n更新しますか？',icon=app.ico)
        if value == 'OK':
            app.main(url)

