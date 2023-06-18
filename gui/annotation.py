import PySimpleGUI as sg
import io

from define import define
from recog import recog
from .static import title,icon_path,background_color

in_area_background_color='#5779dd'

def layout_manage(keys):
    selectable_value_list = {}
    for key, values in define.value_list.items():
        selectable_value_list[key] = ['', *values]
    selectable_value_list['all_options'] = [
        '',
        *define.value_list['options_arrange'],
        *define.value_list['options_arrange_dp'],
        *define.value_list['options_arrange_sync'],
        *define.value_list['options_flip'],
        *define.value_list['options_assist'],
        'BATTLE'
    ]
    selectable_value_list['delimita'] = ['', ',', '/']

    result_informations = [
        [
            sg.Text('プレイモード', size=(18, 1)),
            sg.Text(key='result_play_mode', background_color=in_area_background_color)
        ],
        [
            sg.Text('難易度', size=(18, 1)),
            sg.Text(key='result_difficulty', background_color=in_area_background_color),
            sg.Text(key='result_level', background_color=in_area_background_color)
        ],
        [
            sg.Text('ノーツ数', size=(18, 1)),
            sg.Text(key='result_notes', background_color=in_area_background_color)
        ],
        [
            sg.Text('曲名', size=(18, 1)),
            sg.Text(key='result_music', background_color=in_area_background_color)
        ]
    ]

    result_details = [
        [
            sg.Text('グラフ表示', size=(21, 1)),
            sg.Text(key='result_graph', background_color=in_area_background_color)
        ],
        [
            sg.Text('配置オプション', size=(21, 1)),
            sg.Text(key='result_option_arrange', background_color=in_area_background_color)
        ],
        [
            sg.Text('FLIPオプション', size=(21, 1)),
            sg.Text(key='result_option_flip', background_color=in_area_background_color)
        ],
        [
            sg.Text('アシストオプション', size=(21, 1)),
            sg.Text(key='result_option_assist', background_color=in_area_background_color)
        ],
        [
            sg.Text('特殊オプション', size=(21, 1)),
            sg.Text('BATTLE', visible=False, key='result_option_battle', background_color=in_area_background_color)
        ],
        [
            sg.Text('クリアタイプ', size=(21, 1)),
            sg.Text(key='result_clear_type_best', size=(10, 1), background_color=in_area_background_color),
            sg.Text(key='result_clear_type_current', size=(10, 1), background_color=in_area_background_color),
            sg.Text('NEW', visible=False, key='result_clear_type_new', background_color=in_area_background_color)
        ],
        [
            sg.Text('DJレベル', size=(21, 1)),
            sg.Text(key='result_dj_level_best', size=(10, 1), background_color=in_area_background_color),
            sg.Text(key='result_dj_level_current', size=(10, 1), background_color=in_area_background_color),
            sg.Text('NEW', visible=False, key='result_dj_level_new', background_color=in_area_background_color)
        ],
        [
            sg.Text('スコア', size=(21, 1)),
            sg.Text(key='result_score_best', size=(10, 1), background_color=in_area_background_color),
            sg.Text(key='result_score_current', size=(10, 1), background_color=in_area_background_color),
            sg.Text('NEW', visible=False, key='result_score_new', background_color=in_area_background_color)
        ],
        [
            sg.Text('ミスカウント', size=(21, 1)),
            sg.Text(key='result_miss_count_best', size=(10, 1), background_color=in_area_background_color),
            sg.Text(key='result_miss_count_current', size=(10, 1), background_color=in_area_background_color),
            sg.Text('NEW', visible=False, key='result_miss_count_new', background_color=in_area_background_color)
        ],
        [
            sg.Text('グラフターゲット', size=(21, 1)),
            sg.Text(key='result_graphtarget', size=(21, 1), background_color=in_area_background_color)
        ]
    ]

    manage_label_define = [
        [
            sg.Checkbox('曲情報', key='has_informations', enable_events=True, background_color=in_area_background_color),
            sg.Checkbox('詳細リザルト', key='has_details', enable_events=True, background_color=in_area_background_color),
        ],
        [
            sg.Text('プレイモード', size=(15, 1)),
            sg.Combo(selectable_value_list['play_modes'], key='play_mode', readonly=True, enable_events=True, disabled=True)
        ],
        [
            sg.Text('難易度', size=(15, 1)),
            sg.Combo(selectable_value_list['difficulties'], key='difficulty', size=(13, 1), readonly=True, disabled=True),
            sg.Combo(selectable_value_list['levels'], key='level', readonly=True, disabled=True)
        ],
        [
            sg.Text('ノーツ数', size=(15, 1)),
            sg.Input(key='notes', size=(8, 1)),
        ],
        [
            sg.Text('曲名', size=(15, 1)),
            sg.Input(key='music', size=(30, 1)),
        ],
        [
            sg.Radio('デフォルト', group_id='display', key='display_default', disabled=True, background_color=in_area_background_color),
            sg.Radio('レーン別', group_id='display', key='display_lanes', disabled=True, background_color=in_area_background_color),
            sg.Radio('小節ごと', group_id='display', key='display_measures', disabled=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('オプション', size=(15, 1)),
            sg.Column([
                [
                    sg.Text('SP配置', size=(11, 1)),
                    sg.Combo(selectable_value_list['options_arrange'], key='option_arrange', size=(10, 1), readonly=True, disabled=True)
                ],
                [
                    sg.Text('DP配置', size=(11, 1)),
                    sg.Combo(selectable_value_list['options_arrange_dp'], key='option_arrange_1p', size=(6, 1), readonly=True, disabled=True),
                    sg.Text('/', background_color=in_area_background_color,pad=0),
                    sg.Combo(selectable_value_list['options_arrange_dp'], key='option_arrange_2p', size=(6, 1), readonly=True, disabled=True)
                ],
                [
                    sg.Text('BATTLE配置', size=(11, 1)),
                    sg.Combo(selectable_value_list['options_arrange_sync'], key='option_arrange_sync', size=(10, 1), readonly=True, disabled=True)
                ],
                [
                    sg.Text('フリップ', size=(11, 1)),
                    sg.Combo(selectable_value_list['options_flip'], key='option_flip', size=(10, 1), readonly=True, disabled=True)
                ],
                [
                    sg.Text('アシスト', size=(11, 1)),
                    sg.Combo(selectable_value_list['options_assist'], key='option_assist', size=(8, 1), readonly=True, disabled=True)
                ]
            ], background_color=in_area_background_color, pad=0)
        ],
        [
            sg.Text('特殊オプション', size=(15, 1)),
            sg.Check('BATTLE', key='option_battle', disabled=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('クリアタイプ', size=(15, 1)),
            sg.Combo(selectable_value_list['clear_types'], key='clear_type_best', size=(11, 1), readonly=True, disabled=True),
            sg.Combo(selectable_value_list['clear_types'], key='clear_type_current', size=(11, 1), readonly=True, disabled=True),
            sg.Checkbox('NEW', key='clear_type_new', disabled=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('DJレベル', size=(15, 1)),
            sg.Combo(selectable_value_list['dj_levels'], key='dj_level_best', size=(11, 1), readonly=True, disabled=True),
            sg.Combo(selectable_value_list['dj_levels'], key='dj_level_current', size=(11, 1), readonly=True, disabled=True),
            sg.Checkbox('NEW', key='dj_level_new', disabled=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('スコア', size=(15, 1)),
            sg.Input(key='score_best', size=(12, 1), disabled=True),
            sg.Input(key='score_current', size=(12, 1), disabled=True),
            sg.Checkbox('NEW', key='score_new', disabled=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('ミスカウント', size=(15, 1)),
            sg.Input(key='miss_count_best', size=(12, 1), disabled=True),
            sg.Input(key='miss_count_current', size=(12, 1), disabled=True),
            sg.Checkbox('NEW', key='miss_count_new', disabled=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('グラフターゲット', size=(15, 1)),
            sg.Combo(selectable_value_list['graphtargets'], key='graphtarget', size=(21, 1), readonly=True, disabled=True)
        ],
        [
            sg.Button('アノテーション保存', key='button_label_overwrite'),
            sg.Button('認識結果から引用', key='button_recog')
        ],
        [sg.Checkbox('未アノテーションのみ', key='only_not_annotation', enable_events=True, background_color=in_area_background_color)],
        [sg.Checkbox('曲名なしのみ', key='only_undefined_music', enable_events=True, background_color=in_area_background_color)],
        [sg.Checkbox('F-COMBOのみ', key='only_full_combo', enable_events=True, background_color=in_area_background_color)]
    ]

    return [
        [
            sg.Column([
                [
                    sg.Column([
                        [sg.Image(key='image_informations', size=define.informations_trimsize, background_color=background_color)],
                        [sg.Image(key='image_details', size=define.details_trimsize, background_color=background_color)]
                    ], background_color=background_color),
                    sg.Listbox(keys, key='list_keys', size=(24, 22), enable_events=True),
                ],
                [
                    sg.Column(result_informations, size=(300, 270), background_color=in_area_background_color),
                    sg.Column(result_details, size=(350, 270), background_color=in_area_background_color)
                ],
            ], pad=0, background_color=background_color),
            sg.Column([
                [sg.Column(manage_label_define, size=(410,645), background_color=in_area_background_color)],
            ], pad=0, background_color=background_color)
        ]
    ]

def generate_window(keys):
    global window

    window = sg.Window(
        title,
        layout_manage(keys),
        icon=icon_path,
        grab_anywhere=True,
        return_keyboard_events=True,
        resizable=False,
        finalize=True,
        enable_close_attempted_event=True,
        background_color=background_color
    )

    return window

def change_display(key, value):
    window[key].update(visible=value)

def set_area(area):
        window['left'].update(area[0])
        window['top'].update(area[1])
        window['right'].update(area[2])
        window['bottom'].update(area[3])

def switch_option_widths_view():
    visible = window['area_second'].get() == 'option'

    window['area_option1'].update(visible=visible)
    window['area_delimita1'].update(visible=visible)
    window['area_option2'].update(visible=visible)
    window['area_delimita2'].update(visible=visible)
    window['area_option3'].update(visible=visible)
    window['area_delimita3'].update(visible=visible)

def display_informations(image):
    if image is not None:
        bytes = io.BytesIO()
        image.save(bytes, format='PNG')
        window['image_informations'].update(data=bytes.getvalue(),visible=True)
    else:
        window['image_informations'].update(visible=False)

def display_details(image):
    if image is not None:
        bytes = io.BytesIO()
        image.save(bytes, format='PNG')
        window['image_details'].update(data=bytes.getvalue(),visible=True,size=define.details_trimsize)
    else:
        window['image_details'].update(visible=False)

def display_trim(image):
    while image.width > 1920 / 8 or image.height > 1080 / 4:
        image = image.resize((image.width // 2, image.height // 2))
    bytes = io.BytesIO()
    image.save(bytes, format='PNG')
    window['trim'].update(data=bytes.getvalue())

def update_image(name, image):
    bytes = io.BytesIO()
    image.save(bytes, format='PNG')
    window[name].update(data=bytes.getvalue())

def reset_informations():
    window['has_informations'].update(False)
    switch_informations_controls()

    window['result_play_mode'].update('')
    window['result_difficulty'].update('')
    window['result_level'].update('')
    window['result_notes'].update('')
    window['result_music'].update('')

def set_informations(image):
    window['has_informations'].update(True)
    switch_informations_controls()

    if image.height == 71:
        monochrome = image.convert('L')
    if image.height == 75:
        monochrome = image.crop((0, 3, image.width, image.height-1)).convert('L')
    if image.height == 78:
        monochrome = image.crop((0, 5, image.width, image.height-2)).convert('L')

    informations = recog.get_informations(monochrome)

    window['result_play_mode'].update(informations.play_mode if informations.play_mode is not None else '')
    window['result_difficulty'].update(informations.difficulty if informations.difficulty is not None else '')
    window['result_level'].update(informations.level if informations.level is not None else '')
    window['result_notes'].update(informations.notes if informations.notes is not None else '')
    window['result_music'].update(informations.music if informations.music is not None else '')

def reset_details():
    window['has_details'].update(False)
    switch_details_controls()

    window['result_graph'].update('')
    window['result_option_arrange'].update('')
    window['result_option_flip'].update('')
    window['result_option_assist'].update('')
    window['result_option_battle'].update(visible=False)
    window['result_clear_type_best'].update('')
    window['result_clear_type_current'].update('')
    window['result_clear_type_new'].update(visible=False)
    window['result_dj_level_best'].update('')
    window['result_dj_level_current'].update('')
    window['result_dj_level_new'].update(visible=False)
    window['result_score_best'].update('')
    window['result_score_current'].update('')
    window['result_score_new'].update(visible=False)
    window['result_miss_count_best'].update('')
    window['result_miss_count_current'].update('')
    window['result_miss_count_new'].update(visible=False)
    window['result_graphtarget'].update('')

def set_details(image):
    window['has_details'].update(True)
    switch_details_controls()

    monochrome = image.convert('L')

    window['result_graph'].update(recog.get_graph(monochrome))

    details = recog.get_details(monochrome)
    options = details.options
    clear_type = details.clear_type
    dj_level = details.dj_level
    score = details.score
    miss_count = details.miss_count

    if options is not None:
        window['result_option_arrange'].update(options.arrange if options.arrange is not None else '')
        window['result_option_flip'].update(options.flip if options.flip is not None else '')
        window['result_option_assist'].update(options.assist if options.assist is not None else '')
        window['result_option_battle'].update(visible=options.battle)
    else:
        window['result_option_arrange'].update('')
        window['result_option_flip'].update('')
        window['result_option_assist'].update('')
        window['result_option_battle'].update(visible=False)
    window['result_clear_type_best'].update(clear_type.best if clear_type.best is not None else '')
    window['result_clear_type_current'].update(clear_type.current if clear_type.current is not None else '')
    window['result_clear_type_new'].update(visible=clear_type.new)
    window['result_dj_level_best'].update(dj_level.best if dj_level.best is not None else '')
    window['result_dj_level_current'].update(dj_level.current if dj_level.current is not None else '')
    window['result_dj_level_new'].update(visible=dj_level.new)
    window['result_score_best'].update(score.best if score.best is not None else '')
    window['result_score_current'].update(score.current if score.current is not None else '')
    window['result_score_new'].update(visible=score.new)
    window['result_miss_count_best'].update(miss_count.best if miss_count.best is not None else '')
    window['result_miss_count_current'].update(miss_count.current if miss_count.current is not None else '')
    window['result_miss_count_new'].update(visible=miss_count.new)
    window['result_graphtarget'].update(details.graphtarget if details.graphtarget is not None else '')

def set_result():
    window['play_mode'].update(window['result_play_mode'].get())
    window['difficulty'].update(window['result_difficulty'].get())
    window['level'].update(window['result_level'].get())
    window['notes'].update(window['result_notes'].get())
    window['music'].update(window['result_music'].get())

    if window['result_graph'].get() != '':
        window[f"display_{window['result_graph'].get()}"].update(True)

    window['option_arrange'].update('')
    window['option_arrange_1p'].update('')
    window['option_arrange_2p'].update('')
    window['option_arrange_sync'].update('')
    if window['result_option_arrange'].get() in define.value_list['options_arrange']:
        window['option_arrange'].update(window['result_option_arrange'].get())
    if '/' in window['result_option_arrange'].get():
        left, right = window['result_option_arrange'].get().split('/')
        window['option_arrange_1p'].update(left)
        window['option_arrange_2p'].update(right)
    if window['result_option_arrange'].get() in define.value_list['options_arrange_sync']:
        window['option_arrange_sync'].update(window['result_option_arrange'].get())

    window['option_flip'].update(window['result_option_flip'].get())
    window['option_assist'].update(window['result_option_assist'].get())
    window['option_battle'].update(window['result_option_battle'].visible)
    window['clear_type_best'].update(window['result_clear_type_best'].get())
    window['clear_type_current'].update(window['result_clear_type_current'].get())
    window['clear_type_new'].update(window['result_clear_type_new'].visible)
    window['dj_level_best'].update(window['result_dj_level_best'].get())
    window['dj_level_current'].update(window['result_dj_level_current'].get())
    window['dj_level_new'].update(window['result_dj_level_new'].visible)
    window['score_best'].update(window['result_score_best'].get())
    window['score_current'].update(window['result_score_current'].get())
    window['score_new'].update(window['result_score_new'].visible)
    window['miss_count_best'].update(window['result_miss_count_best'].get())
    window['miss_count_current'].update(window['result_miss_count_current'].get())
    window['miss_count_new'].update(window['result_miss_count_new'].visible)
    window['graphtarget'].update(window['result_graphtarget'].get())

    window['music'].set_focus()

def set_labels(label):
    if not 'informations' in label.keys() or not 'details' in label.keys():
        window['play_mode'].update('')
        window['difficulty'].update('')
        window['level'].update('')
        window['notes'].update('')
        window['music'].update('')
        for key in ['default', 'lanes', 'measures']:
            window[f'display_{key}'].update(False)
        window['option_arrange'].update('')
        window['option_arrange_1p'].update('')
        window['option_arrange_2p'].update('')
        window['option_arrange_sync'].update('')
        window['option_flip'].update('')
        window['option_assist'].update('')
        window['option_battle'].update(False)
        window['clear_type_best'].update('')
        window['clear_type_current'].update('')
        window['clear_type_new'].update('')
        window['dj_level_best'].update('')
        window['dj_level_current'].update('')
        window['dj_level_new'].update('')
        window['score_best'].update('')
        window['score_current'].update('')
        window['score_new'].update('')
        window['miss_count_best'].update('')
        window['miss_count_current'].update('')
        window['miss_count_new'].update('')
        window['graphtarget'].update('')
        return

    window['has_informations'].update(label['informations'] is not None)
    switch_informations_controls()
    window['has_details'].update(label['details'] is not None)
    switch_details_controls()

    if label['informations'] is not None:
        window['play_mode'].update(label['informations']['play_mode'])
        window['difficulty'].update(label['informations']['difficulty'])
        window['level'].update(label['informations']['level'])
        window['notes'].update(label['informations']['notes'] if 'notes' in label['informations'] else '')
        window['music'].update(label['informations']['music'])
    else:
        window['play_mode'].update('')
        window['difficulty'].update('')
        window['level'].update('')
        window['notes'].update('')
        window['music'].update('')
    
    if label['details'] is not None:
        if label['details']['display'] != '':
            window[f"display_{label['details']['display']}"].update(True)
        window['option_battle'].update(label['details']['option_battle'])
        window['option_arrange'].update(label['details']['option_arrange'])
        left, right = label['details']['option_arrange_dp'].split('/')
        window['option_arrange_1p'].update(left)
        window['option_arrange_2p'].update(right)
        window['option_arrange_sync'].update(label['details']['option_arrange_sync'])
        window['option_flip'].update(label['details']['option_flip'])
        window['option_assist'].update(label['details']['option_assist'])
        window['option_battle'].update(label['details']['option_battle'])
        window['clear_type_best'].update(label['details']['clear_type_best'] if 'clear_type_best' in label['details'].keys() else '')
        window['clear_type_current'].update(label['details']['clear_type_current'])
        window['clear_type_new'].update(label['details']['clear_type_new'])
        window['dj_level_best'].update(label['details']['dj_level_best'] if 'dj_level_best' in label['details'].keys() else '')
        window['dj_level_current'].update(label['details']['dj_level_current'])
        window['dj_level_new'].update(label['details']['dj_level_new'])
        window['score_best'].update(label['details']['score_best'] if 'score_best' in label['details'].keys() else '')
        window['score_current'].update(label['details']['score_current'])
        window['score_new'].update(label['details']['score_new'])
        window['miss_count_best'].update(label['details']['miss_count_best'] if 'miss_count_best' in label['details'].keys() else '')
        window['miss_count_current'].update(label['details']['miss_count_current'])
        window['miss_count_new'].update(label['details']['miss_count_new'])
        window['graphtarget'].update(label['details']['graphtarget'] if 'graphtarget' in label['details'].keys() else '')
    else:
        for key in ['default', 'lanes', 'measures']:
            window[f'display_{key}'].update(False)
        window['option_arrange'].update('')
        window['option_arrange_1p'].update('')
        window['option_arrange_2p'].update('')
        window['option_arrange_sync'].update('')
        window['option_flip'].update('')
        window['option_assist'].update('')
        window['option_battle'].update(False)
        window['clear_type_best'].update('')
        window['clear_type_current'].update('')
        window['clear_type_new'].update('')
        window['dj_level_best'].update('')
        window['dj_level_current'].update('')
        window['dj_level_new'].update('')
        window['score_best'].update('')
        window['score_current'].update('')
        window['score_new'].update('')
        window['miss_count_best'].update('')
        window['miss_count_current'].update('')
        window['miss_count_new'].update('')
        window['graphtarget'].update('')

def switch_informations_controls():
    value = window['has_informations'].get()

    window['play_mode'].update(disabled=not value)
    window['difficulty'].update(disabled=not value)
    window['level'].update(disabled=not value)
    window['notes'].update(disabled=not value)
    window['music'].update(disabled=not value)

def switch_details_controls():
    value = window['has_details'].get()

    for key in ['default', 'lanes', 'measures']:
        window[f'display_{key}'].update(disabled=not value)
    window['option_arrange'].update(disabled=not value)
    window['option_arrange_1p'].update(disabled=not value)
    window['option_arrange_2p'].update(disabled=not value)
    window['option_arrange_sync'].update(disabled=not value)
    window['option_flip'].update(disabled=not value)
    window['option_assist'].update(disabled=not value)
    window['option_battle'].update(disabled=not value)
    window['clear_type_best'].update(disabled=not value)
    window['clear_type_current'].update(disabled=not value)
    window['clear_type_new'].update(disabled=not value)
    window['dj_level_best'].update(disabled=not value)
    window['dj_level_current'].update(disabled=not value)
    window['dj_level_new'].update(disabled=not value)
    window['score_best'].update(disabled=not value)
    window['score_current'].update(disabled=not value)
    window['score_new'].update(disabled=not value)
    window['miss_count_best'].update(disabled=not value)
    window['miss_count_current'].update(disabled=not value)
    window['miss_count_new'].update(disabled=not value)
    window['graphtarget'].update(disabled=not value)

def change_search_condition(keys, labels):
    if window['only_not_annotation'].get():
        keys = [key for key in keys if not key in labels.keys()]
    if window['only_undefined_music'].get():
        keys = [key for key in keys if key in labels.keys() and labels[key]['informations'] is not None and labels[key]['informations']['music'] == '']
    if window['only_full_combo'].get():
        keys = [key for key in keys if key in labels.keys() and labels[key]['details'] is not None and (('clear_type_best' in labels[key]['details'].keys() and labels[key]['details']['clear_type_best'] == 'F-COMBO') or labels[key]['details']['clear_type_current'] == 'F-COMBO')]
    window['list_keys'].update(keys)
