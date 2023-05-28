#!/usr/bin/python3
# 出力ファイルの管理全般、将来的にxml出力も移したい
# まずは統計情報出力を実装するところから
import pickle
from collections import defaultdict
from daken_logger import DakenLogger
import datetime

class ManageStats:
    def __init__(self, date='????/??/??', todaylog=[], judge=[], plays=0):
        self.date = date
        self.todaylog = todaylog
        self.judge    = judge
        self.dakenlog = []
        tmp = DakenLogger()
        self.log_last5days = []
        self.dakenlog = tmp.log
        self.plays    = plays
        self.srate    = 0
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

    def update(self, todaylog, judge, plays):
        # TODO リザルト画面に来るたびに実行するが、差分実行にできないか？
        self.lv_hist = defaultdict(lambda:0)
        self.sp      = defaultdict(lambda:0)
        self.dp      = defaultdict(lambda:0)
        self.dbx     = defaultdict(lambda:0)
        self.todaylog = todaylog
        self.judge    = judge
        self.plays    = plays
        if len(self.judge):
            if (self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5]) > 0:
                self.srate = (self.judge[0]*2+self.judge[1])/(self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5])*50
        self.calc_lv_histogram()
        self.get_notes_last5days()

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

            f.write("</Items>\n")

if __name__ == "__main__":

    with open('debug/oneday.pkl', 'rb') as f:
        sample_data = pickle.load(f)

    a = ManageStats(date="2023/05/28", todaylog=sample_data, plays=38, judge=[25258,7399,2816,332,970,759])
    a.disp()
    a.write_stats_to_xml()
    a.get_notes_last5days()