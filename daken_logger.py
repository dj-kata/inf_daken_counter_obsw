#!/usr/bin/python3
import os, datetime, pickle
from matplotlib import pyplot as plt
import numpy as np

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

### 打鍵ログ(ノーツ数)保存用クラス
class DakenLogger:
    def __init__(self):
        self.log = []
        self.log_date = []
        self.load()

    def load(self):
        if not os.path.exists('./dakenlog.pkl'):
            with open('./dakenlog.pkl', 'wb') as f:
                pickle.dump(self.log, f)
        else:
            with open('./dakenlog.pkl', 'rb') as f:
                self.log = pickle.load(f)
        self.log_date = [self.log[i][0] for i in range(len(self.log))]

    def save(self):
        with open('./dakenlog.pkl', 'wb') as f:
            pickle.dump(self.log, f)

    def disp(self):
        for dd in self.log:
            print(f"{dd[0]} - plays:{dd[1]:,}, PG:{dd[2]:,}, GR:{dd[3]:,}, GD:{dd[4]:,}, BD:{dd[5]:,}, PR:{dd[6]:,}, CB:{dd[7]:,}")

    def add(self, date, plays, judge):
        tmp = [date, plays] + judge
        self.log.append(tmp)
        ### TODO dateが既に存在する場合の処理

    def delete(self, idx):
        self.log.pop(idx)
        self.log_date.pop(idx)

    # https://qiita.com/ZawaP/items/e959f7117b33fe5279ee
    def gradient_image(self, ax, direction=0.3, cmap_range=(0, 1), **kwargs):
        phi = direction * np.pi /100
        v = np.array([np.cos(phi), np.sin(phi)])
        X = np.array([[v @ [0.8, 0], v @ [1, 0.9]],
                      [v @ [0, 0], v @ [0, 1]]])
        a, b = cmap_range
        X = a + (b - a) / X.max() * X
        im = ax.imshow(X, interpolation='bicubic', clim=(0, 1), aspect='auto', **kwargs)
        return im

    def gradient_bar(self, ax, x, y, cmap, cmap_range=(0,1.0), width=0.5, bottom=0):
        for left, top in zip(x, y):
            right = left + width
            self.gradient_image(ax, extent=(left, right, bottom, top),
                           cmap=cmap, cmap_range=cmap_range)

    def gen_graph_core(self, filename, x, pg, gr, gd, write_sum=False):
        fig = plt.figure()
        fig.subplots_adjust(bottom=0.2)
        ax = fig.add_subplot(111)
        #fig, ax = plt.subplots()
        colors = ['#4444ff', '#ffdd44', '#22dd33']
        xxx=[i-0.25 for i in range(len(pg))]
        lim = ax.get_xlim()+ax.get_ylim()
        gr_gd = [gr[i]+gd[i] for i in range(len(pg))]
        total = [pg[i]+gr[i]+gd[i] for i in range(len(pg))]
        if len(total) > 0:
            ax.set_ylim([0, max(total)+5000]) # warning対策
            labels = ax.get_xticklabels()
            plt.setp(labels, rotation=90)

            # グラデーション
            self.gradient_bar(ax, xxx, total, plt.cm.winter, width=0.5, cmap_range=(0.3,1.2))
            self.gradient_bar(ax, xxx, gr_gd, plt.cm.Wistia, width=0.5, cmap_range=(-0.3, 0.7))
            self.gradient_bar(ax, xxx, gd, plt.cm.twilight_shifted, width=0.5, cmap_range=(0,0.2))

            #枠線, ax.textの都合上、bpgだけbottomなしでtotal(一番外側の矩形)を指定
            bgd = ax.bar(x, gd, color=colors[2], width=0.5, edgecolor='Black', linewidth=1, facecolor='none')
            bgr = ax.bar(x, gr, bottom=gd, color=colors[1], width=0.5, edgecolor='Black', linewidth=1, facecolor='none')
            bpg = ax.bar(x, total, color=colors[0], width=0.5, edgecolor='Black', linewidth=1, facecolor='none')
            # 棒グラフの上に合計値を表示
            if write_sum:
                for rect, t in zip(bpg, total):
                    h = rect.get_height()
                    if t>0:
                        ax.text(rect.get_x()+rect.get_width()/2, h+5, f"{t:,}", ha="center", va="bottom")
            # グラフの余白調整用、Xは-0.25～N-0.75、Y軸最大は適宜調整
            ax.bar([-0.25, len(pg)-0.75], [0, max(total)+5000], facecolor='none')
            #ax.legend(['PG', 'GR', 'GD'], loc='lower right', bbox_to_anchor=(1, 1), ncol=3)
            plt.savefig(filename)

    def gen_graph_with_date(self, filename, st, ed, write_sum=False):
        x  = []
        pg = []
        gr = []
        gd = []
        out = [0]*7 # plays, pg, gr, gd, bd, pr, cb, 

        for i in range((ed-st).days+1): 
            cur_date = st + datetime.timedelta(days=i)
            x.append(cur_date.strftime('%Y/%m/%d'))
            if cur_date.strftime('%Y/%m/%d') in self.log_date:
                idx = self.log_date.index(cur_date.strftime('%Y/%m/%d'))
                pg.append(self.log[idx][2])
                gr.append(self.log[idx][3])
                gd.append(self.log[idx][4])
                for i in range(7):
                    out[i] += self.log[idx][1+i]
            else:
                pg.append(0)
                gr.append(0)
                gd.append(0)
        self.gen_graph_core(filename, x, pg, gr, gd, write_sum)
        return out

            
if __name__ == "__main__":
    a = DakenLogger()
    a.disp()
    a.save()
    a.gen_graph_with_date('tmp.png', datetime.date(2023,4,1), datetime.date(2023,4,7))