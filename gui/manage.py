import PySimpleGUI as sg
import io
from PIL import Image

from define import define
from resources import masks
from recog import recog
from .static import title,icon_path,background_color,in_area_background_color

default_box = (0, 0, 1280, 720)
scales = ['1/1', '1/2', '1/4']

def layout_manage(filenames):
    areas_firstkeys = [*define.areas.keys()]

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
        'BATTLE',
        'H-RANDOM'
    ]
    selectable_value_list['delimita'] = ['', ',', '/']

    images = {}
    for key in masks.keys():
        bytes = io.BytesIO()
        image = Image.fromarray(masks[key].value)
        image.save(bytes, format='PNG')
        images[key] = bytes.getvalue()

    area_define = [
        [
            sg.Text('領域', size=(12, 1)),
            sg.Column([
                [sg.Combo(areas_firstkeys, key='area_top', size=(11, 1), readonly=True, enable_events=True)],
                [sg.Combo([], key='area_second', size=(13, 1), readonly=True, enable_events=True)]
            ], pad=0, background_color=in_area_background_color)
        ],
        [
            sg.Text('オプション幅', size=(12, 1)),
            sg.Column([
                [
                    sg.Combo(selectable_value_list['all_options'], key='area_option1', size=(11, 1), readonly=True, enable_events=True),
                    sg.Combo(selectable_value_list['delimita'], key='area_delimita1', size=(2, 1), readonly=True, enable_events=True)
                ],
                [
                    sg.Combo(selectable_value_list['all_options'], key='area_option2', size=(11, 1), readonly=True, enable_events=True),
                    sg.Combo(selectable_value_list['delimita'], key='area_delimita2', size=(2, 1), readonly=True, enable_events=True)
                ],
                [
                    sg.Combo(selectable_value_list['all_options'], key='area_option3', size=(11, 1), readonly=True, enable_events=True),
                    sg.Combo(selectable_value_list['delimita'], key='area_delimita3', size=(2, 1), readonly=True, enable_events=True)
                ]
            ], pad=0, background_color=in_area_background_color),
        ],
        [
            sg.Text('X1', size=(2, 1)), sg.Input(default_box[0], key='left', size=(4, 1)),
            sg.Text('Y1', size=(2, 1)), sg.Input(default_box[1], key='top', size=(4, 1))
        ],
        [
            sg.Text('X2', size=(2, 1)), sg.Input(default_box[2], key='right', size=(4, 1)),
            sg.Text('Y2', size=(2, 1)), sg.Input(default_box[3], key='bottom', size=(4, 1))
        ],
        [sg.Button('トリム', key='button_trim')],
        [sg.Image(key='trim', background_color=background_color)]
    ]

    manage_label_define = [
        [
            sg.Text('画面', size=(40, 1)),
        ],
        [
            sg.Column([
                [sg.Radio('なし', key='screen_none', group_id='screen', background_color=in_area_background_color)],
                [sg.Radio('ローディング', key='screen_loading', group_id='screen', background_color=in_area_background_color)]
            ], pad=0, background_color=in_area_background_color),
            sg.Column([
                [sg.Radio('選曲', key='screen_music_select', group_id='screen', background_color=in_area_background_color)],
                [sg.Radio('プレイ中', key='screen_playing', group_id='screen', background_color=in_area_background_color)],
                [sg.Radio('リザルト', key='screen_result', group_id='screen', background_color=in_area_background_color, default=True)]
            ], pad=0, background_color=in_area_background_color)
        ],
        [
            sg.Text('リザルト判定', size=(16, 1)),
            sg.Checkbox('認識可能', key='trigger', default=True, background_color=in_area_background_color)
        ],
        [
            sg.Text('カットイン', size=(16, 1)),
            sg.Checkbox('ミッション', key='cutin_mission', background_color=in_area_background_color),
            sg.Checkbox('ビット獲得', key='cutin_bit', background_color=in_area_background_color)
        ],
        [
            sg.Text('ライバル挑戦状', size=(16, 1)),
            sg.Checkbox('表示あり', key='rival', default=False, background_color=in_area_background_color)
        ],
        [
            sg.Text('リザルト', size=(16, 1)),
            sg.Text('モード', background_color=in_area_background_color),
            sg.Combo(['', 'SP', 'DP'], key='play_mode'),
            sg.Text('サイド', background_color=in_area_background_color),
            sg.Combo(['', '1P', '2P'], key='play_side')
        ],
        [
            sg.Text('途中落ち', size=(16, 1)),
            sg.Checkbox('表示あり', key='dead', default=False, background_color=in_area_background_color)
        ],
        [
            sg.Button('アノテーション保存', key='button_label_overwrite'),
            sg.Button('認識結果から引用', key='button_feedback')
        ]
    ]

    manage_result = [
        [
            sg.Text('サイズ', size=(12, 1)),
            sg.Text(key='screen_size', background_color=in_area_background_color)
        ],
        [sg.Text('検出画像', size=(30, 1), justification='center', pad=1)],
        [
            sg.Text('Loading', size=(7, 1), justification='center', pad=1),
            sg.Text('Select', size=(7, 1), justification='center', pad=1),
            sg.Text('Playing', size=(7, 1), justification='center', pad=1),
            sg.Text('Result', size=(7, 1), justification='center', pad=1)
        ],
        [
            sg.Text(key='recog_loading', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color),
            sg.Text(key='recog_music_select', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color),
            sg.Text(key='recog_playing', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color),
            sg.Text(key='recog_result', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color)
        ],
        [sg.Text('リザルト認識', size=(30, 1), justification='center', pad=1)],
        [
            sg.Text('EXTRA', size=(7, 1), justification='center', pad=1),
            sg.Text('mission', size=(7, 1), justification='center', pad=1),
            sg.Text('bit', size=(7, 1), justification='center', pad=1),
            sg.Text('Rival', size=(7, 1), justification='center', pad=1)
        ],
        [
            sg.Text(key='recog_trigger', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color),
            sg.Text(key='recog_cutin_mission', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color),
            sg.Text(key='recog_cutin_bit', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color),
            sg.Text(key='recog_rival', size=(7, 1), justification='center', pad=1, background_color=in_area_background_color)
        ],
        [
            sg.Text('プレイサイド', size=(20, 1)),
            sg.Text(key='recog_play_side', background_color=in_area_background_color)
        ],
        [
            sg.Text('途中落ち', size=(20, 1)),
            sg.Text(key='recog_dead', background_color=in_area_background_color)
        ]
    ]

    return [
        [
            sg.Column([
                [
                    sg.Column([
                        [
                            sg.Text('画像表示スケール', background_color=background_color),
                            sg.Combo(scales, default_value='1/2', readonly=True, key='scale')
                        ],
                        [sg.Image(key='screenshot', size=(640, 360), background_color=background_color)]
                    ], pad=0, background_color=background_color),
                    sg.Listbox(filenames, key='list_screens', size=(27, 20), enable_events=True),
                    sg.Column([
                        [sg.Radio('すべて', default=True, key='search_all', group_id='search', enable_events=True, background_color=background_color)],
                        [sg.Radio('選曲のみ', key='search_only_music_select', group_id='search', enable_events=True, background_color=background_color)],
                        [sg.Radio('プレイ中のみ', key='search_only_playing', group_id='search', enable_events=True, background_color=background_color)],
                        [sg.Radio('リザルトのみ', key='search_only_result', group_id='search', enable_events=True, background_color=background_color)]
                    ], pad=0, background_color=background_color)
                ],
                [
                    sg.Column(area_define, size=(300, 350), background_color=in_area_background_color),
                    sg.Column(manage_label_define, size=(420, 350), background_color=in_area_background_color),
                    sg.Column(manage_result, size=(300, 350), background_color=in_area_background_color)
                ],
            ], pad=0, background_color=background_color)
        ],
    ]

def generate_window(filenames):
    global window

    window = sg.Window(
        title,
        layout_manage(filenames),
        icon=icon_path,
        grab_anywhere=True,
        return_keyboard_events=True,
        resizable=False,
        finalize=True,
        enable_close_attempted_event=True,
        background_color=background_color
    )

    window['area_second'].update(visible=False)
    window['area_option1'].update(visible=False)
    window['area_delimita1'].update(visible=False)
    window['area_option2'].update(visible=False)
    window['area_delimita2'].update(visible=False)
    window['area_option3'].update(visible=False)
    window['area_delimita3'].update(visible=False)

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

def display_image(image):
    scale = window['scale'].get()
    if scale == '1/2':
        image = image.resize((image.width // 2, image.height // 2))
    if scale == '1/4':
        image = image.resize((image.width // 3, image.height // 3))
    
    bytes = io.BytesIO()
    image.save(bytes, format='PNG')

    window['screenshot'].update(size=image.size, data=bytes.getvalue())

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

def feedback():
    if window['recog_loading'].get() != '':
        window['screen_loading'].update(True)
    if window['recog_music_select'].get() != '':
        window['screen_music_select'].update(True)
    if window['recog_result'].get() != '':
        window['screen_result'].update(True)
    window['trigger'].update(window['recog_trigger'].get() != '')
    window['cutin_mission'].update(window['recog_cutin_mission'].get() != '')
    window['cutin_bit'].update(window['recog_cutin_bit'].get() != '')
    window['rival'].update(window['recog_rival'].get() != '')
    window['play_side'].update(window['recog_play_side'].get())
    window['dead'].update(window['recog_dead'].get() != '')

def set_labels(label):
    window['screen_none'].update(True)
    window['trigger'].update(True)
    window['cutin_mission'].update(False)
    window['cutin_bit'].update(False)
    window['rival'].update(False)
    window['play_side'].update('')
    window['play_mode'].update('')
    window['dead'].update(False)
    if not label is None:
        if 'screen' in label.keys():
            window[f"screen_{label['screen']}"].update(True)
        if 'trigger' in label.keys():
            window['trigger'].update(label['trigger'])
        if 'cutin_mission' in label.keys():
            window['cutin_mission'].update(label['cutin_mission'])
        if 'cutin_bit' in label.keys():
            window['cutin_bit'].update(label['cutin_bit'])
        if 'rival' in label.keys():
            window['rival'].update(label['rival'])
        if 'play_side' in label.keys():
            window['play_side'].update(label['play_side'])
        if 'play_mode' in label.keys():
            window['play_mode'].update(label['play_mode'])
        if 'dead' in label.keys():
            window['dead'].update(label['dead'])

def set_recognition(screen):
    width, height = screen.original.size
    window['screen_size'].update(f'{width} x {height}')

    loading = recog.get_is_screen_loading(screen.original)
    music_select = recog.get_is_screen_music_select(screen.original)
    playing = recog.get_is_screen_playing(screen.original)
    result = recog.get_is_screen_result(screen.original)

    trigger = recog.get_has_trigger(screen.monochrome)
    cutin_mission = recog.get_has_cutin_mission(screen.monochrome)
    cutin_bit = recog.get_has_cutin_bit(screen.monochrome)
    rival = recog.get_has_rival(screen.monochrome)

    play_side = recog.get_play_side(screen.monochrome)
    if play_side is not None:
        dead = recog.get_has_dead(screen.monochrome, play_side)
    else:
        dead = False

    window['recog_loading'].update('☒' if loading else '')
    window['recog_music_select'].update('☒' if music_select else '')
    window['recog_playing'].update('☒' if playing else '')
    window['recog_result'].update('☒' if result else '')

    window['recog_trigger'].update('☒' if trigger else '')
    window['recog_cutin_mission'].update('☒' if cutin_mission else '')
    window['recog_cutin_bit'].update('☒' if cutin_bit else '')
    window['recog_rival'].update('☒' if rival else '')

    window['recog_play_side'].update(play_side if play_side is not None else '')
    window['recog_dead'].update('☒' if dead else '')
