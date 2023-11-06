from logging import getLogger

logger_child_name = 'define'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded define.py')

class Define():
    width = 1280
    height = 720

    # 幅は8の倍数でないとだめかも
    get_screen_area = {
        'left': 782,
        'top': 690,
        'width': 8,
        'height': 2
    }

    result_check = {
        'background_count': 13,
        'background_key_position': (641, 410, 1),
        'areas': {
            "heightline1": (slice(5, 150), 420, 1),
            "heightline2": (slice(235, 630), 420, 1)
        }
    }

    value_list = {
        'play_modes': ('SP', 'DP',),
        'difficulties': ('BEGINNER', 'NORMAL', 'HYPER', 'ANOTHER', 'LEGGENDARIA',),
        'levels': ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12',),
        'dj_levels': ('F', 'E', 'D', 'C', 'B', 'A', 'AA', 'AAA',),
        'play_sides': ('1P', '2P',),
        'options_arrange': ('RANDOM', 'S-RANDOM', 'R-RANDOM', 'MIRROR', 'H-RANDOM',),
        'options_arrange_dp': ('OFF', 'RAN', 'S-RAN', 'R-RAN', 'MIR', 'H-RAN',),
        'options_arrange_sync': ('SYNC-RAN', 'SYMM-RAN',),
        'options_flip': ('FLIP',),
        'options_assist': ('A-SCR', 'LEGACY',),
        'clear_types': ('NO PLAY', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO'),
        'graphtargets': ('no graph', 'personal best score only', 'national best', 'national average', 'prefecture best', 'prefecture average', 'same class best', 'same class average', 'rival', 'rival best', 'rival average', 'pacemaker')
    }

    areas_np = {
        'rival': (slice(578, 592), slice(542, 611), 0),
        'play_side': {
            '1P': (slice(17, 26), slice(36, 46), 0),
            '2P': (slice(17, 26), slice(1212, 1222), 0)
        },
        'dead': {
            '1P': (slice(168, 178), slice(406, 412), 0),
            '2P': (slice(168, 178), slice(822, 828), 0)
        },
        'informations': (slice(628, 706), slice(410, 870)),
        'details': {
            '1P': (slice(192, 485), slice(25, 375)),
            '2P': (slice(192, 485), slice(905, 1255))
        }    }

    informations_trimpos = (410, 633)
    informations_trimsize = (460, 71)

    informations_recognition_version = '2.1'
    informations_trimarea = (410, 628, 870, 706)

    informations_areas = {
        'play_mode': (82, 55, 102, 65),
        'difficulty': (196, 58, 229, 62),
        'level': (231, 58, 250, 62),
        'notes': (268, 59, 324, 61)
    }

    details_recognition_version = '1.0'

    details_trimpos = {
        '1P': (25, 192),
        '2P': (905, 192),
    }

    details_trimsize = (350, 293)

    details_graphtarget_name_area = (121, 265, 196, 283)

    musictable_version = '1.0'
    
    filter_ranking_size = (386, 504)
    filter_ranking_position = {
        '1P': (876, 175),
        '2P': (20, 175)
    }

    filter_areas = {
        'ranking': {},
        'graphtarget_name': {},
        'loveletter': (527, 449, 760, 623)
    }

    def __init__(self):
        self.informations_resourcename = f'informations{self.informations_recognition_version}'
        self.details_resourcename = f'details{self.details_recognition_version}'
        self.musictable_resourcename = f'musictable{self.musictable_version}'

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

        for key in self.details_trimpos.keys():
            self.filter_areas['graphtarget_name'][key] = (
                self.details_trimpos[key][0] + self.details_graphtarget_name_area[0],
                self.details_trimpos[key][1] + self.details_graphtarget_name_area[1],
                self.details_trimpos[key][0] + self.details_graphtarget_name_area[2],
                self.details_trimpos[key][1] + self.details_graphtarget_name_area[3]
            )

define = Define()
