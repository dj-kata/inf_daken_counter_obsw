from src.config import *
from src.classes import *
from src.funcs import *
from src.obs_control import *
from src.songinfo import *
from src.screen_reader import *
from src.result import *

if __name__ == '__main__':
    reader = ScreenReader()
    config = Config()
    obs_manager = OBSWebSocketManager()
    obs_manager.set_config(config)
    obs_manager.connect()
    obs_manager.screenshot()
    reader.update_screen(obs_manager.screen)
    if reader.is_result():
        r = reader.read_result_screen()
        print(r)