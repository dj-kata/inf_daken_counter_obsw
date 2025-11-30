from logging import getLogger
import numpy as np

logger_child_name = 'define'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded define.py')

class Playmodes():
    '''プレイモード

    SP と DP
    '''
    SP: str = 'SP'
    '''SINGLE PLAY'''

    DP: str = 'DP'
    '''DOUBLE PLAY'''

    values: list[str] = [SP, DP]
    '''プレイモードのリスト'''

class Playtypes():
    '''プレイの種類

    プレイモードにDP BATTLEを加えたもの
    '''
    DPBATTLE: str = 'DP BATTLE'
    '''DOUBLE PLAY BATTLE'''

    values: list[str] = [Playmodes.SP, Playmodes.DP, DPBATTLE]
    '''プレイの種類のリスト'''

class Define():
    width = 1920
    height = 1080

    screens = {
        'loading': {
            'left': 380,
            'top': 120,
            'width': 8,
            'height': 2,
        },
        'result': {
            'left': 1110,
            'top': 1042,
            'width': 4,
            'height': 2,
        },
        'music_select': {
            'left': 181,
            'top': 84,
            'width': 4,
            'height': 2,
        }
    }

    result_check = {
        "horizontalline": (60, slice(156, 390), 1),
        "verticalline": (slice(550, 760), 788, 1),
    }

    value_list = {
        'difficulties': ('BEGINNER', 'NORMAL', 'HYPER', 'ANOTHER', 'LEGGENDARIA',),
        'levels': ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12',),
        'dj_levels': ('F', 'E', 'D', 'C', 'B', 'A', 'AA', 'AAA',),
        'play_sides': ('1P', '2P',),
        'options_arrange': ('RANDOM', 'R-RANDOM', 'S-RANDOM', 'MIRROR', 'H-RANDOM',),
        'options_arrange_dp': ('OFF', 'RAN', 'R-RAN', 'S-RAN', 'MIR', 'H-RAN',),
        'options_arrange_sync': ('SYNC-RAN', 'SYMM-RAN',),
        'options_flip': ('FLIP',),
        'options_assist': ('A-SCR', 'LEGACY',),
        'clear_types': ('NO PLAY', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO',),
        'graphtargets': ('no graph', 'personal best score only', 'national best', 'national average', 'prefecture best', 'prefecture average', 'same class best', 'same class average', 'rival', 'rival best', 'rival average', 'pacemaker',),
        'notesradar_attributes': ('NOTES', 'CHORD', 'PEAK', 'CHARGE', 'SCRATCH', 'SOF-LAN',),
    }

    informations_trimpos = (560, 910)
    informations_trimsize = (800, 156)

    informations_recognition_version = '4.0'
    informations_trimarea = (560, 910, 1360, 1066)

    details_recognition_version = '3.0'

    details_trimpos = {
        '1P': (10, 64),
        '2P': (1360, 64),
    }

    details_trimsize = (554, 952)

    details_playside_area = 5, slice(4, 548, 8), 0
    details_playside = {
        '0fffffffffffffffe': '1P',
        '7fffffffffffffff0': '2P'
    }
    details_graphtarget_name_area = (210, 622, 300, 644)

    musictable_version = '1.1'
    
    musicselect_recognition_version = '2.2'
    musicselect_trimarea = (48, 135, 1188, 952)
    musicselect_trimarea_np = (
        (slice(musicselect_trimarea[1], musicselect_trimarea[3])),
        (slice(musicselect_trimarea[0], musicselect_trimarea[2])),
    )

    musicselect_rivals_name_area = (760, 634, 856, 808)

    notesradar_version = '1.0'

    filter_ranking_size = (526, 626)
    filter_ranking_compact_size = (97, 20)
    filter_ranking_position = {
        '1P': (1372, 264),
        '2P': (32, 264),
    }
    filter_ranking_compact_positions = {
        'left': {'1P': 1494, '2P': 154},
        'tops': (287, 393, 499, 605, 711, 817, ),
    }

    filter_areas = {
        'ranking': {},
        'ranking_compact': {},
        'graphtarget_name': {},
        'loveletter': (820, 700, 1102, 912),
        'loveletter_compact': (880, 777, 978, 800),
    }

    overlay = {
        'rival': {
            'positions': {
                '1P': (1370, 270),
                '2P': (30, 270),
            },
            'width': 530,
        },
        'loveletter': {
            'position': (820, 700),
            'width': 280,
        },
        'rivalname': {
            'positions': {},
            'width': 90,
        },
    }

    areas_np = {
        'rival': (slice(858, 872), slice(842, 920), 0),
        'play_side': {
            '1P': (slice(26, 30), slice(20, 24), 0),
            '2P': (slice(26, 30), slice(1860, 1864), 0),
        },
        'dead': {
            '1P': (slice(300, 304), slice(573, 576), 0),
            '2P': (slice(300, 304), slice(1145, 1148), 0),
        },
        'informations': (slice(910, 1066), slice(560, 1360)),
        'details': {
            '1P': (slice(64, 1016), slice(10, 564)),
            '2P': (slice(64, 1016), slice(1360, 1914)),
        },
    }

    def __init__(self):
        self.informations_resourcename = f'informations{self.informations_recognition_version}'
        self.details_resourcename = f'details{self.details_recognition_version}'
        self.musictable_resourcename = f'musictable{self.musictable_version}'
        self.musicselect_resourcename = f'musicselect{self.musicselect_recognition_version}'
        self.notesradar_resourcename = f'notesradar{self.notesradar_version}'

        self.details_trimarea = {}
        for play_side in self.details_trimpos.keys():
            self.details_trimarea[play_side] = (
                self.details_trimpos[play_side][0],
                self.details_trimpos[play_side][1],
                self.details_trimpos[play_side][0] + self.details_trimsize[0],
                self.details_trimpos[play_side][1] + self.details_trimsize[1]
            )

        for key in self.filter_ranking_position.keys():
            self.filter_areas['ranking'][key] = (
                self.filter_ranking_position[key][0],
                self.filter_ranking_position[key][1],
                self.filter_ranking_position[key][0] + self.filter_ranking_size[0],
                self.filter_ranking_position[key][1] + self.filter_ranking_size[1]
            )
        
        for playside in self.filter_ranking_compact_positions['left'].keys():
            left = self.filter_ranking_compact_positions['left'][playside]
            self.filter_areas['ranking_compact'][playside] = []
            for top in self.filter_ranking_compact_positions['tops']:
                self.filter_areas['ranking_compact'][playside].append((
                    left,
                    top,
                    left + self.filter_ranking_compact_size[0],
                    top + self.filter_ranking_compact_size[1]
                ))

        for key in self.details_trimpos.keys():
            self.filter_areas['graphtarget_name'][key] = (
                self.details_trimpos[key][0] + self.details_graphtarget_name_area[0],
                self.details_trimpos[key][1] + self.details_graphtarget_name_area[1],
                self.details_trimpos[key][0] + self.details_graphtarget_name_area[2],
                self.details_trimpos[key][1] + self.details_graphtarget_name_area[3]
            )
        
            self.overlay['rivalname']['positions'][key] = (
                self.details_trimpos[key][0] + self.details_graphtarget_name_area[0],
                self.details_trimpos[key][1] + self.details_graphtarget_name_area[1],
            )

    def details_get_playside(self, np_value):
        trimmed = np_value[self.details_playside_area]
        bins = np.where(trimmed==150, 1, 0)
        hexs = bins[0::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        playsidekey = ''.join([format(v, '0x') for v in hexs.flatten()])
        if not playsidekey in self.details_playside.keys():
            return None
        return self.details_playside[playsidekey]

define = Define()
