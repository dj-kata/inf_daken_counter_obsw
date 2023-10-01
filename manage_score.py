# スコア管理部
# GUI機能も有しており、本ソース単体でも動作する
import pickle
import datetime
import json
import csv
import sys, os, math
from collections import defaultdict
import PySimpleGUI as sg
from tkinter import filedialog
from lib_score_manager import ScoreManager
import numpy as np

lamp_table = ['NO PLAY', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO']
class ScoreViewer:
    def __init__(self):
        self.score_manager = ScoreManager()
        self.mode = 'SP'
        self.flg_save = False
        #with open('settings.json') as f:
        #    self.settings = json.load(f)
        try:
            with open('dp_unofficial.pkl', 'rb') as f:
                self.dp_unofficial = pickle.load(f)
        except:
            self.dp_unofficial   = False
        try:
            with open('sp_12jiriki.pkl', 'rb') as f:
                self.sp_jiriki = pickle.load(f)
        except:
            self.sp_jiriki   = {}

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
        header = ['LV', 'Title', 'mode', 'Lamp', 'Score', '(rate)', 'BP', 'Opt(best score)', 'Opt(min bp)', 'Last Played', ' ']
        layout_mode = []
        for mode in ('sp', 'dp', 'dbx'):
            layout_mode.append(sg.Radio(mode.upper(), key=f"radio_mode_{mode}", group_id="mode", default=mode=='sp', enable_events=True))
        layout_lv = [sg.Checkbox('ALL', key='chk_lvall', enable_events=True, default=True)]
        for i in range(1, 13):
            layout_lv.append(sg.Checkbox(f'☆{i}', key=f"chk_lv{i}", enable_events=True, default=True))
        layout_sort = []
        layout_sort.append(sg.Radio('昇順', key='sort_ascend', group_id='sort_mode', default=True, enable_events=True))
        layout_sort.append(sg.Radio('降順', key='sort_descend', group_id='sort_mode', default=False, enable_events=True))
        layout_sort.append(sg.Text('ソート対象列:'))
        layout_sort.append(sg.Radio('曲名', key='sortkey_title', group_id='sortkey', default=True, enable_events=True))
        layout_sort.append(sg.Radio('クリアランプ', key='sortkey_lamp', group_id='sortkey', default=False, enable_events=True))
        layout_sort.append(sg.Radio('スコアレート', key='sortkey_srate', group_id='sortkey', default=False, enable_events=True))
        layout_sort.append(sg.Radio('BP', key='sortkey_bp', group_id='sortkey', default=False, enable_events=True))
        layout_sort.append(sg.Radio('最終プレー日', key='sortkey_date', group_id='sortkey', default=False, enable_events=True))
        layout_sort.append(sg.Radio('非公式難易度', key='sortkey_unofficial', group_id='sortkey', default=False, enable_events=True))
        layout_left = [
            layout_mode,
            layout_lv,
            layout_sort,
            [sg.Text('search:'), sg.Input('', key='txt_search', enable_events=True)
             ,sg.Button('クリア', key='clear')
             ,sg.Button('CSVにエクスポート', key='btn_export', enable_events=True, tooltip='プレーデータをcsvに保存します。\nSP/DP/DoubleBattleのデータを全て1ファイルに書き出します。')
             ,sg.Button('再読み込み', key='reload')
            ],
        ]
        layout_right = [
            [sg.Text('', key='txt_title')],
            [
                sg.Button('OBSで表示', key='disp_obs'),
                sg.Button('削除', key='delete'),
                sg.Button('保存', key='save'),
            ],
            [
                sg.Listbox([], size=(80,4), key='list_details')
            ]
        ]
        layout = [
            [sg.Column([
                [sg.Frame('filter', layout=layout_left),sg.Frame('details', layout=layout_right)],
            ])],
            [sg.Table([], key='table', headings=header
                      , font=(None, 16)
                      , vertical_scroll_only=False
                      , auto_size_columns=False
                      , col_widths=[4, 40, 4, 10, 5, 5, 5, 20, 20, 14, 4]
                      ,background_color='#ffffff'
                      ,alternating_row_color='#eeeeee'
                      , justification='left'
                      ,select_mode = sg.TABLE_SELECT_MODE_BROWSE
                      , size=(1,10)
                      ,enable_events=True
                    )
            ],
        ]
        ico=self.ico_path('icon.ico')
        self.window = sg.Window("INFINITAS Score Viewer", layout, resizable=True, return_keyboard_events=True, finalize=True, enable_close_attempted_event=True, icon=ico, size=(800,600))
        self.window['table'].expand(expand_x=True, expand_y=True)
        self.update_table()

    def gui_detals(self, rowdata):
        details = []
        for d in self.score_manager.score[rowdata[1]+"___"+rowdata[2]]:
            tmp = f"{d[13]}, {d[7]}, ex:{d[9]}, bp:{d[11]} opt:{d[12]}"
            details.append(tmp)
        self.window['list_details'].update(details)
        self.window['txt_title'].update(f"{rowdata[1]} (playcount:{len(self.score_manager.score[rowdata[1]+'___'+rowdata[2]])})")

    def delete_playdata(self, tabledata, detaildata):
        details = detaildata[0].split(', ')
        for i,d in enumerate(self.score_manager.log):
            flg_title = (d[1] == tabledata[1])
            flg_diff = (d[2][0] == tabledata[2][0]) and (d[2][2] == tabledata[2][2])
            flg_date  = (details[0] == d[13])
            flg_score = (d[9] == int(details[2][3:]))
            #flg_bp = (d[11] == int(details[3][4:])) # Noneになることがある
            if flg_title and flg_diff and flg_date and flg_score:
                print(i, d)
                self.score_manager.log.pop(i)
                self.score_manager.reload_tmp()
                self.gui_detals(tabledata)
                self.flg_save = True
                break # 1つだけ削除

    def escape_for_xml(self, input):
        return input.replace('&', '&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&apos;')

    # ノーツ数とスコアを受け取ってAAA+50みたいな表記にして返す。タプルで返す
    def calc_rankdiff(self, notes, score):
        target,diff = ('', '') # AAA, -50 みたいな結果を返す
        smax = notes*2
        if score == smax:
            target,diff = ('MAX', '+0')
        elif score >= math.ceil(17*smax/18):
            target,diff = ('MAX', f"{score-smax:+}")
        elif score >= math.ceil(15*smax/18):
            aaa = math.ceil(smax*16/18)
            target,diff = ('AAA', f'{score - aaa:+}')
        elif score >= math.ceil(13*smax/18):
            aa = math.ceil(smax*14/18)
            target,diff = ('AA', f'{score - aa:+}')
        elif score >= math.ceil(11*smax/18):
            a = math.ceil(smax*12/18)
            target,diff = ('A', f'{score - a:+}')
        elif score >= math.ceil(9*smax/18):
            tmp = math.ceil(smax*10/18)
            target,diff = ('B', f'{score - tmp:+}')
        elif score >= math.ceil(7*smax/18):
            tmp = math.ceil(smax*8/18)
            target,diff = ('C', f'{score - tmp:+}')
        elif score >= math.ceil(5*smax/18):
            tmp = math.ceil(smax*6/18)
            target,diff = ('D', f'{score - tmp:+}')
        elif score >= math.ceil(3*smax/18):
            tmp = math.ceil(smax*4/18)
            target,diff = ('E', f'{score - tmp:+}')
        else:
            target,diff = ('F', f'{score:+}')
        if diff == '-0':
            diff = '+0'

        return target,diff

    def write_history_cursong_xml(self, result):
        lv = result[0][1:]
        title = result[1]
        difficulty = result[2][0]+'P'+result[2][2]
        spjiriki_list = ['地力S+', '個人差S+', '地力S', '個人差S', '地力A+', '個人差A+', '地力A', '個人差A', '地力B+', '個人差B+', '地力B', '個人差B', '地力C', '個人差C', '地力D', '個人差D', '地力E', '個人差E', '地力F', '難易度未定']
        with open('history_cursong.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Results>\n")
            f.write(f'    <lv>{lv}</lv>\n')
            f.write(f'    <music>{self.escape_for_xml(result[1])}</music>\n')
            f.write(f'    <difficulty>{result[2]}</difficulty>\n')
            key = f"{title}({difficulty})"

            # 非公式難易度
            dpunoff_key = f"{result[1]}"
            dp_unofficial_lv = ''
            if dpunoff_key in self.dp_unofficial.keys():
                tmp = self.dp_unofficial[dpunoff_key]
                if result[2] == 'DPA':
                    dp_unofficial_lv = tmp[6]
                elif result[2] == 'DPH':
                    dp_unofficial_lv = tmp[5]
                elif result[2] == 'DPL':
                    dp_unofficial_lv = tmp[8]
            if 'BATTLE' in result[-2]:
                dp_unofficial_lv = ''
            f.write(f'    <dp_unofficial_lv>{dp_unofficial_lv}</dp_unofficial_lv>\n')
            # SP地力表
            spjiriki_key = f"{result[1]}___{result[2]}"
            sp_12hard = ''
            sp_12clear = ''
            if spjiriki_key in self.sp_jiriki['hard'].keys():
                sp_12hard = spjiriki_list[self.sp_jiriki['hard'][spjiriki_key]]
            if spjiriki_key in self.sp_jiriki['clear'].keys():
                sp_12clear = spjiriki_list[self.sp_jiriki['clear'][spjiriki_key]]
            f.write(f'    <sp_12hard>{sp_12hard}</sp_12hard>\n')
            f.write(f'    <sp_12clear>{sp_12clear}</sp_12clear>\n')
            best = ['NO PLAY', 0, 9999, '', '', '', '','','',0,'xxxx-xx-xx', 'xxxx-xx-xx', 'xxxx-xx-xx'] # lamp, score, bp, lamp-op,score-op,bp-op,lamp-date, score-date, bp-date
            for s in self.score_manager.score[f"{result[1]}___{result[2]}"]:
                if 'DB' in result[2]: # 現在DBx系オプションの場合、単曲履歴もDBxのリザルトのみを表示
                    if 'BATTLE' in s[-2]: # DBxのリザルトのみ抽出
                        best[9] = s[3]
                        if lamp_table.index(best[0]) < lamp_table.index(s[7]):
                            best[0] = s[7]
                            best[3] = s[-2]
                            best[10] = s[-1][2:10]
                        if s[9] > best[1]:
                            best[1] = s[9]
                            best[4] = s[-2]
                            best[11] = s[-1][2:10]
                            best[6] = s[5]
                            best[7],best[8] = self.calc_rankdiff(s[3], s[9])
                        if type(s[11]) == int:
                            if s[11] < best[2]:
                                best[2] = s[11]
                                best[5] = s[-2]
                                best[12] = s[-1][2:10]
                else: # 現在のオプションがDBx系ではない
                    if not 'BATTLE' in s[-2]: # DBx''以外''のリザルトのみ抽出
                        best[9] = s[3]
                        if lamp_table.index(best[0]) < lamp_table.index(s[7]):
                            best[0] = s[7]
                            best[3] = s[-2]
                            best[10] = s[-1][2:10]
                        if s[9] > best[1]:
                            best[1] = s[9]
                            best[4] = s[-2]
                            best[6] = s[5]
                            best[7],best[8] = self.calc_rankdiff(s[3], s[9])
                            best[11] = s[-1][2:10]
                        if s[8] > best[1]: # 過去の自己べ情報も確認
                            best[1] = s[8]
                            best[6] = s[5]
                            best[7],best[8] = self.calc_rankdiff(s[3], s[8])
                        if type(s[11]) == int:
                            if s[11] < best[2]:
                                best[2] = s[11]
                                best[5] = s[-2]
                                best[12] = s[-1][2:10]
                        if type(s[10]) == int:
                            if s[10] < best[2]:
                                best[2] = s[10]
            f.write(f'    <best_lamp>{best[0]}</best_lamp>\n')
            f.write(f'    <best_score>{best[1]}</best_score>\n')
            f.write(f'    <best_bp>{best[2]}</best_bp>\n')
            f.write(f'    <best_lamp_opt>{best[3]}</best_lamp_opt>\n')
            f.write(f'    <best_score_opt>{best[4]}</best_score_opt>\n')
            f.write(f'    <best_bp_opt>{best[5]}</best_bp_opt>\n')
            f.write(f'    <best_rank>{best[6]}</best_rank>\n')
            f.write(f'    <best_rankdiff0>{best[7]}</best_rankdiff0>\n')
            f.write(f'    <best_rankdiff1>{best[8]}</best_rankdiff1>\n')
            f.write(f'    <best_notes>{best[9]}</best_notes>\n')
            f.write(f'    <best_lamp_date>{best[10]}</best_lamp_date>\n')
            f.write(f'    <best_score_date>{best[11]}</best_score_date>\n')
            f.write(f'    <best_bp_date>{best[12]}</best_bp_date>\n')
            f.write(f'    <best_bp_rate>{best[2]*100/best[9]:.2f}</best_bp_rate>\n')

            for s in reversed(self.score_manager.score[f"{result[1]}___{result[2]}"]): # 過去のプレー履歴のループ,sが1つのresultに相当
                #logger.debug(f"s = {s}")
                bp = s[11]
                if len(s) != 14: # フォーマットがおかしい場合は飛ばす
                    continue
                if bp == None: # 昔のリザルトに入っていない可能性を考えて一応例外処理している
                    bp = '?'
                if 'DB' in result[2]: # 現在DBx系オプションの場合、単曲履歴もDBxのリザルトのみを表示
                    if 'BATTLE' in s[-2]: # DBxのリザルトのみ抽出
                        f.write('    <item>\n')
                        f.write(f'        <date>{s[-1][2:10]}</date>\n')
                        f.write(f'        <lamp>{s[7]}</lamp>\n')
                        f.write(f'        <score>{s[9]}</score>\n')
                        f.write(f'        <opt>{s[-2]}</opt>\n')
                        f.write(f'        <bp>{bp}</bp>\n')
                        f.write(f'        <notes>{s[3]*2}</notes>\n')
                        f.write(f'        <rank>{s[5]}</rank>\n')
                        tmp0,tmp1 = self.calc_rankdiff(s[3]*2, s[9])
                        f.write(f'        <rankdiff>{tmp0}{tmp1}</rankdiff>\n')
                        f.write(f'        <rankdiff0>{tmp0}</rankdiff0>\n')
                        f.write(f'        <rankdiff1>{tmp1}</rankdiff1>\n')
                        srate = f"{25*s[9]/s[3]:.2f}"
                        f.write(f'        <scorerate>{srate}</scorerate>\n')
                        f.write('    </item>\n')
                else: # 現在のオプションがDBx系ではない
                    if not 'BATTLE' in s[-2]: # DBx''以外''のリザルトのみ抽出
                        f.write('    <item>\n')
                        f.write(f'        <date>{s[-1][2:10]}</date>\n')
                        f.write(f'        <lamp>{s[7]}</lamp>\n')
                        f.write(f'        <score_pre>{s[8]}</score_pre>\n')
                        f.write(f'        <score>{s[9]}</score>\n')
                        f.write(f'        <opt>{s[-2]}</opt>\n')
                        f.write(f'        <bp>{bp}</bp>\n')
                        f.write(f'        <notes>{s[3]}</notes>\n')
                        f.write(f'        <rank_pre>{s[4]}</rank_pre>\n')
                        f.write(f'        <rank>{s[5]}</rank>\n')
                        tmp0,tmp1 = self.calc_rankdiff(s[3], s[9])
                        f.write(f'        <rankdiff>{tmp0}{tmp1}</rankdiff>\n')
                        f.write(f'        <rankdiff0>{tmp0}</rankdiff0>\n')
                        f.write(f'        <rankdiff1>{tmp1}</rankdiff1>\n')
                        srate = f"{50*s[9]/s[3]:.2f}"
                        f.write(f'        <scorerate>{srate}</scorerate>\n')
                        f.write('    </item>\n')
            f.write('</Results>\n')

    def update_table(self):
        mode = 'SP'
        if self.window['radio_mode_dp'].get():
            mode = 'DP'
        elif self.window['radio_mode_dbx'].get():
            mode = 'DB'
        self.mode = mode
        dat = []
        row_colors = []
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
                    if tmp[6]>0:
                        tmp[5] = f"{tmp[4]*100/(tmp[6]*2):.1f}"
                    else:
                        tmp[5] = 0
                    tmp[6] = bp
                    date = tmp[-1].split('-')
                    tmp[-1] = f"{date[0]}/{date[1]}/{date[2]} {date[3]}:{date[4]}"
                    # 非公式難易度
                    if mode == 'DP' and self.dp_unofficial != False:
                        if tmp[1] in self.dp_unofficial.keys():
                            if tmp[2][-1] == 'H':
                                tmp.append(self.dp_unofficial[tmp[1]][5])
                            elif tmp[2][-1] == 'A':
                                tmp.append(self.dp_unofficial[tmp[1]][6])
                            elif tmp[2][-1] == 'L':
                                tmp.append(self.dp_unofficial[tmp[1]][8])
                        #else:
                        #    print(tmp[1],'is not found!!!')
                    if len(tmp) == 10:
                        tmp.append('')
                    # フィルタ処理
                    to_push = True
                    if self.window['txt_search'].get().strip() != '':
                        for search_word in self.window['txt_search'].get().strip().split(' '):
                            if search_word.lower() not in tmp[1].lower():
                                to_push = False
                    if to_push: # 表示するデータを追加
                        dat.append(tmp)
        dat_np = np.array(dat)
        if len(dat_np.shape) > 1:
            # 曲名ソート用の処理
            # 同じ曲が並ぶ場合にlist.index()だと先頭の要素しか引けないため、
            # 全譜面が表示されるように補正している。表示順は特に考えていないので、N,H,Aなどの順に揃えるなら更に修正が必要
            if self.window['sortkey_title'].get():
                sort_row = 1
                titles = [dat_np[i][1] for i in range(dat_np.shape[0])]
                sorted_title = sorted(titles, key=str.lower)
                idxlist = [titles.index(sorted_title[i]) for i in range(len(sorted_title))]

                for ii in range(len(sorted_title)):
                    if ii > 0:
                        if sorted_title[ii] == sorted_title[ii-1]:
                            num_dup = 2
                            if ii > 1:
                                if sorted_title[ii] == sorted_title[ii-2]: # 3つ同じものが続いた場合
                                    num_dup = 3
                            tmp_chk = 0
                            for j in range(len(dat_np)):
                                if dat_np[j][1] == sorted_title[ii]:
                                    if tmp_chk < num_dup:
                                        idxlist[ii-num_dup+1+tmp_chk] = j
                                    else:
                                        break
                                    tmp_chk += 1
            if self.window['sortkey_lamp'].get():
                sort_row = 3
                # ランプソートの場合、一旦各ランプを数値に置き換える
                for y in range(dat_np.shape[0]):
                    dat_np[y][3] = lamp_table.index(dat_np[y][3])
            if self.window['sortkey_srate'].get():
                tmp = []
                for i,y in enumerate(range(dat_np.shape[0])):
                    tmp.append([float(i), float(dat_np[y][5])])
                tmp = np.array(tmp)
                tmp = tmp[tmp[:,1].argsort()] # IDX, srateだけのfloat型のnp.arrayを作ってソート
                idxlist = [int(tmp[i][0]) for i in range(tmp.shape[0])]
            if self.window['sortkey_bp'].get():
                tmp = []
                for i,y in enumerate(range(dat_np.shape[0])):
                    if dat_np[y][6] == '':
                        tmp.append([i, 9999])
                    else:
                        tmp.append([i, int(dat_np[y][6])])
                tmp = np.array(tmp)
                tmp = tmp[tmp[:,1].argsort()] # IDX, BPだけのint型のnp.arrayを作ってソート
                idxlist = [int(tmp[i][0]) for i in range(tmp.shape[0])]
            if self.window['sortkey_date'].get():
                sort_row = 9
            if self.window['sortkey_unofficial'].get():
                tmp = []
                for i,y in enumerate(range(dat_np.shape[0])):
                    if dat_np[y][10] == '':
                        tmp.append([float(i), 0.0])
                    else:
                        tmp.append([float(i), float(dat_np[y][10])])
                tmp = np.array(tmp)
                tmp = tmp[tmp[:,1].argsort()] # IDX, 非公式難易度だけのfloat型のnp.arrayを作ってソート
                idxlist = [int(tmp[i][0]) for i in range(tmp.shape[0])]
            # srate, BPソートの場合数値として求めたidxlistでソート
            if self.window['sortkey_srate'].get() or self.window['sortkey_bp'].get() or self.window['sortkey_unofficial'].get() or self.window['sortkey_title'].get():
                dat_np = dat_np[idxlist, :]
            else: # それ以外の場合、文字列としてソート
                dat_np = dat_np[dat_np[:,sort_row].argsort()]
            # 降順の処理
            if self.window['sort_descend'].get():
                dat_np = dat_np[::-1]
            # ランプソートの場合、数値に置き換えたランプをもとに戻す
            if self.window['sortkey_lamp'].get():
                for y in range(dat_np.shape[0]):
                    dat_np[y][3] = lamp_table[int(dat_np[y][3])]
            # ソート処理
            dat = dat_np.tolist()
        self.window['table'].update(dat)
        for d in dat:
            lamp = d[3]
            if lamp == 'FAILED':
                bgc = '#aaaaaa'
            elif lamp == 'A-CLEAR':
                bgc = '#ffaaff'
            elif lamp == 'E-CLEAR':
                bgc = '#aaffaa'
            elif lamp == 'CLEAR':
                bgc = '#77aaff'
            elif lamp == 'H-CLEAR':
                bgc = '#ffaa77'
            elif lamp == 'EXH-CLEAR':
                bgc = '#ffff44'
            elif lamp == 'F-COMBO':
                bgc = '#00ffff'
            else:
                bgc = '#ffffff'
            row_colors.append([len(row_colors), '#000000', bgc])
        self.window['table'].update(row_colors=row_colors)

    def main(self):
        self.gui()

        while True:
            ev, val = self.window.read()
            #print(ev, val)
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'btn_close_setting', 'btn_close_info'): # 終了処理
                if self.flg_save:
                    ico=self.ico_path('icon.ico')
                    ans = sg.popup_yes_no('プレーデータが変更されています。\nプレーデータを保存しますか?', icon=ico)
                    if ans == 'Yes':
                        self.score_manager.save()
                break
            elif ev == 'chk_lvall': # ALLボタンの処理
                for i in range(1,13):
                    self.window[f"chk_lv{i}"].update(val['chk_lvall'])
            elif ev == 'btn_export':
                self.export_csv()
            elif ev == 'reload':
                self.score_manager.load()
            elif ev == 'table':
                if len(val['table']) > 0:
                    self.gui_detals(self.window['table'].get()[val['table'][0]])
            elif ev == 'disp_obs':
                if len(val['table']) > 0:
                    self.write_history_cursong_xml(self.window['table'].get()[val['table'][0]])
            elif ev == 'clear':
                self.window['txt_search'].update('')
            elif ev == 'delete':
                if len(val['list_details']) > 0:
                    self.delete_playdata(self.window['table'].get()[val['table'][0]],val['list_details'])
            elif ev == 'save':
                ico=self.ico_path('icon.ico')
                ans = sg.popup_yes_no('プレーデータを保存しますか?', icon=ico)
                if ans == 'Yes':
                    self.score_manager.save()
                    self.flg_save = False
            if ev.startswith('sortkey_') or ev.startswith('radio_mode_') or ev.startswith('sort_') or (ev=='txt_search') or ev.startswith('chk_') or (ev=='reload') or (ev=='delete') or (ev=='clear'):
                self.update_table()

if __name__ == '__main__':
    c = ScoreManager()
    #b = c.disp_diff_best('DP12')

    a = ScoreViewer()
    a.main()

