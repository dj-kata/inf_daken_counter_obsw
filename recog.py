import numpy as np
from logging import getLogger

logger_child_name = 'recog'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded recog.py')

from define import define
from resources import resource
from result import ResultInformations,ResultValues,ResultDetails,ResultOptions,Result

class Recog():
    def __init__(self, mask):
        self.mask = mask
    
    def find(self, image):
        np_trim = np.array(image)

        return self.mask.eval(np_trim)

class Recognition():
    def get_is_savable(self, np_value):
        define_result_check = define.result_check

        background_key = np_value[define_result_check['background_key_position']]
        if not background_key in resource.is_savable.keys():
            return False

        for area_key, area in define_result_check['areas'].items():
            if not np.array_equal(np_value[area], resource.is_savable[background_key][area_key]):
                return False
        
        return True
        
    def get_play_side(self, np_value):
        for target in define.value_list['play_sides']:
            trimmed = np_value[define.areas_np['play_side'][target]]
            if np.all((resource.play_side==0)|(trimmed==resource.play_side)):
                return target

        return None

    def get_has_dead(self, np_value, play_side):
        trimmed = np_value[define.areas_np['dead'][play_side]]
        if np.all((resource.dead==0)|(trimmed==resource.dead)):
            return True
        else:
            return False
    
    def get_has_rival(self, np_value):
        trimmed = np_value[define.areas_np['rival']]
        if np.all((resource.rival==0)|(trimmed==resource.rival)):
            return True
        else:
            return False
    
    def get_play_mode(self, np_value_informations):
        trimmed = np_value_informations[resource.informations['play_mode']['trim']].flatten()
        bins = np.where(trimmed==resource.informations['play_mode']['maskvalue'], 1, 0)
        hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        tablekey = ''.join([format(v, '0x') for v in hexs])
        if not tablekey in resource.informations['play_mode']['table'].keys():
            return None
        return resource.informations['play_mode']['table'][tablekey]

    def get_difficulty(self, np_value_informations):
        trimmed = np_value_informations[resource.informations['difficulty']['trim']]
        uniques, counts = np.unique(trimmed, return_counts=True)
        difficultykey = uniques[np.argmax(counts)]
        if not difficultykey in resource.informations['difficulty']['table']['difficulty'].keys():
            return None, None
        
        difficulty = resource.informations['difficulty']['table']['difficulty'][difficultykey]

        leveltrimmed = trimmed[resource.informations['difficulty']['trimlevel']].flatten()
        bins = np.where(leveltrimmed==difficultykey, 1, 0)
        hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        levelkey = ''.join([format(v, '0x') for v in hexs])

        if not levelkey in resource.informations['difficulty']['table']['level'][difficulty].keys():
            return None, None
        
        level = resource.informations['difficulty']['table']['level'][difficulty][levelkey]

        return difficulty, level

    def get_notes(self, np_value_informations):
        trimmed = np_value_informations[resource.informations['notes']['trim']]
        splited = np.hsplit(trimmed, resource.informations['notes']['digit'])

        value = 0
        pos = 3
        for pos in range(4):
            trimmed_once = splited[pos][resource.informations['notes']['trimnumber']]
            bins = np.where(trimmed_once==resource.informations['notes']['maskvalue'], 1, 0).flatten()
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs])
            if not tablekey in resource.informations['notes']['table'].keys():
                if value != 0:
                    return None
                else:
                    continue
            
            value = value * 10 + resource.informations['notes']['table'][tablekey]

        if value == 0:
            return None

        return value

    def get_music(self, np_value_informations):
        """曲名を取得する

        Args:
            np_value_informations (np.array): 対象のトリミングされたリザルト画像データ

        Returns:
            str: 曲名(認識失敗時はNone)
        """
        trimmed = np_value_informations[resource.informations['music']['trim']]

        blue = np.where(trimmed[:,:,2]==resource.informations['music']['bluevalue'],trimmed[:,:,2],0)
        red = np.where(trimmed[:,:,0]==resource.informations['music']['redvalue'],trimmed[:,:,0],0)
        gray1 = np.where((trimmed[:,:,0]==trimmed[:,:,1])&(trimmed[:,:,0]==trimmed[:,:,2]),trimmed[:,:,0],0)
        gray = np.where((gray1!=255)&(gray1>resource.informations['music']['gray_threshold']),gray1,0)

        gray_count = np.count_nonzero(gray)
        blue_count = np.count_nonzero(blue)
        red_count = np.count_nonzero(red)
        max_count = max(gray_count, blue_count, red_count)
        if max_count == gray_count:
            masked = np.where(resource.informations['music']['mask']['gray']==1,gray,0)
            targettable = resource.informations['music']['table']['gray']
        if max_count == blue_count:
            masked = np.where(resource.informations['music']['mask']['blue']==1,blue,0)
            targettable = resource.informations['music']['table']['blue']
        if max_count == red_count:
            masked = np.where(resource.informations['music']['mask']['red']==1,red,0)
            targettable = resource.informations['music']['table']['red']
        
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
        trimmed = np_value[resource.details['define']['option']['trim']]

        def generatekey(np_value):
            bins = np.where(np_value==resource.details['define']['option']['maskvalue'], 1, 0)
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            return ''.join([format(v, '0x') for v in hexs.flatten()])

        arrange = None
        flip = None
        assist = None
        battle = False
        while True:
            tablekey = generatekey(trimmed[:, :resource.details['option']['lengths'][0]*8:2])
            value = None
            for length in resource.details['option']['lengths']:
                if tablekey[:length] in resource.details['option'].keys():
                    value = resource.details['option'][tablekey[:length]]
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
                trimmed = trimmed[:, resource.details['define']['option']['width'][value] + resource.details['define']['option']['width'][',']:]
            else:
                trimmed = trimmed[:, resource.details['define']['option']['width'][value] + resource.details['define']['option']['width']['/']:]
        
        return ResultOptions(arrange, flip, assist, battle)

    def get_graphtype(self, np_value):
        for key, value in resource.details['graphtype'].items():
            trimmed = np_value[resource.details['define']['graphtype'][key]]
            if np.all(trimmed==value):
                return key
        return 'gauge'

    def get_clear_type(self, np_value):
        result = {'best': None, 'current': None}
        for key in result.keys():
            trimmed = np_value[resource.details['define']['clear_type'][key]]
            uniques, counts = np.unique(trimmed, return_counts=True)
            color = uniques[np.argmax(counts)]
            if color in resource.details['clear_type'].keys():
                result[key] = resource.details['clear_type'][color]
        
        trimmed = np_value[resource.details['define']['clear_type']['new']]
        if np.all((resource.details['not_new']==0)|(trimmed==resource.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(result['best'], result['current'], isnew)

    def get_dj_level(self, np_value):
        result = {'best': None, 'current': None}
        for key in result.keys():
            trimmed = np_value[resource.details['define']['dj_level'][key]]
            count = np.count_nonzero(trimmed==resource.details['define']['dj_level']['maskvalue'])
            if count in resource.details['dj_level'].keys():
                result[key] = resource.details['dj_level'][count]
        
        trimmed = np_value[resource.details['define']['dj_level']['new']]
        if np.all((resource.details['not_new']==0)|(trimmed==resource.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(result['best'], result['current'], isnew)

    def get_score(self, np_value):
        trimmed = np_value[resource.details['define']['score']['best']]
        best = None
        for dig in range(resource.details['define']['score']['digit']):
            splitted = np.hsplit(trimmed, resource.details['define']['score']['digit'])
            trimmed_once = splitted[-(dig+1)][resource.details['define']['numberbest']['trim']]
            bins = np.where(trimmed_once==resource.details['define']['numberbest']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in resource.details['number_best'].keys():
                break
            if best is None:
                best = 0
            best += 10 ** dig * resource.details['number_best'][tablekey]

        trimmed = np_value[resource.details['define']['score']['current']]
        current = None
        for dig in range(resource.details['define']['score']['digit']):
            splitted = np.hsplit(trimmed, resource.details['define']['score']['digit'])
            trimmed_once = splitted[-(dig+1)][resource.details['define']['numbercurrent']['trim']]
            bins = np.where(trimmed_once==resource.details['define']['numbercurrent']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in resource.details['number_current'].keys():
                break
            if current is None:
                current = 0
            current += 10 ** dig * resource.details['number_current'][tablekey]
        
        trimmed = np_value[resource.details['define']['score']['new']]
        if np.all((resource.details['not_new']==0)|(trimmed==resource.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(best, current, isnew)

    def get_miss_count(self, np_value):
        trimmed = np_value[resource.details['define']['miss_count']['best']]
        best = None
        for dig in range(resource.details['define']['miss_count']['digit']):
            splitted = np.hsplit(trimmed, resource.details['define']['miss_count']['digit'])
            trimmed_once = splitted[-(dig+1)][resource.details['define']['numberbest']['trim']]
            bins = np.where(trimmed_once==resource.details['define']['numberbest']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in resource.details['number_best'].keys():
                break
            if best is None:
                best = 0
            best += 10 ** dig * resource.details['number_best'][tablekey]

        trimmed = np_value[resource.details['define']['miss_count']['current']]
        current = None
        for dig in range(resource.details['define']['miss_count']['digit']):
            splitted = np.hsplit(trimmed, resource.details['define']['miss_count']['digit'])
            trimmed_once = splitted[-(dig+1)][resource.details['define']['numbercurrent']['trim']]
            bins = np.where(trimmed_once==resource.details['define']['numbercurrent']['maskvalue'], 1, 0).T
            hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
            if not tablekey in resource.details['number_current'].keys():
                break
            if current is None:
                current = 0
            current += 10 ** dig * resource.details['number_current'][tablekey]
        
        trimmed = np_value[resource.details['define']['miss_count']['new']]
        if np.all((resource.details['not_new']==0)|(trimmed==resource.details['not_new'])):
            isnew = False
        else:
            isnew = True
        
        return ResultValues(best, current, isnew)
    
    def get_graphtarget(self, np_value):
        trimmed = np_value[resource.details['define']['graphtarget']['trimmode']]
        uniques, counts = np.unique(trimmed, return_counts=True)
        mode = uniques[np.argmax(counts)]
        if not mode in resource.details['graphtarget'].keys():
            return None
        
        trimmed = np_value[resource.details['define']['graphtarget']['trimkey']]
        bins = np.where(trimmed==mode, 1, 0)
        hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        tablekey = ''.join([format(v, '0x') for v in hexs])
        if not tablekey in resource.details['graphtarget'][mode].keys():
            return None
        
        return resource.details['graphtarget'][mode][tablekey]

    def get_informations(self, np_value):
        play_mode = self.get_play_mode(np_value)
        difficulty, level = self.get_difficulty(np_value)
        notes = self.get_notes(np_value)
        music = self.get_music(np_value)

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
            self.get_informations(screen.np_value[define.areas_np['informations']]),
            play_side,
            self.get_has_rival(screen.np_value),
            self.get_has_dead(screen.np_value, play_side),
            self.get_details(screen.np_value[define.areas_np['details'][play_side]])
        )
    
        return result

recog = Recognition()
