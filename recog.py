import numpy as np
from logging import getLogger

logger_child_name = 'recog'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded recog.py')

from define import define
from resources import resource
from result import ResultInformations,ResultValues,ResultDetails,ResultOptions,Result

class Recognition():
    class Result():
        @staticmethod
        def get_play_side(np_value):
            for target in define.value_list['play_sides']:
                trimmed = np_value[define.areas_np['play_side'][target]]
                if np.all((resource.play_side==0)|(trimmed==resource.play_side)):
                    return target

            return None

        @staticmethod
        def get_has_dead(np_value, play_side):
            trimmed = np_value[define.areas_np['dead'][play_side]]
            if np.all((resource.dead==0)|(trimmed==resource.dead)):
                return True
            else:
                return False
        
        @staticmethod
        def get_has_rival(np_value):
            trimmed = np_value[define.areas_np['rival']]
            if np.all((resource.rival==0)|(trimmed==resource.rival)):
                return True
            else:
                return False
        
        @staticmethod
        def get_play_mode(np_value_informations):
            if resource.informations is None:
                return None
            
            trimmed = np_value_informations[resource.informations['play_mode']['trim']].flatten()
            bins = np.where(trimmed==resource.informations['play_mode']['maskvalue'], 1, 0)
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs])
            if not tablekey in resource.informations['play_mode']['table'].keys():
                return None
            return resource.informations['play_mode']['table'][tablekey]

        @staticmethod
        def get_difficulty(np_value_informations):
            if resource.informations is None:
                return None, None
            
            trimmed = np_value_informations[resource.informations['difficulty']['trim']]
            converted = trimmed[:,:,0]*0x10000+trimmed[:,:,1]*0x100+trimmed[:,:,2]

            uniques, counts = np.unique(converted, return_counts=True)
            difficultykey = uniques[np.argmax(counts)]
            if not difficultykey in resource.informations['difficulty']['table']['difficulty'].keys():
                return None, None
            
            difficulty = resource.informations['difficulty']['table']['difficulty'][difficultykey]

            leveltrimmed = converted[resource.informations['difficulty']['trimlevel']].flatten()
            bins = np.where(leveltrimmed==difficultykey, 1, 0)
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            levelkey = ''.join([format(v, '0x') for v in hexs])

            if not levelkey in resource.informations['difficulty']['table']['level'][difficulty].keys():
                return None, None
            
            level = resource.informations['difficulty']['table']['level'][difficulty][levelkey]

            return difficulty, level

        @staticmethod
        def get_notes(np_value_informations):
            if resource.informations is None:
                return None
            
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

        @staticmethod
        def get_music(np_value_informations):
            """曲名を取得する

            Args:
                np_value_informations (np.array): 対象のトリミングされたリザルト画像データ

            Returns:
                str: 曲名(認識失敗時はNone)
            """
            if resource.informations is None:
                return None

            trimmed = np_value_informations[resource.informations['music']['trim']]

            lower = resource.informations['music']['factors']['blue']['lower']
            upper = resource.informations['music']['factors']['blue']['upper']
            filtereds = []
            for i in range(trimmed.shape[2]):
                filtereds.append(np.where((lower[:,:,i]<=trimmed[:,:,i])&(trimmed[:,:,i]<=upper[:,:,i]), trimmed[:,:,i], 0))
            blue = np.where((filtereds[0]!=0)&(filtereds[1]!=0)&(filtereds[2]!=0), filtereds[2], 0)

            lower = resource.informations['music']['factors']['red']['lower']
            upper = resource.informations['music']['factors']['red']['upper']
            filtereds = []
            for i in range(trimmed.shape[2]):
                filtereds.append(np.where((lower[:,:,i]<=trimmed[:,:,i])&(trimmed[:,:,i]<=upper[:,:,i]), trimmed[:,:,i], 0))
            red = np.where((filtereds[0]!=0)&(filtereds[1]!=0)&(filtereds[2]!=0), trimmed[:,:,0], 0)

            lower = resource.informations['music']['factors']['gray']['lower']
            upper = resource.informations['music']['factors']['gray']['upper']
            filtereds = []
            for i in range(trimmed.shape[2]):
                filtereds.append(np.where((lower[:,:,i]<=trimmed[:,:,i])&(trimmed[:,:,i]<=upper[:,:,i]), trimmed[:,:,i], 0))
            gray = np.where((filtereds[0]==filtereds[1])&(filtereds[0]==filtereds[2]), filtereds[0], 0)

            gray_count = np.count_nonzero(gray)
            blue_count = np.count_nonzero(blue)
            red_count = np.count_nonzero(red)
            max_count = max(gray_count, blue_count, red_count)
            if max_count == gray_count:
                masked = np.where(resource.informations['music']['masks']['gray']==1,gray,0)
                targettable = resource.informations['music']['tables']['gray']
            if max_count == blue_count:
                masked = np.where(resource.informations['music']['masks']['blue']==1,blue,0)
                targettable = resource.informations['music']['tables']['blue']
            if max_count == red_count:
                masked = np.where(resource.informations['music']['masks']['red']==1,red,0)
                targettable = resource.informations['music']['tables']['red']
            
            for height in range(masked.shape[0]):
                unique, counts = np.unique(masked[height], return_counts=True)
                if len(unique) == 1:
                    continue
                index = -np.argmax(np.flip(counts[1:])) - 1
                intensity = unique[index]
                bins = np.where(masked[height]==intensity, 1, 0)
                hexs = bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
                tablekey = f"{height:02d}{''.join([format(v, '0x') for v in hexs])}"
                if not tablekey in targettable.keys():
                    break

                if type(targettable[tablekey]) == str:
                    return targettable[tablekey]
                
                targettable = targettable[tablekey]
            
            return None

        @staticmethod
        def get_options(np_value):
            if resource.details is None:
                return None

            playside = define.details_get_playside(np_value)
            trimmed = np_value[resource.details['define']['option']['trim'][playside]]

            def generatekey(np_value):
                bins = np.where(np_value[:, ::4]==resource.details['define']['option']['maskvalue'], 1, 0).T
                hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
                return ''.join([format(v, '0x') for v in hexs.flatten()])

            arrange = None
            flip = None
            assist = None
            battle = False
            while True:
                tablekey = generatekey(trimmed[:, :resource.details['option']['lengths'][0]*2])
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

        @staticmethod
        def get_graphtype(np_value):
            if resource.details is None:
                return None

            for key, value in resource.details['graphtype'].items():
                playside = define.details_get_playside(np_value)
                trimmed = np_value[resource.details['define']['graphtype'][playside][key]]
                if np.all(trimmed==value):
                    return key
            return 'gauge'

        @staticmethod
        def get_clear_type(np_value):
            if resource.details is None:
                return None

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

        @staticmethod
        def get_dj_level(np_value):
            if resource.details is None:
                return None

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

        @staticmethod
        def get_score(np_value):
            if resource.details is None:
                return None

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

        @staticmethod
        def get_miss_count(np_value):
            if resource.details is None:
                return None

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
        
        @staticmethod
        def get_graphtarget(np_value):
            if resource.details is None:
                return None

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

        @classmethod
        def get_informations(cls, np_value):
            play_mode = cls.get_play_mode(np_value)
            difficulty, level = cls.get_difficulty(np_value)
            notes = cls.get_notes(np_value)
            music = cls.get_music(np_value)

            return ResultInformations(play_mode, difficulty, level, notes, music)

        @classmethod
        def get_details(cls, np_value):
            graphtype = cls.get_graphtype(np_value)
            if graphtype == 'gauge':
                options = cls.get_options(np_value)
            else:
                options = None

            clear_type = cls.get_clear_type(np_value)
            dj_level = cls.get_dj_level(np_value)
            score = cls.get_score(np_value)
            miss_count = cls.get_miss_count(np_value)
            graphtarget = cls.get_graphtarget(np_value)

            return ResultDetails(graphtype, options, clear_type, dj_level, score, miss_count, graphtarget)

    class MusicSelect():
        @staticmethod
        def get_playmode(np_value):
            if resource.musicselect is None:
                return None
            if not 'playmode' in resource.musicselect.keys():
                return None
            trimmed = np_value[resource.musicselect['playmode']['trim']].flatten()
            bins = np.where(trimmed==resource.musicselect['playmode']['maskvalue'], 1, 0)
            hexs=bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
            tablekey = ''.join([format(v, '0x') for v in hexs])
            if not tablekey in resource.musicselect['playmode']['table'].keys():
                return None
            return resource.musicselect['playmode']['table'][tablekey]
        
        @staticmethod
        def get_version(np_value):
            if resource.musicselect is None:
                return None
            for table in resource.musicselect['version']:
                cropped = np_value[table['trim']]
                reshaped = cropped.reshape(cropped.shape[0]*cropped.shape[1], cropped.shape[2])
                hexes = [''.join([format(b, '02x') for b in point]) for point in reshaped]
                tablekey = ''.join(hexes)

                if tablekey in table['table'].keys():
                    return table['table'][tablekey]
            return None

        @staticmethod
        def get_musicname(np_value):
            if resource.musicselect is None:
                return None
            
            resource_target = resource.musicselect['musicname']['infinitas']
            cropped = np_value[resource_target['trim']]
            filtereds = []
            for index in range(len(resource_target['thresholds'])):
                threshold = resource_target['thresholds'][index]
                masked = np.where((threshold[0]<=cropped[:,:,index])&(cropped[:,:,index]<=threshold[1]), 1, 0)
                filtereds.append(masked)
            bins = np.where((filtereds[0]==1)&(filtereds[1]==1)&(filtereds[2]==1), 1, 0)
            hexes = [line[::4]*8+line[1::4]*4+line[2::4]*2+line[3::4] for line in bins]
            recogkeys = [''.join([format(v, '0x') for v in line]) for line in hexes]
            tabletarget = resource_target['table']
            for recogkey in recogkeys:
                if not recogkey in tabletarget.keys():
                    break
                if type(tabletarget[recogkey]) is str:
                    return tabletarget[recogkey]
                tabletarget = tabletarget[recogkey]
            
            resource_target = resource.musicselect['musicname']['leggendaria']
            cropped = np_value[resource_target['trim']]
            filtereds = []
            for index in range(len(resource_target['thresholds'])):
                threshold = resource_target['thresholds'][index]
                masked = np.where((threshold[0]<=cropped[:,:,index])&(cropped[:,:,index]<=threshold[1]), 1, 0)
                filtereds.append(masked)
            bins = np.where((filtereds[0]==1)&(filtereds[1]==1)&(filtereds[2]==1), 1, 0)
            hexes = [line[::4]*8+line[1::4]*4+line[2::4]*2+line[3::4] for line in bins]
            recogkeys = [''.join([format(v, '0x') for v in line]) for line in hexes]
            tabletarget = resource_target['table']
            for recogkey in recogkeys:
                if not recogkey in tabletarget.keys():
                    break
                if type(tabletarget[recogkey]) is str:
                    return tabletarget[recogkey]
                tabletarget = tabletarget[recogkey]

            resource_target = resource.musicselect['musicname']['arcade']
            thresholds = resource_target['thresholds']
            cropped = np_value[resource_target['trim']]
            masked = np.where((cropped[:,:,0]==cropped[:,:,1])&(cropped[:,:,0]==cropped[:,:,2]),cropped[:,:,0], 0)
            bins = [np.where((thresholds[i][0]<=masked[i])&(masked[i]<=thresholds[i][1]), 1, 0) for i in range(masked.shape[0])]
            hexes = [line[::4]*8+line[1::4]*4+line[2::4]*2+line[3::4] for line in bins]
            recogkeys = [''.join([format(v, '0x') for v in line]) for line in hexes]
            tabletarget = resource_target['table']
            for recogkey in recogkeys:
                if not recogkey in tabletarget.keys():
                    return None
                if type(tabletarget[recogkey]) is str:
                    return tabletarget[recogkey]
                tabletarget = tabletarget[recogkey]
            return None
        
        @staticmethod
        def get_difficulty(np_value):
            if resource.musicselect is None:
                return None
            targetresource = resource.musicselect['levels']['select']
            for difficulty in targetresource.keys():
                trimmed = np_value[targetresource[difficulty]['trim']]
                filtereds = []
                for index in range(len(targetresource[difficulty]['thresholds'])):
                    threshold = targetresource[difficulty]['thresholds'][index]
                    masked = np.where((threshold[0]<=trimmed[:,:,index])&(trimmed[:,:,index]<=threshold[1]), 1, 0)
                    filtereds.append(masked)
                bins = np.where((filtereds[0]==1)&(filtereds[1]==1)&(filtereds[2]==1), 1, 0)
                hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
                tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
                if tablekey in targetresource[difficulty]['table'].keys():
                    return str.upper(difficulty)
            return None

        @staticmethod
        def get_cleartype(np_value):
            if resource.musicselect is None:
                return None
            trimmed = np_value[resource.musicselect['cleartype']['trim']]
            uniques, counts = np.unique(trimmed, return_counts=True)
            if len(uniques) == 0:
                return None
            color = uniques[np.argmax(counts)]
            if color in resource.musicselect['cleartype']['table'].keys():
                return resource.musicselect['cleartype']['table'][color]
            return None

        @staticmethod
        def get_djlevel(np_value):
            if resource.musicselect is None:
                return None
            trimmed = np_value[resource.musicselect['djlevel']['trim']]
            count = np.count_nonzero(trimmed==resource.musicselect['djlevel']['maskvalue'])
            if count in resource.musicselect['djlevel']['table'].keys():
                return resource.musicselect['djlevel']['table'][count]
            return None

        @staticmethod
        def get_score(np_value):
            if resource.musicselect is None:
                return None
            trimmed = np_value[resource.musicselect['score']['trim']]
            score = None
            for dig in range(resource.musicselect['score']['digit']):
                splitted = np.hsplit(trimmed, resource.musicselect['score']['digit'])
                trimmed_once = splitted[-(dig+1)][resource.musicselect['number']['trim']]
                bins = np.where(trimmed_once==resource.musicselect['number']['maskvalue'], 1, 0).T
                hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
                tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
                if not tablekey in resource.musicselect['number']['table'].keys():
                    break
                if score is None:
                    score = 0
                score += 10 ** dig * resource.musicselect['number']['table'][tablekey]
            
            return score

        @staticmethod
        def get_misscount(np_value):
            if resource.musicselect is None:
                return None
            trimmed = np_value[resource.musicselect['misscount']['trim']]
            score = None
            for dig in range(resource.musicselect['misscount']['digit']):
                splitted = np.hsplit(trimmed, resource.musicselect['misscount']['digit'])
                trimmed_once = splitted[-(dig+1)][resource.musicselect['number']['trim']]
                bins = np.where(trimmed_once==resource.musicselect['number']['maskvalue'], 1, 0).T
                hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
                tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
                if not tablekey in resource.musicselect['number']['table'].keys():
                    break
                if score is None:
                    score = 0
                score += 10 ** dig * resource.musicselect['number']['table'][tablekey]
            
            return score

        @staticmethod
        def get_levels(np_value):
            if resource.musicselect is None:
                return None
            
            ret = {}
            for difficulty in resource.musicselect['levels']['select']:
                resourcetarget = resource.musicselect['levels']['select'][difficulty]
                trimmed = np_value[resourcetarget['trim']]
                
                filtereds = []
                for index in range(len(resourcetarget['thresholds'])):
                    threshold = resourcetarget['thresholds'][index]
                    masked = np.where((threshold[0]<=trimmed[:,:,index])&(trimmed[:,:,index]<=threshold[1]), 1, 0)
                    filtereds.append(masked)
                bins = np.where((filtereds[0]==1)&(filtereds[1]==1)&(filtereds[2]==1), 1, 0)
                hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
                tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
                if tablekey in resourcetarget['table'].keys():
                    ret[str.upper(difficulty)] = resourcetarget['table'][tablekey]
                    break
            for difficulty in resource.musicselect['levels']['noselect']:
                resourcetarget = resource.musicselect['levels']['noselect'][difficulty]
                trimmed = np_value[resourcetarget['trim']]
                threshold = resourcetarget['threshold']
                filtereds = []
                for index in range(trimmed.shape[2]):
                    masked = np.where((threshold[0]<=trimmed[:,:,index])&(trimmed[:,:,index]<=threshold[1]), 1, 0)
                    filtereds.append(masked)
                bins = np.where((filtereds[0]==1)&(filtereds[1]==1)&(filtereds[2]==1), 1, 0)
                hexs = bins[:,0::4]*8+bins[:,1::4]*4+bins[:,2::4]*2+bins[:,3::4]
                tablekey = ''.join([format(v, '0x') for v in hexs.flatten()])
                if tablekey in resourcetarget['table'].keys():
                    ret[str.upper(difficulty)] = resourcetarget['table'][tablekey]
            return ret

    @staticmethod
    def get_is_savable(np_value):
        define_result_check = define.result_check

        background_key = np_value[define_result_check['background_key_position']]
        if not background_key in resource.is_savable.keys():
            return False

        for area_key, area in define_result_check['areas'].items():
            if not np.array_equal(np_value[area], resource.is_savable[background_key][area_key]):
                return False
        
        return True
        
    @classmethod
    def get_result(cls, screen):
        play_side = cls.Result.get_play_side(screen.np_value)
        if play_side == None:
            return None

        result = Result(
            cls.Result.get_informations(screen.np_value[define.areas_np['informations']]),
            play_side,
            cls.Result.get_has_rival(screen.np_value),
            cls.Result.get_has_dead(screen.np_value, play_side),
            cls.Result.get_details(screen.np_value[define.areas_np['details'][play_side]])
        )
    
        return result
