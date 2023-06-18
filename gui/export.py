import PySimpleGUI as sg
import io
from PIL import Image
from pyperclip import copy
from os.path import abspath
from re import compile

from define import define
from .static import title,icon_path,background_color,background_color_label,selected_background_color
from .general import message
from playdata import output,export_dirname

icon_image = Image.open(icon_path)
resized_icon = icon_image.resize((32, 32))
icon_bytes = io.BytesIO()
resized_icon.save(icon_bytes, format='PNG')

pattern_color = compile('#[0-9a-fA-F]{6}')

graph_color_size=(15, 15)
graph_blank_size=(2, 2)

def open(recent):
    tab_manual = [
        [sg.Text('リザルト手帳はいくつかのファイルをexportフォルダに作成します。', background_color=background_color)],
        [
            sg.Text('exportの場所', background_color=background_color),
            sg.Input(key='exportpath', size=(60, 1)),
            sg.Button('クリップボードにコピー', key='button_copy_exportpath')
        ],
        [sg.Graph(canvas_size=graph_blank_size, graph_bottom_left=(0, 0), graph_top_right=graph_blank_size, background_color=background_color)],
        [
            sg.Column([
                [sg.Text('CSV出力', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('「CSV出力」ボタンを押すと全プレイデータと、いくつかの統計データファイル(CSV)を作成します。', background_color=background_color)],
        [sg.Text('作られた統計データファイルはExcel等で開くことができます。', background_color=background_color)],
        [
            sg.Column([
                [sg.Text('全プレイデータ', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('SP.csvとDP.csvは全プレイデータです。', background_color=background_color)],
        [
            sg.Column([
                [sg.Text('統計データ', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('難易度ごとの各クリアタイプ・各DJレベルの曲数や、レベルごとの各クリアタイプ・各DJレベルの曲数を統計したファイルを作成します。', background_color=background_color)],
        [sg.Text('たとえば、SP-難易度-DJレベル.csv はSPの難易度ごとに各DJレベルの曲数を統計したデータです。', background_color=background_color)],
        [sg.Text('各行の「total」はリザルト手帳で記録済みの曲数です。', background_color=background_color)],
        [sg.Text('INFINITASに収録されている曲数とは異なるのでご注意ください。', background_color=background_color)]
    ]

    tab_obs = [
        [
            sg.Column([
                [sg.Text('OBSとは録画や配信をするためのソフトウェアです。', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('exportフォルダに含まれる最近のデータ(recent.html)と統計データ(summary.html)は、OBSに追加することができます。', background_color=background_color)],
        [sg.Text('ソースにブラウザを追加して、ローカルファイルのチェックを入れて対象のhtmlファイルを指定してください。', background_color=background_color)],
        [
            sg.Column([
                [sg.Text('recent.html', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('過去12時間以内のプレイ曲数と曲名が表示できます。', background_color=background_color)],
        [
            sg.Column([
                [sg.Text('summary.html', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('CSV出力で作られた統計データファイルを表示できます。', background_color=background_color)],
        [sg.Text('デフォルトではSP,DP両方のANOTHERのA,AA,AAAの曲数を表示します。', background_color=background_color)],
        [sg.Text('表示内容を変更するときは「統計データ」タブでカスタムCSSを作成してください。', background_color=background_color)],
        [
            sg.Column([
                [sg.Text('カスタムCSS', background_color=background_color_label)]
            ], pad=5, background_color=background_color_label)
        ],
        [sg.Text('「最近のデータ」「統計データ」タブからカスタムCSSを作成できます。', background_color=background_color)],
        [sg.Text('作成されたCSSをコピーして、OBSのほうのソースのプロパティで「カスタムCSS」に貼り付けてください。', background_color=background_color)]
    ]

    tab_recent = [
        [
            sg.Text('文字サイズ', size=(10, 1), justification='right', background_color=background_color),
            sg.Input('46', size=(4, 1), key='recent size', enable_events=True),
            sg.Text('px', background_color=background_color),
            sg.Text('文字色', size=(10, 1), justification='right', background_color=background_color),
            sg.Input('#808080', size=(9, 1), key='recent color', enable_events=True),
            sg.Graph(key='graph recent color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#808080'),
            sg.Text('影色', size=(10, 1), justification='right', background_color=background_color),
            sg.Input('#000000', size=(9, 1), key='recent shadow-color', enable_events=True),
            sg.Graph(key='graph recent shadow-color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#000000')
        ],
        [
            sg.Column([
                [
                    sg.Text('プレイ曲数', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent played_count display', default=True, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent played_count color', enable_events=True),
            sg.Graph(key='graph recent played_count color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ],
        [
            sg.Column([
                [
                    sg.Text('スコアの合計', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent score display', default=False, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent score color', enable_events=True),
            sg.Graph(key='graph recent score color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ],
        [
            sg.Column([
                [
                    sg.Text('ミスカウントの合計', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent misscount display', default=False, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent misscount color', enable_events=True),
            sg.Graph(key='graph recent misscount color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ],
        [
            sg.Column([
                [
                    sg.Text('更新したスコアの合計', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent updated_score display', default=False, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent updated_score color', enable_events=True),
            sg.Graph(key='graph recent updated_score color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ],
        [
            sg.Column([
                [
                    sg.Text('更新したミスカウントの合計', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent updated_misscount display', default=False, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent updated_misscount color', enable_events=True),
            sg.Graph(key='graph recent updated_misscount color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ],
        [
            sg.Column([
                [
                    sg.Text('クリアの回数', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent clear display', default=False, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent clear color', enable_events=True),
            sg.Graph(key='graph recent clear color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ],
        [
            sg.Column([
                [
                    sg.Text('FAILEDの回数', background_color=background_color_label, size=(26, None), justification='right'),
                    sg.Checkbox('表示する', key='recent failed display', default=False, enable_events=True, background_color=background_color_label)
                ]
            ], pad=5, background_color=background_color_label),
            sg.Text('文字色', justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='recent failed color', enable_events=True),
            sg.Graph(key='graph recent failed color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff'),
        ]
    ]

    tab_summary = [
        [
            sg.Text('文字色', size=(8, 1), justification='right', background_color=background_color),
            sg.Input('#808080', size=(9, 1), key='summary color', enable_events=True),
            sg.Graph(key='graph summary color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#808080'),
            sg.Text('影色', size=(6, 1), justification='right', background_color=background_color),
            sg.Input('#000000', size=(9, 1), key='summary shadow-color', enable_events=True),
            sg.Graph(key='graph summary shadow-color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#000000'),
            sg.Text('日時の文字色', size=(15, 1), justification='right', background_color=background_color),
            sg.Input('#c0c0ff', size=(9, 1), key='summary date color', enable_events=True),
            sg.Graph(key='graph summary date color', canvas_size=graph_color_size, graph_bottom_left=(0, 0), graph_top_right=graph_color_size, background_color='#c0c0ff')
        ],
        [
            sg.Checkbox('SP', key='SP', default=True, enable_events=True, background_color=background_color),
            sg.Column([
                [
                    *[sg.Checkbox(value, key=f'check SP {value}', enable_events=True, background_color=background_color_label) for value in define.value_list['difficulties']],
                ],
                [
                    sg.Column([
                        [
                            *[sg.Checkbox(value, key=f'check SP difficulty {value}', enable_events=True, background_color=background_color) for value in define.value_list['clear_types']]
                        ],
                        [
                            *[sg.Checkbox(value, key=f'check SP difficulty {value}', enable_events=True, background_color=background_color) for value in define.value_list['dj_levels']]
                        ],
                    ], pad=2, background_color=background_color)
                ],
                [
                    *[sg.Checkbox(value, key=f'check SP {value}', enable_events=True, background_color=background_color_label) for value in define.value_list['levels']]
                ],
                [
                    sg.Column([
                        [
                            *[sg.Checkbox(value, key=f'check SP level {value}', enable_events=True, background_color=background_color) for value in define.value_list['clear_types']]
                        ],
                        [
                            *[sg.Checkbox(value, key=f'check SP level {value}', enable_events=True, background_color=background_color) for value in define.value_list['dj_levels']]
                        ],
                    ], pad=2, background_color=background_color)
                ],
            ], pad=2, background_color=background_color_label)
        ],
        [
            sg.Checkbox('DP', key='DP', default=True, enable_events=True, background_color=background_color),
            sg.Column([
                [
                    *[sg.Checkbox(value, key=f'check DP {value}', enable_events=True, background_color=background_color_label) for value in define.value_list['difficulties']],
                ],
                [
                    sg.Column([
                        [
                            *[sg.Checkbox(value, key=f'check DP difficulty {value}', enable_events=True, background_color=background_color) for value in define.value_list['clear_types']]
                        ],
                        [
                            *[sg.Checkbox(value, key=f'check DP difficulty {value}', enable_events=True, background_color=background_color) for value in define.value_list['dj_levels']]
                        ],
                    ], pad=2, background_color=background_color)
                ],
                [
                    *[sg.Checkbox(value, key=f'check DP {value}', enable_events=True, background_color=background_color_label) for value in define.value_list['levels']]
                ],
                [
                    sg.Column([
                        [
                            *[sg.Checkbox(value, key=f'check DP level {value}', enable_events=True, background_color=background_color) for value in define.value_list['clear_types']]
                        ],
                        [
                            *[sg.Checkbox(value, key=f'check DP level {value}', enable_events=True, background_color=background_color) for value in define.value_list['dj_levels']]
                        ],
                    ], pad=2, background_color=background_color)
                ],
            ], pad=2, background_color=background_color_label)
        ]
    ]

    layout = [
        [
            sg.TabGroup([[
                sg.Tab('マニュアル', tab_manual, pad=0, background_color=background_color),
                sg.Tab('OBSについて', tab_obs, pad=0, background_color=background_color),
                sg.Tab('最近のデータ', tab_recent, pad=0, background_color=background_color),
                sg.Tab('統計データ', tab_summary, pad=0, background_color=background_color)
            ]], pad=0, background_color=background_color, tab_background_color=background_color, selected_background_color=selected_background_color)
        ],
        [
        ],

        [
            sg.Multiline(key='css', size=(60, 6)),
            sg.Column([
                [
                    sg.Button('CSV出力', key='button_output_csv'),
                    sg.Button('最近のデータのリセット', key='button_clear_recent')
                ],
                [sg.Button('←CSSをクリップボードにコピー', key='button_copy_css')],
                [sg.Button('閉じる', key='button_close')]
            ], pad=0, background_color=background_color, vertical_alignment='bottom')
        ]
    ]

    window = sg.Window(
        f'{title} (エクスポート)',
        layout,
        icon=icon_path,
        grab_anywhere=True,
        return_keyboard_events=True,
        resizable=False,
        finalize=True,
        enable_close_attempted_event=True,
        background_color=background_color,
        modal=True
    )

    generate_recent_css(window)
    for play_mode in define.value_list['play_modes']:
        change_checkstatus_from_playside(window, play_mode)
        window[f'check {play_mode} ANOTHER'].update(True)
        window[f'check {play_mode} difficulty A'].update(True)
        window[f'check {play_mode} difficulty AA'].update(True)
        window[f'check {play_mode} difficulty AAA'].update(True)
    window['exportpath'].update(abspath(export_dirname))

    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, sg.WINDOW_CLOSE_ATTEMPTED_EVENT, 'button_close'):
            break
        if 'recent' in event:
            generate_recent_css(window)
        if 'summary' in event:
            generate_summary_css(window)
        if event in define.value_list['play_modes']:
            change_checkstatus_from_playside(window, event)
            generate_summary_css(window)
        if 'check' in event:
            generate_summary_css(window)
        if event == 'button_output_csv':
            output()
            message('完了', '出力が完了しました。')
        if event == 'button_clear_recent':
            recent.clear()
        if event == 'button_copy_css':
            copy(values['css'])
        if event == 'button_copy_exportpath':
            copy(values['exportpath'])

    window.close()

    return

def change_checkstatus_from_playside(window, play_mode):
    value = window[play_mode].get()
    for difficulty in define.value_list['difficulties']:
        window[f'check {play_mode} {difficulty}'].update(disabled=not value)
    for level in define.value_list['levels']:
        window[f'check {play_mode} {level}'].update(disabled=not value)
    for clear_type in define.value_list['clear_types']:
        window[f'check {play_mode} difficulty {clear_type}'].update(disabled=not value)
        window[f'check {play_mode} level {clear_type}'].update(disabled=not value)
    for dj_level in define.value_list['dj_levels']:
        window[f'check {play_mode} difficulty {dj_level}'].update(disabled=not value)
        window[f'check {play_mode} level {dj_level}'].update(disabled=not value)

def generate_recent_css(window):
    css = []

    css.append('body {')
    size = window[f'recent size'].get()
    if str.isdecimal(size):
        css.append(f'  font-size: {size}px;')
    color = window[f'recent color'].get()
    if pattern_color.fullmatch(color) is not None:
        window[f'graph recent color'].update(background_color=color)
        css.append(f'  color: {color};')
    shadow_color = window[f'recent shadow-color'].get()
    if pattern_color.fullmatch(shadow_color) is not None:
        window[f'graph recent shadow-color'].update(shadow_color)
        shadows = ['1px 1px', '-1px 1px', '1px -1px', '-1px -1px']
        shadow_value = [f'{shadow} 0 {shadow_color}' for shadow in shadows]
        css.append(f"  text-shadow: {','.join(shadow_value)};")
    css.append('}')

    for key in ['played_count', 'score', 'misscount', 'updated_score', 'updated_misscount', 'clear', 'failed']:
        display = 'block' if window[f'recent {key} display'].get() else 'none'
        color = window[f'recent {key} color'].get()
        if pattern_color.fullmatch(color) is not None:
            css.append(f'div#{key} {{')
            window[f'graph recent {key} color'].update(background_color=color)
            css.append(f'  display: {display};')
            css.append(f'  color: {color};')
            css.append('}')

    window['css'].update('\n'.join(css))

def generate_summary_css(window):
    css = []

    css.append('body {')
    color = window[f'summary color'].get()
    if pattern_color.fullmatch(color) is not None:
        window[f'graph summary color'].update(background_color=color)
        css.append(f'  color: {color};')
    shadow_color = window[f'summary shadow-color'].get()
    if pattern_color.fullmatch(shadow_color) is not None:
        window[f'graph summary shadow-color'].update(shadow_color)
        shadows = ['1px 1px', '-1px 1px', '1px -1px', '-1px -1px']
        shadow_value = [f'{shadow} 0 {shadow_color}' for shadow in shadows]
        css.append(f"  text-shadow: {','.join(shadow_value)};")
    css.append('}')

    color = window[f'summary date color'].get()
    if pattern_color.fullmatch(color) is not None:
        css.append('div#update_date {')
        window[f'graph summary date color'].update(background_color=color)
        css.append(f'  color: {color};')
        css.append('}')

    for play_mode in define.value_list['play_modes']:
        for dj_level in ['A', 'AA', 'AAA']:
            css.append(f"div.{play_mode}.ANOTHER.{dj_level} {{ display: none;}}")
        if window[play_mode].get():
            for difficulty in define.value_list['difficulties']:
                if window[f'check {play_mode} {difficulty}'].get():
                    for clear_type in define.value_list['clear_types']:
                        if window[f'check {play_mode} difficulty {clear_type}'].get():
                            css.append(f"div.{play_mode}.{difficulty}.{clear_type} {{ display: block;}}")
                    for dj_level in define.value_list['dj_levels']:
                        if window[f'check {play_mode} difficulty {dj_level}'].get():
                            css.append(f"div.{play_mode}.{difficulty}.{dj_level} {{ display: block;}}")
            for level in define.value_list['levels']:
                if window[f'check {play_mode} {level}'].get():
                    for clear_type in define.value_list['clear_types']:
                        if window[f'check {play_mode} level {clear_type}'].get():
                            css.append(f"div.{play_mode}.LEVEL{level}.{clear_type} {{ display: block;}}")
                    for dj_level in define.value_list['dj_levels']:
                        if window[f'check {play_mode} level {dj_level}'].get():
                            css.append(f"div.{play_mode}.LEVEL{level}.{dj_level} {{ display: block;}}")

    window['css'].update('\n'.join(css))
