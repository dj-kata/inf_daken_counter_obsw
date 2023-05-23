import calendar
import datetime
import os, sys
import PySimpleGUI as sg
from daken_logger import DakenLogger
import webbrowser, urllib, requests

today = datetime.date.today()

# icon用
class LogManager:
    def __init__(self, settings):
        self.settings = settings
        self.dakenlog = DakenLogger()
        self.idxlist  = [] # 現在表示しているリストボックス内のデータがself.dakenlog.logの何番目であるか
        self.sel_day  = False # 現在選択している日
        self.window   = False
    def ico_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def update_date(self, date):
        cal = calendar.Calendar(firstweekday=6)
        days = cal.monthdatescalendar(date.year, date.month)
        self.window['cur_year'].update(date.year)
        self.window['cur_month'].update(f"{date.month:2d}")
        for j,row in enumerate(days):
            inner = []
            for i, day in enumerate(row):
                textc, bgc = self.get_color(date, i, day)
                self.window[f"day_{j}{i}"].update(day.day, text_color=textc, background_color=bgc)
                cur = self.get_date_from_cell(i, j, date).strftime('%Y/%m/%d')
                if cur in self.dakenlog.log_date: # ログがある日は*をつける
                    self.window[f"day_{j}{i}"].update(f"*{self.window[f'day_{j}{i}'].get()}")

        if len(days) == 5:
            for i in range(7):
                self.window[f"day_{5}{i}"].update("")

    def get_color(self, cal_date, i, day):
        text_color = 'black'
        background_color   = 'white'
        if day == today:
            text_color='white'
            background_color='gray'
        elif (i == 0) and (day.month == cal_date.month):
            text_color='red'
        elif (i == 6) and (day.month == cal_date.month):
            text_color='blue'
        elif day.month == cal_date.month:
            pass
        elif i == 0:
            text_color='#ff9999'
        elif i == 6:
            text_color='#9999ff'
        else:
            text_color='#cccccc'
        return text_color, background_color

    # 全日付ますの色付けを再実行
    def set_allday_color(self, cal_date, range_st=False, range_ed=False):
        cal = calendar.Calendar(firstweekday=6)
        days = cal.monthdatescalendar(cal_date.year, cal_date.month)
        for j,row in enumerate(days):
            for i, day in enumerate(row):
                textc, bgc = self.get_color(cal_date, i, day)
                if range_st and range_ed:
                    if day >= range_st and day<= range_ed:
                        textc = '#000000'
                        bgc   = '#22ff77'
                self.window[f"day_{j}{i}"].update(text_color=textc, background_color=bgc)
        if len(days) == 5:
            for i in range(7):
                self.window[f"day_{5}{i}"].update("", background_color='#ffffff')

    # 指定されたセルの日付をdatetime.date形式で返す
    def get_date_from_cell(self, i, j, cal_date):
        dat = self.window[f"day_{j}{i}"].get().split('*')[-1]
        ret = False
        if dat == '':
            ret = False
        elif j==0 and int(dat) > 14: # 前の月の分
            last_month = datetime.date(cal_date.year, cal_date.month, 1) - datetime.timedelta(days=1)
            ret = datetime.date(last_month.year, last_month.month, int(dat))
        elif j>=4 and int(dat) < 14: # 次の月の分
            next_month = datetime.date(cal_date.year, cal_date.month, 28) + datetime.timedelta(days=4)
            ret = datetime.date(next_month.year, next_month.month, int(dat))
        else:
            ret = datetime.date(cal_date.year, cal_date.month, int(dat))
        return ret

    def create_layout(self):
        cal_date = datetime.date.today()
        weekday = ['SUN','MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']  
        cal = calendar.Calendar(firstweekday=6)
        days = cal.monthdatescalendar(cal_date.year, cal_date.month)
        layout_cal = [
                    [sg.Radio('編集', group_id='0', font=(None, 16), default=True, enable_events=True, key='btn_edit'), sg.Radio('範囲選択', '0', font=(None, 16), enable_events=True, key='btn_range')],
                    [sg.Button('<<'), sg.Text(cal_date.year, font=(None, 16, 'bold'), key='cur_year')
                    ,sg.Text('年', font=(None, 16, 'bold')), sg.Button('>>')
                    ,sg.Push(), sg.Button('<'), sg.Text(f"{cal_date.month:2d}"
                    ,font=(None, 16, 'bold'), key='cur_month')
                    ,sg.Text('月', font=(None, 16, 'bold')), sg.Button('>'), sg.Push()],
                ]
        layout_edit = [
                    [sg.Text('選択中:', font=(None,16)), sg.Text('xxxx/xx/xx', font=(None, 16), key='date_start'),sg.Text(' - ', font=(None, 16)),sg.Text('xxxx/xx/xx', font=(None, 16), key='date_end')],
                    [sg.Listbox([''], size=(50, 7), key='list_log', enable_events=True, select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE)],
                    [sg.Button('削除', font=(None, 16), key='delete'),sg.Button('マージ', font=(None, 16), key='merge'),sg.Button('保存', font=(None, 16), key='save'),sg.Button('グラフ生成', font=(None, 16), key='generate')],
                    [sg.Button('直近7日', font=(None, 16), key='thisweek'),sg.Button('今月', font=(None, 16), key='thismonth')],
        ]
        inner = []

        for week in weekday:
            inner.append(sg.Text(week, size=(4,1), text_color='white', background_color='green', justification='center', font=(None, 16)))
        layout_cal.append(inner.copy())

        for j in range(6):
            inner = []
            for i in range(7):
                inner.append(sg.Text(' ', size=(4,1), justification='right', key=f"day_{j}{i}", enable_events=True, font=(None,16)))
            layout_cal.append(inner.copy())

        layout = [[sg.Column(layout_cal), sg.Column(layout_edit)],
                [sg.Text('', key='info', font=(None,9))]]
        return layout

    def update_listbox(self):
        # 保存されているスコアの一覧を取得
        tmp = []
        tmp_idx = []
        for i,d in enumerate(self.dakenlog.log):
            if self.day.strftime('%Y/%m/%d') == self.dakenlog.log_date[i]:
                tmp_idx.append(i)
                tmp.append(f"{i}, plays:{d[1]:,}, {d[2]:,}-{d[3]:,}-{d[4]:,}-{d[5]:,}-{d[6]:,} (cb{d[7]:,})")
        self.window['list_log'].update(tmp)
        self.idxlist = tmp_idx

    def open_twitter(self, dat, term):
        encoded_title = urllib.parse.quote(f"{term}は{dat[0]:,}曲プレイし、{dat[1]+dat[2]+dat[3]:,}ノーツ叩きました。\n(PG:{dat[1]:,}, GR:{dat[2]:,}, GD:{dat[3]:,}, BD:{dat[4]:,}, PR:{dat[5]:,}, CB:{dat[6]:,})\n#INFINITAS_daken_counter")
        webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_title}")

    def main(self):
        mode = 'edit' # edit, range_st, range_ed
        cal_date = today
        layout = self.create_layout()
        icon = self.ico_path('icon.ico')
        self.window = sg.Window('INFINITAS打鍵カウンタ - グラフ生成ツール', layout,icon=icon, return_keyboard_events=True, finalize=True, modal=True, location=(self.settings['lx'], self.settings['ly']))
        self.update_date(cal_date)
        self.set_allday_color(cal_date)
        pre_sel = False
        pre_sel_day = False

        # 作成範囲
        range_st = False
        range_ed = False
        while True:
            event, val = self.window.read()
            if event in (sg.WIN_CLOSED, 'Escape:27'):
                break
            elif event == '<':
                cal_date = datetime.date(cal_date.year, cal_date.month, 1) - datetime.timedelta(days=1)
                self.update_date(cal_date)
                self.set_allday_color(cal_date, range_st, range_ed)
            elif event == '>':
                cal_date = datetime.date(cal_date.year, cal_date.month, 28) + datetime.timedelta(days=4)
                self.update_date(cal_date)
                self.set_allday_color(cal_date, range_st, range_ed)
            elif event == '<<':
                cal_date = datetime.date(cal_date.year - 1, cal_date.month, 1)
                self.update_date(cal_date)
                self.set_allday_color(cal_date, range_st, range_ed)
            elif event == '>>':
                cal_date = datetime.date(cal_date.year + 1, cal_date.month, 1)
                self.update_date(cal_date)
                self.set_allday_color(cal_date, range_st, range_ed)
            elif event == 'delete':
                # 複数同時にpopするために、削除した数をカウントしておく
                deleted = 0
                for d in val['list_log']:
                    idx = int(d.split(',')[0]) - deleted
                    self.dakenlog.delete(idx)
                    self.dakenlog.disp()
                    self.update_listbox()
                    self.update_date(cal_date)
                    self.set_allday_color(cal_date, range_st, range_ed)
                    deleted += 1
            elif event == 'merge':
                newval = [0]*7
                if len(self.idxlist) > 0:
                    for d in self.idxlist:
                        for i in range(7):
                            newval[i] += self.dakenlog.log[d][1+i]
                    for i in range(7):
                        self.dakenlog.log[self.idxlist[0]][1+i] = newval[i]

                    deleted = 0
                    for i in range(1,len(self.idxlist)):
                        idx = self.idxlist[i] - deleted
                        self.dakenlog.delete(idx)
                        deleted += 1
                    self.dakenlog.disp()
                    self.update_listbox()
                    self.update_date(cal_date)
                    self.set_allday_color(cal_date, range_st, range_ed)

            elif event == 'save':
                self.dakenlog.save()
                self.window['info'].update(f"打鍵ログを保存しました。")
            elif event == 'btn_range':
                mode = 'range_st'
            elif event == 'btn_edit':
                mode = 'edit'
                range_st = False
                range_ed = False
                self.set_allday_color(cal_date)
            elif event.startswith('day_'):
                # 選択したセルを色付け
                if mode == 'edit':
                    self.day = self.get_date_from_cell(int(event[-1]), int(event[-2]), cal_date)
                    if pre_sel:
                        if pre_sel_day and pre_sel != event:
                            textc, bgc = self.get_color(cal_date, int(pre_sel[-1]), pre_sel_day)
                            # 1つ前に選択したセルの色を戻す
                            self.window[pre_sel].update(background_color=bgc, text_color=textc)
                    pre_sel_day = self.day
                    pre_sel = event
                    if self.day:
                        self.window[event].update(background_color='#22ff77', text_color='#000000')
                        self.window['date_start'].update(f"{self.day.year}/{self.day.month:02d}/{self.day.day:02d}")
                        self.window['date_end'].update(f"{self.day.year}/{self.day.month:02d}/{self.day.day:02d}")
                        self.update_listbox()
                elif mode == 'range_st':
                    mode = 'range_ed'
                    range_ed = False
                    range_st = self.get_date_from_cell(int(event[-1]), int(event[-2]), cal_date)
                    self.window['date_start'].update(f"{range_st.year}/{range_st.month:02d}/{range_st.day:02d}")
                    self.window['date_end'].update('xxxx/xx/xx')
                    self.set_allday_color(cal_date)
                    if range_st:
                        self.window[event].update(background_color='#22ff77', text_color='#000000')
                elif mode == 'range_ed':
                    mode = 'range_st'
                    range_ed = self.get_date_from_cell(int(event[-1]), int(event[-2]), cal_date)
                    self.set_allday_color(cal_date, range_st, range_ed)
                    if range_ed:
                        self.window['date_end'].update(f"{range_ed.year}/{range_ed.month:02d}/{range_ed.day:02d}")
            elif event == 'thisweek':
                range_ed = today
                range_st = today-datetime.timedelta(days=6)
                self.window['date_start'].update(f"{range_st.year}/{range_st.month:02d}/{range_st.day:02d}")
                self.window['date_end'].update(f"{range_ed.year}/{range_ed.month:02d}/{range_ed.day:02d}")
                self.set_allday_color(cal_date, range_st, range_ed)
                if self.settings['autosave_dir'] != '':
                    filename = f"{self.settings['autosave_dir']}/log_{range_st}_{range_ed}.png"
                else:
                    filename = f"log_{range_st}_{range_ed}.png"
                stats = self.dakenlog.gen_graph_with_date(filename, range_st, range_ed, write_sum=True)
                self.open_twitter(stats, '今週')
                self.window['info'].update(f"グラフ画像を生成しました -> {filename}")
            elif event == 'thismonth':
                range_st = datetime.date(today.year,today.month,1)
                ed_tmp = datetime.date(today.year,today.month,27) + datetime.timedelta(days=4)
                range_ed = datetime.date(ed_tmp.year, ed_tmp.month, 1) - datetime.timedelta(days=1)
                self.window['date_start'].update(f"{range_st.year}/{range_st.month:02d}/{range_st.day:02d}")
                self.window['date_end'].update(f"{range_ed.year}/{range_ed.month:02d}/{range_ed.day:02d}")
                self.set_allday_color(cal_date, range_st, range_ed)
                if self.settings['autosave_dir'] != '':
                    filename = f"{self.settings['autosave_dir']}/log_{range_st.strftime('%Y-%m')}.png"
                else:
                    filename = f"log_{range_st.strftime('%Y-%m')}.png"
                stats = self.dakenlog.gen_graph_with_date(filename, range_st, range_ed)
                self.open_twitter(stats, range_st.strftime("%Y年%m月"))
                self.window['info'].update(f"グラフ画像を生成しました -> {filename}")
            elif event == 'generate':
                if range_st and range_ed:
                    if self.settings['autosave_dir'] != '':
                        filename = f"{self.settings['autosave_dir']}/log_{range_st}_{range_ed}.png"
                    else:
                        filename = f"log_{range_st}_{range_ed}.png"
                    write_sum = (range_ed - range_st).days <= 7
                    stats = self.dakenlog.gen_graph_with_date(filename, range_st, range_ed, write_sum=write_sum)
                    self.open_twitter(stats, f'{range_st.strftime("%Y年%m月%d日")}～{range_ed.strftime("%Y年%m月%d日")}')
                    self.window['info'].update(f"グラフ画像を生成しました -> {filename}")

        self.window.close()

if __name__ == '__main__':
    a = LogManager({'lx':-1000, 'ly':500})
    a.main()