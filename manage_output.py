#!/usr/bin/python3
# 出力ファイルの管理全般、将来的にxml出力も移したい
# まずは統計情報出力を実装するところから
import pickle
from collections import defaultdict
from daken_logger import DakenLogger
from lib_score_manager import ScoreManager
import datetime

import logging, logging.handlers
import traceback
import os
os.makedirs('log', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

class ManageStats:
    def __init__(self, date='????/??/??', todaylog=[], judge=[], plays=0, from_alllog=False, target_srate='80'):
        self.date = date
        self.todaylog = todaylog
        self.judge    = judge
        self.dakenlog = []
        tmp = DakenLogger()
        self.score_manager = ScoreManager()
        self.log_last5days = []
        self.dakenlog = tmp.log
        self.plays    = plays
        self.srate    = 0
        self.from_alllog = from_alllog
        self.target_srate = int(target_srate)
        if len(self.judge):
            if (self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5]) > 0:
                self.srate = (self.judge[0]*2+self.judge[1])/(self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5])*50

        self.lv_hist = defaultdict(lambda:0)
        self.sp      = defaultdict(lambda:0)
        self.dp      = defaultdict(lambda:0)
        self.dbx     = defaultdict(lambda:0)
        # 後回ししてるけど、一応DBMとかのカウンタも用意
        self.lv_dbm  =defaultdict(lambda:0)
        self.lv_dbr  =defaultdict(lambda:0)
        self.lv_dbsr =defaultdict(lambda:0)
        self.lv_db   =defaultdict(lambda:0)

        self.lv_dbm_with_scratch  =defaultdict(lambda:0)
        self.lv_dbr_with_scratch  =defaultdict(lambda:0)
        self.lv_dbsr_with_scratch =defaultdict(lambda:0)
        self.lv_db_with_scratch   =defaultdict(lambda:0)
        self.calc_lv_histogram()
        self.score_manager.load()
        self.stat_on_start = self.score_manager.stat_perlv.copy()

    def calc_lv_histogram(self):
        for s in self.todaylog:
            if s[9] != None: # スコアが存在
                self.lv_hist[s[0]] += s[9]
                if 'SP' in s[2]:
                    self.sp[s[0]] += s[9]
                else:
                    if 'BATTLE' in s[-2]:
                        self.dbx[s[0]] += s[9]
                    else:
                        self.dp[s[0]] += s[9]

    def get_notes_last5days_from_alllog(self):
        with open('alllog.pkl', 'rb') as f:
            alllog = pickle.load(f)
        #logger.debug(alllog)
        tmp = []
        dates = []
        tmp_date = list(map(int, alllog[-1][-1].split('-')))
        self.date = f"{tmp_date[0]:02d}/{tmp_date[1]:02d}/{tmp_date[2]:02d}"
        today = datetime.date(tmp_date[0], tmp_date[1], tmp_date[2])
        logger.debug(f'today={today}, self.date={self.date}')
        for i in reversed(range(5)): # 先に[日付,0,0,0,0,0,0,0]として初期化
            date = today - datetime.timedelta(days=i)
            dates.append(date)
            tmp.append([date.strftime('%Y/%m/%d'), 0, 0, 0, 0, 0, 0, 0])
        logger.debug(f'tmp={tmp}')

        for l in reversed(alllog):
            tmp_date = list(map(int, l[-1].split('-')))
            tmp_day = datetime.date(tmp_date[0], tmp_date[1], tmp_date[2])
            if tmp_day in dates:
                tmp[dates.index(tmp_day)][2] += (l[9]*self.target_srate)//100
            else:
                break
        self.log_last5days = tmp
        logger.debug(f'tmp={tmp}')
        

    def get_notes_last5days(self):
        tmp_date = list(map(int, self.date.split('/')))
        today = datetime.date(tmp_date[0], tmp_date[1], tmp_date[2])
        tmp = []

        for i in reversed(range(1,5)): # 先に[日付,0,0,0,0,0,0,0]として初期化
            date = today - datetime.timedelta(days=i)
            tmp.append([date.strftime('%Y/%m/%d'), 0, 0, 0, 0, 0, 0, 0])
        tmp.append([today.strftime('%Y/%m/%d')])
        tmp[-1].append(self.plays)
        for notes in self.judge: # 今日の判定分を出力配列に追加
            tmp[-1].append(notes)

        for d in reversed(self.dakenlog):
            tmp_date = list(map(int, d[0].split('/')))
            date = datetime.date(tmp_date[0], tmp_date[1], tmp_date[2])
            idx = 4 - (today-date).days
            if (today-date).days < 5:
                for i, notes in enumerate(d[1:]):
                    tmp[idx][i+1] += notes
            else:
                break
        self.log_last5days = tmp
        logger.debug(tmp)

    def update(self, todaylog, judge, plays):
        # TODO リザルト画面に来るたびに実行するが、差分実行にできないか？
        self.lv_hist    = defaultdict(lambda:0)
        self.sp         = defaultdict(lambda:0)
        self.dp         = defaultdict(lambda:0)
        self.dbx        = defaultdict(lambda:0)
        self.todaylog   = todaylog
        self.judge      = judge
        self.plays      = plays
        if len(self.judge):
            if (self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5]) > 0:
                self.srate = (self.judge[0]*2+self.judge[1])/(self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5])*50
        self.calc_lv_histogram()
        try:
            if self.from_alllog:
                self.get_notes_last5days_from_alllog()
            else:
                self.get_notes_last5days()
        except Exception:
            logger.debug(traceback.format_exc())
            #self.get_notes_last5days_from_alllog()
        self.score_manager.load()

    def disp(self):
        for i in range(1,13):
            print(f"☆{i}: {self.lv_hist[str(i)]}")

    def write_stats_to_xml(self):
        with open('stats.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Items>\n")
            f.write(f"    <playdate>{self.date}</playdate>\n")
            f.write(f"    <plays>{self.plays}</plays>\n")
            f.write(f"    <score_rate>{self.srate:.1f}</score_rate>\n")

            f.write(f"    <PerLv>\n")
            for i in range(1,13):
                f.write(f"        <Lv>\n")
                f.write(f"            <difficulty>{i}</difficulty>\n")
                f.write(f"            <total>{self.lv_hist[str(i)]}</total>\n")
                f.write(f"            <sp>{self.sp[str(i)]}</sp>\n")
                f.write(f"            <dp>{self.dp[str(i)]}</dp>\n")
                f.write(f"            <dbx>{self.dbx[str(i)]}</dbx>\n")
                f.write(f"        </Lv>\n")

            f.write(f"    </PerLv>\n\n")

            f.write(f"    <Notes>\n")
            for tmp in self.log_last5days:
                f.write(f"        <day>\n")
                f.write(f"            <date>{tmp[0][-5:]}</date>\n")
                f.write(f"            <pg>{tmp[2]}</pg>\n")
                f.write(f"            <gr>{tmp[3]}</gr>\n")
                f.write(f"            <gd>{tmp[4]}</gd>\n")
                f.write(f"        </day>\n")
            f.write(f"    </Notes>\n")

            d = self.score_manager.stat_perlv
            f.write(f"    <Stats>\n")
            for k in d.keys():
                stat_lamp  = d[k][0]
                stat_score = d[k][1]
                f.write(f"        <lv>\n")
                f.write(f"            <difficulty>{k.lower()}</difficulty>\n")
                for ii, val in enumerate(('noplay', 'failed', 'assist', 'easy', 'clear', 'hard', 'exh', 'fc')):
                    f.write(f"            <{val}>{stat_lamp[ii]}</{val}>\n")
                for ii, val in enumerate(('under_b', 'a', 'aa', 'aaa', 'max_minus', 'max')):
                    f.write(f"            <{val}>{stat_score[ii]}</{val}>\n")
                # 本日の更新分の埋め込み
                pre_lamp = self.stat_on_start[k][0]
                pre_score = self.stat_on_start[k][1]
                for ii, val in enumerate(('noplay', 'failed', 'assist', 'easy', 'clear', 'hard', 'exh', 'fc')):
                    if stat_lamp[ii] == pre_lamp[ii]:
                        f.write(f"            <{val}_diff>0</{val}_diff>\n")
                    else:
                        f.write(f"            <{val}_diff>{stat_lamp[ii]-pre_lamp[ii]:+}</{val}_diff>\n")
                for ii, val in enumerate(('under_b', 'a', 'aa', 'aaa', 'max_minus', 'max')):
                    if stat_score[ii] == pre_score[ii]:
                        f.write(f"            <{val}_diff>0</{val}_diff>\n")
                    else:
                        f.write(f"            <{val}_diff>{stat_score[ii]-pre_score[ii]:+}</{val}_diff>\n")
                f.write(f"        </lv>\n")
            f.write(f"    </Stats>\n")

            f.write("</Items>\n")

if __name__ == "__main__":

    with open('debug/oneday.pkl', 'rb') as f:
        sample_data = pickle.load(f)

    a = ManageStats(date="2023/05/28", todaylog=sample_data, plays=38, judge=[25258,7399,2816,332,970,759])
    a.disp()
    a.write_stats_to_xml()
    a.get_notes_last5days()