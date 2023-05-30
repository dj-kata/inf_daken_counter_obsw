import numpy as np
import json
from logging import getLogger
from os.path import exists

logger_child_name = 'recog'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded recog.py')

from define import define
from resources import recog_musics_filepath,load_resource_serialized,load_resource_numpy
from result import ResultInformations,ResultValues,ResultDetails,ResultOptions,Result

class Recog():
    def __init__(self, mask):
        self.mask = mask
    
    def find(self, image):
        np_trim = np.array(image)

        return self.mask.eval(np_trim)

class Recognition():
    def __init__(self):
        self.is_savable = load_resource_serialized('is_savable')
        self.play_side = load_resource_numpy('play_side')
        self.dead = load_resource_numpy('dead')
        self.rival = load_resource_numpy('rival')

        self.load_resource_informations()
        self.load_resource_details()

        self.musics = None
        self.load_resource_musics()
    
    def get_is_savable(self, np_value):
        define_result_check = define.result_check

        background_key = np_value[define_result_check['background_key_position']]
        if not background_key in self.is_savable.keys():
            return False

        for area_key, area in define_result_check['areas'].items():
            if not np.array_equal(np_value[area], self.is_savable[background_key][area_key]):
                return False
        
        return True
        
    def get_play_side(self, np_value):
        for target in define.value_list['play_sides']:
            trimmed = np_value[define.areas_np['play_side'][target]]
            if np.all((self.play_side==0)|(trimmed==self.play_side)):
                return target

        return None

    def get_has_dead(self, np_value, play_side):
        trimmed = np_value[define.areas_np['dead'][play_side]]
        if np.all((self.dead==0)|(trimmed==self.dead)):
            return True
        else:
            return False
    
    def get_has_rival(self, np_value):
        trimmed = np_value[define.areas_np['rival']]
        if np.all((self.rival==0)|(trimmed==self.rival)):
            return True
        else:
            return False
    
    def get_play_mode(self, np_value_informations):
        trimmed = np_value_informations[self.informations['play_mode']['trim']].flatten()
        bins = np.where(trimmed==self.informations['play_mode']['maskvalue'], 1, 0)
        hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        tablekey = ''.join([format(v, '0x') for v in hexs])
        if not tablekey in self.informations['play_mode']['table'].keys():
            return None
        return self.informations['play_mode']['table'][tablekey]

    def get_difficulty(self, np_value_informations):
        trimmed = np_value_informations[self.informations['difficulty']['trim']]
        uniques, counts = np.unique(trimmed, return_counts=True)
        difficultykey = uniques[np.argmax(counts)]
        if not difficultykey in self.informations['difficulty']['table']['difficulty'].keys():
            return None, None
        
        difficulty = self.informations['difficulty']['table']['difficulty'][difficultykey]

        leveltrimmed = trimmed[self.informations['difficulty']['trimlevel']].flatten()
        bins = np.where(leveltrimmed==difficultykey, 1, 0)
        hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        levelkey = ''.join([format(v, '0x') for v in hexs])

        if not levelkey in self.informations['difficulty']['table']['level'][difficulty].keys():
            return None, None
        
        level = self.informations['difficulty']['table']['level'][difficulty][levelkey]

        return difficulty, level

    def get_notes(self, np_value_informations):
        trimmed = np_value_informations[self.informations['notes']['trim']]
        splited = np.hsplit(trimmed, self.informations['notes']['digit'])

        value = 0
        pos = 3
        for pos in range(4):
            trimmed_once = splited[pos][self.informations['notes']['trimnumber']]
            bins = np.where(trimmed_once==self.informations['notes']['maskvalue'], 1, 0).flatten()
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs])
            if not tablekey in self.informations['notes']['table'].keys():
                if value != 0:
                    return None
                else:
                    continue
            
            value = value * 10 + self.informations['notes']['table'][tablekey]

        if value == 0:
            return None

        return value

    def get_music(self, image_informations):
        if self.musics is None:
            return None

        if self.backgrounds is None:
            return None
        
        background_key = str(image_informations.getpixel(self.background_key_position))
        if not background_key in self.backgrounds.keys():
            return None
        
        np_value = np.array(image_informations.crop(self.music_trimarea))
        background_removed = np.where(self.backgrounds[background_key]!=np_value, np_value, 0)
        gray_filtered = np.where(background_removed>=self.gray_filter, background_removed, 0)

        masked = np.where(self.mask, 0, gray_filtered)

        maxcounts = []
        maxcount_values = []
        for line in masked:
            unique, counts = np.unique(line, return_counts=True)
            if len(counts) != 1:
                index = -np.argmax(np.flip(counts[1:])) - 1
                maxcounts.append(counts[index])
                maxcount_values.append(unique[index])
            else:
                maxcounts.append(0)
                maxcount_values.append(0)

        target = self.music_recognition
        for y in np.argsort(maxcounts)[::-1]:
            color = int(maxcount_values[y])
            bins = np.where(masked[y]==color, 1, 0)
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            mapkey = f"{y:02d}{''.join([format(v, '0x') for v in hexs])}"
            if not mapkey in target:
                return None
            if type(target[mapkey]) == str:
                return target[mapkey]
            target = target[mapkey]
        
        return None

    def get_music_new(self, np_value_informations):
        trimmed = np_value_informations[self.informations['music']['trim']]

        blue = np.where(trimmed[:,:,2]==self.informations['music']['bluevalue'],trimmed[:,:,2],0)
        gray1 = np.where((trimmed[:,:,0]==trimmed[:,:,1])&(trimmed[:,:,0]==trimmed[:,:,2]),trimmed[:,:,0],0)
        gray = np.where((gray1!=255)&(gray1>self.informations['music']['gray_threshold']),gray1,0)

        if np.count_nonzero(gray) > np.count_nonzero(blue):
            masked = np.where(self.informations['music']['mask']['gray']==1,gray,0)
            targettable = self.informations['music']['table']['gray']
        else:
            masked = np.where(self.informations['music']['mask']['blue']==1,blue,0)
            targettable = self.informations['music']['table']['blue']
        
        maxcounts = []
        maxcount_values = []
        for line in masked:
            unique, counts = np.unique(line, return_counts=True)
            if len(counts) != 1:
                index = -np.argmax(np.flip(counts[1:])) - 1
                maxcounts.append(counts[index])
                maxcount_values.append(unique[index])
            else:
                maxcounts.append(0)
                maxcount_values.append(0)

        for y in np.argsort(maxcounts)[::-1]:
            color = int(maxcount_values[y])
            bins = np.where(masked[y]==color, 1, 0)
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            mapkey = f"{y:02d}{color:02x}{''.join([format(v, '0x') for v in hexs])}"
            if not mapkey in targettable:
                return None
            if type(targettable[mapkey]) == str:
                return targettable[mapkey]
            targettable = targettable[mapkey]
        
        return None

    def get_options(self, np_value):
        trimmed = np_value[self.details['define']['option']['trim']]

        def generatekey(np_value):
            bins = np.where(np_value==self.details['define']['option']['maskvalue'], 1, 0)
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            return ''.join([format(v, '0x') for v in hexs.flatten()])

        arrange = None
        flip = None
        assist = None
        battle = False
        while True:
            tablekey = generatekey(trimmed[:, :self.details['option']['lengths'][0]*8:2])
            value = None
            for length in self.details['option']['lengths']:
                if tablekey[:length] in self.details['option'].keys():
                    value = self.details['option'][tablekey[:length]]
                    break
            
            if value is None:
                break

            arrange_dp_left = False
            if value in define.value_list['options_arrange']:
                arrange = value
            if value in define.value_list['options_arrange_dp']:
                if arrange is None:
                    arrange = f'{value}/'
                    arrange_dp_left = True
                else:
                    arrange += value
            if value in define.value_list['options_arrange_sync']:
                arrange = value
            if value in define.value_list['options_flip']:
                flip = value
            if value in define.value_list['options_assist']:
                assist = value
            if value == 'BATTLE':
                battle = True
            if not arrange_dp_left:
                trimmed = trimmed[:, self.details['define']['option']['width'][value] + self.details['define']['option']['width'][',']:]
            else:
                trimmed = trimmed[:, self.details['define']['option']['width'][value] + self.details['define']['option']['width']['/']:]
        
        return ResultOptions(arrange, flip, assist, battle)

    def get_graphtype(self, np_value):
        for key, value in self.details['graphtype'].items():
            trimmed = np_value[self.details['define']['graphtype'][key]]
            if np.all(trimmed==value):
                return key
        return 'gauge'

    def get_clear_type(self, np_value):
        result = {'best': None, 'current': None}
        for key in result.keys():
            trimmed = np_value[self.details['define']['clear_type'][key]]
            uniques, counts = np.unique(trimmed, return_counts=True)
            color = uniques[np.argmax(counts)]
            if color in self.details['clear_type'].keys():
                result[key] = self.details['clear_type'][color]
        
        trimmed = np_value[self.details['define']['clear_type']['new']]
        if np.all((self.details['not_new']==0)|(trimmed==self.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(result['best'], result['current'], isnew)

    def get_dj_level(self, np_value):
        result = {'best': None, 'current': None}
        for key in result.keys():
            trimmed = np_value[self.details['define']['dj_level'][key]]
            count = np.count_nonzero(trimmed==self.details['define']['dj_level']['maskvalue'])
            if count in self.details['dj_level'].keys():
                result[key] = self.details['dj_level'][count]
        
        trimmed = np_value[self.details['define']['dj_level']['new']]
        if np.all((self.details['not_new']==0)|(trimmed==self.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(result['best'], result['current'], isnew)

    def get_score(self, np_value):
        trimmed = np_value[self.details['define']['score']['best']]
        best = None
        for dig in range(self.details['define']['score']['digit']):
            splitted = np.hsplit(trimmed, self.details['define']['score']['digit'])
            trimmed_once = splitted[-(dig+1)][self.details['define']['numberbest']['trim']]
            bins = np.where(trimmed_once==self.details['define']['numberbest']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in self.details['number_best'].keys():
                break
            if best is None:
                best = 0
            best += 10 ** dig * self.details['number_best'][tablekey]

        trimmed = np_value[self.details['define']['score']['current']]
        current = None
        for dig in range(self.details['define']['score']['digit']):
            splitted = np.hsplit(trimmed, self.details['define']['score']['digit'])
            trimmed_once = splitted[-(dig+1)][self.details['define']['numbercurrent']['trim']]
            bins = np.where(trimmed_once==self.details['define']['numbercurrent']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in self.details['number_current'].keys():
                break
            if current is None:
                current = 0
            current += 10 ** dig * self.details['number_current'][tablekey]
        
        trimmed = np_value[self.details['define']['score']['new']]
        if np.all((self.details['not_new']==0)|(trimmed==self.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(best, current, isnew)

    def get_miss_count(self, np_value):
        trimmed = np_value[self.details['define']['miss_count']['best']]
        best = None
        for dig in range(self.details['define']['miss_count']['digit']):
            splitted = np.hsplit(trimmed, self.details['define']['miss_count']['digit'])
            trimmed_once = splitted[-(dig+1)][self.details['define']['numberbest']['trim']]
            bins = np.where(trimmed_once==self.details['define']['numberbest']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in self.details['number_best'].keys():
                break
            if best is None:
                best = 0
            best += 10 ** dig * self.details['number_best'][tablekey]

        trimmed = np_value[self.details['define']['miss_count']['current']]
        current = None
        for dig in range(self.details['define']['miss_count']['digit']):
            splitted = np.hsplit(trimmed, self.details['define']['miss_count']['digit'])
            trimmed_once = splitted[-(dig+1)][self.details['define']['numbercurrent']['trim']]
            bins = np.where(trimmed_once==self.details['define']['numbercurrent']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in self.details['number_current'].keys():
                break
            if current is None:
                current = 0
            current += 10 ** dig * self.details['number_current'][tablekey]
        
        trimmed = np_value[self.details['define']['miss_count']['new']]
        if np.all((self.details['not_new']==0)|(trimmed==self.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(best, current, isnew)
    
    def get_graphtarget(self, np_value):
        trimmed = np_value[self.details['define']['graphtarget']['trimmode']]
        uniques, counts = np.unique(trimmed, return_counts=True)
        mode = uniques[np.argmax(counts)]
        if not mode in self.details['graphtarget'].keys():
            return None
        
        trimmed = np_value[self.details['define']['graphtarget']['trimkey']]
        bins = np.where(trimmed==mode, 1, 0)
        hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        tablekey = ''.join([format(v, '0x') for v in hexs])
        if not tablekey in self.details['graphtarget'][mode].keys():
            return None
        
        return self.details['graphtarget'][mode][tablekey]

    def check_newrecognition(self, result, np_value):
        if self.informations is None:
            return True
        
        np_value_informations = np_value[define.areas_np['informations']]
        music = self.get_music_new(np_value_informations)
        
        if result.informations.music != music:
            print(f'mismatch music {result.informations.music} {music}')
            return False

        return True

    def get_informations(self, np_value):
        play_mode = self.get_play_mode(np_value)
        difficulty, level = self.get_difficulty(np_value)
        notes = self.get_notes(np_value)
        music = self.get_music_new(np_value)

        return ResultInformations(play_mode, difficulty, level, notes, music)

    def get_details(self, np_value):
        graphtype = self.get_graphtype(np_value)
        if graphtype == 'gauge':
            options = self.get_options(np_value)
        else:
            options = None

        clear_type = self.get_clear_type(np_value)
        dj_level = self.get_dj_level(np_value)
        score = self.get_score(np_value)
        miss_count = self.get_miss_count(np_value)
        graphtarget = self.get_graphtarget(np_value)

        return ResultDetails(graphtype, options, clear_type, dj_level, score, miss_count, graphtarget)

    def get_result(self, screen):
        play_side = self.get_play_side(screen.np_value)
        if play_side == None:
            return None

        result = Result(
            screen.original,
            self.get_informations(screen.np_value[define.areas_np['informations']]),
            play_side,
            self.get_has_rival(screen.np_value),
            self.get_has_dead(screen.np_value, play_side),
            self.get_details(screen.np_value[define.areas_np['details'][play_side]])
        )
    
        if result.informations.music is None:
            monochrome = screen.original.convert('L')
            trim_informations = monochrome.crop(define.informations_trimarea)
            result.informations.music = self.get_music(trim_informations)

        return result
    
    def load_resource_musics(self):
        if not exists(recog_musics_filepath):
            return
        
        with open(recog_musics_filepath) as f:
            resource = json.load(f)
        
        self.music_trimarea = tuple(resource['define']['trimarea'])
        self.background_key_position = tuple(resource['define']['background_key_position'])

        self.backgrounds = {}
        for background_key in resource['backgrounds'].keys():
            self.backgrounds[background_key] = np.array(resource['backgrounds'][background_key])
        
        trimarea = resource['define']['trimarea']
        width = trimarea[2] - trimarea[0]
        self.gray_filter = np.tile(np.array(resource['define']['gray_thresholds']), (width, 1)).T

        self.mask = np.array(resource['mask'])
        
        self.music_recognition = resource['recognition']

        self.musics = resource['musics']
    
    def load_resource_informations(self):
        resourcename = f'informations{define.informations_recognition_version}'
        
        self.informations = load_resource_serialized(resourcename)

    def load_resource_details(self):
        resourcename = f'details{define.details_recognition_version}'
        
        self.details = load_resource_serialized(resourcename)

recog = Recognition()
