import pickle
from src.screen_reader import ScreenReader
from src.logger import get_logger
from src.result import *
from src.result_database import ResultDatabase
from src.classes import *
from src.config import Config
from src.funcs import *
with open('alllog.pkl', 'rb') as f:
    a = pickle.load(f)

print(len(a))
rdb = ResultDatabase()
key = 'Lords Of The Roundtable'
key = 'Timepiece phase II (CN Ver.)'
key = 'True Blue'
# for r in rdb.search(key, play_style.dp, difficulty.another):
    # print(r)

best = rdb.get_all_best_results()
# print(best[(key, play_style.sp, difficulty.another, None)])
# print(rdb)
reader = ScreenReader()
#reader.update_screen_from_file('debug/inf_The end of my spiritually_SPA_FAILED_ex8_20251130_234832.png')
# reader.update_screen_from_file('pic/inf_Rosa azuL_SPA_assist_ex2340_bp3_20260210_011234.png')
# r = reader.read_result_screen()
# print(r.result.__dict__)

# a = rdb.write_bpi_csv(play_style.sp)
# print(rdb.get_monthly_notes())
titles = []
for line in a:
    titles.append(line[1])
    # if key == line[1]:
        # print(line)

# with open('alllog.pkl', 'wb') as f:
    # pickle.dump(modify, f)


# for r in rdb.search(title=key, style=play_style.dp, difficulty=difficulty.another):
    # print(r)

rdb.results[-1].detect_mode = detect_mode.result
# print(rdb.get_best(title=key, style=play_style.dp, difficulty=difficulty.another))

# a = rdb.get_best_all_charts()