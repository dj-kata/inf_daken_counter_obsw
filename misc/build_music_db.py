# wuv run python -m misc.build_music_dbで実行できる
import pickle
from src.songinfo import SongDatabase

with open("D:\\bin\\YouTubeLive\\inf_daken_counter\\resources\\musictable1.1.res", 'rb') as f:
    a = pickle.load(f)

print(a['levels']['SP']['12'])
print(a['versions'].keys())

b = SongDatabase()
