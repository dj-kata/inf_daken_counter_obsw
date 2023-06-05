# スコア管理部
# GUI機能も有しており、本ソース単体でも動作する
import pickle
import datetime
import json
import csv
import sys, os
from collections import defaultdict
import PySimpleGUI as sg
from tkinter import filedialog

class ScoreManager:
    def __init__(self):
        # 全ての認識結果ログ
        self.log = []
        # keyを曲名___譜面とした全ログdict
        self.score = defaultdict(lambda: list())
        # keyを曲名___譜面とした自己べのdict。DBx系は___DBAみたいな付け方とする。
        self.score_best = defaultdict(lambda: list())
        # 難易度ごとの曲名一覧
        self.list_diff = defaultdict(lambda: list())
        # ノーツ数一覧
        with open('noteslist.pkl', 'rb') as f:
            self.noteslist = pickle.load(f)
        self.load()
        self.difflist = ['SPB', 'SPN', 'SPH', 'SPA', 'DPN', 'DPH', 'DPA']
        self.get_scores_from_log()
        self.get_scores_best()
        self.get_musiclist_with_difficulty()

    def load(self):
        with open('alllog.pkl', 'rb') as f:
            self.log = pickle.load(f)

    # 曲___譜面をkeyとし、全プレーログを保存したdictの作成
    def get_scores_from_log(self):
        for s in self.log:
            key = f"{s[1]}___{s[2]}"
            notes = self.noteslist[s[1]][self.difflist.index(s[2])]
            if 'BATTLE' in s[-2]:
                notes = 2 * self.noteslist[s[1]][self.difflist.index(s[2].replace('DP','SP'))]
            if s[3] == notes:
                self.score[key].append(s)
            else:
                print(f'error! ノーツ数が不一致 ({s}), notes={notes}')
            #if 'GAMBOL' in key:
            #    print(s)

    def get_scores_best(self):
        lamp_table = ['NO PLAY', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO']
        for key in self.score.keys():
            # ランプ、スコア、BP、notes, best_opt_score, best_opt_bp、最終プレー日
            best_reg = ['NO PLAY', 0, 9999, 0, '?', '?', '2000-01-01'] 
            best_dbx = ['NO PLAY', 0, 9999, 0, '?', '?', '2000-01-01'] 
            for s in self.score[key]: # その曲の全ログを確認
                tmp = list(map(int, s[-1].split('-')))
                date_cur = datetime.date(tmp[0], tmp[1], tmp[2])
                if 'BATTLE' in s[-2]:
                    tmp = list(map(int, best_dbx[-1].split('-')))
                    date_best = datetime.date(tmp[0], tmp[1], tmp[2])
                    if date_cur > date_best:
                        best_dbx[-1] = s[-1]
                    if s[9] != None:
                        if best_dbx[1] < s[9]: # スコア
                            best_dbx[1] = s[9]
                            best_dbx[4] = s[-2]
                            best_dbx[3] = s[3]
                    if s[11] != None:
                        if best_dbx[2] > s[11]: # bp
                            best_dbx[2] = s[11]
                            best_dbx[5] = s[-2]
                    if s[7] != None:
                        if lamp_table.index(best_dbx[0]) < lamp_table.index(s[7]):
                            best_dbx[0] = s[7]
                else:
                    tmp = list(map(int, best_reg[-1].split('-')))
                    date_best = datetime.date(tmp[0], tmp[1], tmp[2])
                    if date_cur > date_best:
                        best_reg[-1] = s[-1]
                    if s[9] != None:
                        if best_reg[1] < s[9]: # スコア
                            best_reg[1] = s[9]
                            best_reg[4] = s[-2]
                            best_reg[3] = s[3]
                    if s[11] != None:
                        if best_reg[2] > s[11]: # bp
                            best_reg[2] = s[11]
                            best_reg[5] = s[-2]
                    if s[7] != None:
                        if lamp_table.index(best_reg[0]) < lamp_table.index(s[7]):
                            best_reg[0] = s[7]
            # 2ループ目: リザルトは残っていないが自己べのほうが高いものを検出(ルーチンがゴチャ付きそうなので一応分ける)
            for s in self.score[key]: # その曲の全ログを確認
                if 'BATTLE' in s[-2]:
                    if s[8] != None:
                        if best_dbx[1] < s[8]: # スコア
                            best_dbx[1] = s[8]
                            best_dbx[4] = '?'
                            best_dbx[3] = s[3]
                    if s[10] != None:
                        if best_dbx[2] > s[10]: # bp
                            best_dbx[2] = s[10]
                            best_dbx[5] = '?'
                    if s[6] != None:
                        if lamp_table.index(best_dbx[0]) < lamp_table.index(s[6]):
                            best_dbx[0] = s[6]
                else:
                    if s[8] != None:
                        if best_reg[1] < s[8]: # スコア
                            best_reg[1] = s[8]
                            best_reg[4] = '?'
                            best_reg[3] = s[3]
                    if s[10] != None:
                        if best_reg[2] > s[10]: # bp
                            best_reg[2] = s[10]
                            best_reg[5] = '?'
                    if s[6] != None:
                        if lamp_table.index(best_reg[0]) < lamp_table.index(s[6]):
                            best_reg[0] = s[6]
            if best_reg[1] > 0:
                self.score_best[key]=best_reg
            if best_dbx[2] < 9999: # DBx系はbpが残っていれば登録
                key_dbx = key[:-2] + 'B' + key[-1]
                self.score_best[key_dbx]=best_dbx
                #print('dbx added ===> 'key_dbx, best_dbx)

    # 難易度ごとの曲リストを取得
    def get_musiclist_with_difficulty(self):
        for k in self.score.keys():
            for song in self.score[k]:
                val = k
                if 'BATTLE' in song[-2]:
                    key = song[2][0]+'B'+song[0]
                    val = k[:-2]+'B'+k[-1]
                else:
                    key = song[2][:2]+song[0]
                self.list_diff[key].append(val)
                self.list_diff[key] = list(set(self.list_diff[key]))
        # ソート
        for k in self.list_diff.keys():
            self.list_diff[k] = sorted(sorted(self.list_diff[k]), key=str.lower)

    def disp_stat(self):
        for k in self.score.keys():
            tmp = len(self.score[k])
            if tmp>10:
                print(tmp, k)

    def disp_all_log(self):
        for d in self.log:
            print(f"{d[-1]}, {d}")

    def get_diff_best(self, diff):
        ret = []
        if diff in self.list_diff:
            for s in self.list_diff[diff]:
                if s in self.score_best.keys():
                    tmp = self.score_best[s]
                    info = [s[:-6], s[-3:]]
                    ret.append(info+tmp)
        return ret
    
    def disp_diff_best(self, diff):
        tmp = self.get_diff_best(diff)
        for s in tmp:
            x = '\t'.join([str(i) for i in s])
            print(x)

class ScoreViewer:
    def __init__(self):
        self.score_manager = ScoreManager()
        #with open('settings.json') as f:
        #    self.settings = json.load(f)

    def ico_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    
    def export_csv(self):
        savedir = filedialog.askdirectory()
        ret = []
        if savedir != '':
            for mode in ('SP', 'DP', 'DB'):
                for lv in range(1, 13):
                    lvlist = self.score_manager.get_diff_best(f"{mode}{lv}")
                    for tmp in lvlist:
                        # tmpの形式:get_diff_scores_bestの形式なのでここで整形しておく
                        tmp.insert(0, f'☆{lv}')
                        if tmp[5] == 9999:
                            tmp[5] = ''
                        # score, bp, notesの順なので、これをscore, score_rate, bpに書き換える
                        bp = tmp[5]
                        tmp[5] = f"{tmp[4]*100/(tmp[6]*2):.1f}"
                        tmp[6] = bp
                        date = tmp[-1].split('-')
                        tmp[-1] = f"{date[0]}/{date[1]}/{date[2]} {date[3]}:{date[4]}"
                        ret.append(tmp)
            outfile = f'{savedir}/inf_score.csv'
            try:
                with open(outfile, 'w') as f:
                    w = csv.writer(f, lineterminator="\n")
                    w.writerow(['LV', 'Title', 'mode', 'Lamp', 'Score', '(rate)', 'BP', 'Opt(best score)', 'Opt(min bp)', 'Last Played'])
                    for s in ret:
                        w.writerow(s)
                sg.popup(f'CSVエクスポート完了.\n --> {outfile}')
            except Exception as e:
                sg.popup(f'error!!\n{e}')
    
    def gui(self):
        sg.theme('SystemDefault')
        header = ['LV', 'Title', 'mode', 'Lamp', 'Score', '(rate)', 'BP', 'Opt(best score)', 'Opt(min bp)', 'Last Played']
        layout_mode = []
        for mode in ('sp', 'dp', 'dbx'):
            layout_mode.append(sg.Radio(mode.upper(), key=f"radio_mode_{mode}", group_id="mode", default=mode=='sp', enable_events=True))
        layout_lv = [sg.Checkbox('ALL', key='chk_lvall', enable_events=True, default=True)]
        for i in range(1, 13):
            layout_lv.append(sg.Checkbox(f'☆{i}', key=f"chk_lv{i}", enable_events=True, default=True))
        layout = [
            layout_mode,
            layout_lv,
            [sg.Text('search:'), sg.Input('', key='txt_search', enable_events=True), sg.Button('CSVにエクスポート', key='btn_export', enable_events=True, tooltip='プレーデータをcsvに保存します。\nSP/DP/DoubleBattleのデータを全て1ファイルに書き出します。')],
            [sg.Table([], key='table', headings=header
                      , font=(None, 16)
                      , vertical_scroll_only=False
                      , auto_size_columns=False
                      , col_widths=[4, 40, 4, 10, 5, 5, 5, 20, 20, 14]
                      ,background_color='#ffffff'
                      ,alternating_row_color='#eeeeee'
                      , justification='left', size=(1,10))
            ],
        ]
        ico=self.ico_path('icon.ico')
        self.window = sg.Window("INFINITAS Score Viewer", layout, resizable=True, return_keyboard_events=True, finalize=True, enable_close_attempted_event=True, icon=ico, size=(800,600))
        self.window['table'].expand(expand_x=True, expand_y=True)
        self.update_table()

    def update_table(self):
        mode = 'SP'
        if self.window['radio_mode_dp'].get():
            mode = 'DP'
        elif self.window['radio_mode_dbx'].get():
            mode = 'DB'
        dat = []
        for i in range(1, 13):
            if self.window[f"chk_lv{i}"].get():
                lvs = self.score_manager.get_diff_best(f"{mode}{i}")
                for tmp in lvs:
                    # tmpの形式:get_diff_scores_bestの形式なのでここで整形しておく
                    tmp.insert(0, f'☆{i}')
                    if tmp[5] == 9999:
                        tmp[5] = ''
                    # score, bp, notesの順なので、これをscore, score_rate, bpに書き換える
                    bp = tmp[5]
                    tmp[5] = f"{tmp[4]*100/(tmp[6]*2):.1f}"
                    tmp[6] = bp
                    date = tmp[-1].split('-')
                    tmp[-1] = f"{date[0]}/{date[1]}/{date[2]} {date[3]}:{date[4]}"
                    to_push = True
                    if self.window['txt_search'].get().strip() != '':
                        for search_word in self.window['txt_search'].get().strip().split(' '):
                            if search_word.lower() not in tmp[1].lower():
                                to_push = False
                    if to_push:
                        dat.append(tmp)
        self.window['table'].update(dat)


    def main(self):
        self.gui()

        while True:
            ev, val = self.window.read()
            print(ev, val)
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'btn_close_setting', 'btn_close_info'): # 終了処理
                break
            elif ev == 'chk_lvall': # ALLボタンの処理
                for i in range(1,13):
                    self.window[f"chk_lv{i}"].update(val['chk_lvall'])
            elif ev == 'btn_export':
                self.export_csv()
            self.update_table()

if __name__ == '__main__':
    c = ScoreManager()
    #b = c.disp_diff_best('DP12')

    a = ScoreViewer()
    a.main()

