import json
from os import remove,mkdir,rename
from os.path import join,exists
from logging import getLogger
from copy import deepcopy
from re import search

logger_child_name = 'record'

logger = getLogger().getChild(logger_child_name)
logger.debug(f'loaded record.py')

#from version import version
from resources import resource,resources_dirname
from define import Playmodes,Playtypes,define
from result import Result
#from versioncheck import version_isold

records_basepath = 'records'

musicnamechanges_filename = 'musicnamechanges.res'

recent_filename = 'recent.json'
summary_filename = 'summary.json'

regenerateachievement_fromhistories_version = '0.20.dev1'
'''履歴から実績の記録を生成する条件のバージョン

履歴から実績の記録を生成する処理を最後に実行したのがこのバージョンより前の場合は
再生成を実行する。
'''

if not exists(records_basepath):
    mkdir(records_basepath)

class Notebook():
    filename: str = None
    
    def __init__(self):
        self.filepath = join(records_basepath, self.filename)

        if not exists(self.filepath):
            self.json = {}
            return
        
        try:
            with open(self.filepath) as f:
                self.json = json.load(f)
        except Exception:
            self.json = {}
    
    def save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.json, f)

class NotebookRecent(Notebook):
    def __init__(self, maxcount: int):
        self.filename = recent_filename
        self.maxcount = maxcount

        super().__init__()

        if not 'version' in self.json.keys() or self.json['version'] != version:
            self.json = {'version': version}
            self.save()
    
    def append(self, result: Result, saved: bool, filtered: bool):
        if not 'timestamps' in self.json.keys():
            self.json['timestamps'] = []
        self.json['timestamps'].append(result.timestamp)

        if not 'results' in self.json.keys():
            self.json['results'] = {}

        if result.details.options is None:
            option = None
        else:
            optionvalues = [
                result.details.options.arrange,
                result.details.options.flip,
                result.details.options.assist
            ]
            option = ','.join([v for v in optionvalues if v is not None])
        
        update_score = None
        if result.details.score is not None and result.details.score.new:
            if result.details.score.current is not None and result.details.score.best is not None:
                update_score = result.details.score.current - result.details.score.best
        
        update_miss_count = None
        if result.details.miss_count is not None and result.details.miss_count.new:
            if result.details.miss_count.current is not None and result.details.miss_count.best is not None:
                update_miss_count = result.details.miss_count.current - result.details.miss_count.best
        
        self.json['results'][result.timestamp] = {
            'playtype': result.playtype,
            'difficulty': result.informations.difficulty,
            'playspeed': result.informations.playspeed,
            'music': result.informations.music,
            'clear_type_new': result.details.clear_type is not None and result.details.clear_type.new,
            'dj_level_new': result.details.dj_level is not None and result.details.dj_level.new,
            'score_new': result.details.score is not None and result.details.score.new,
            'miss_count_new': result.details.miss_count is not None and result.details.miss_count.new,
            'update_clear_type': result.details.clear_type.current if result.details.clear_type is not None and result.details.clear_type.new else None,
            'update_dj_level': result.details.dj_level.current if result.details.dj_level is not None and result.details.dj_level.new else None,
            'update_score': update_score,
            'update_miss_count': update_miss_count,
            'option': option,
            'play_side': result.play_side,
            'has_loveletter': result.rival,
            'has_graphtargetname': result.details.graphtarget == 'rival',
            'saved': saved,
            'filtered': filtered,
        }

        while len(self.json['timestamps']) > self.maxcount:
            if self.json['timestamps'][0] in self.json['results'].keys():
                del self.json['results'][self.json['timestamps'][0]]
            del self.json['timestamps'][0]
    
    @property
    def timestamps(self):
        if not 'timestamps' in self.json.keys():
            return []
        return self.json['timestamps']
    
    def get_result(self, timestamp: str) -> dict:
        if not 'results' in self.json.keys() or not timestamp in self.json['results']:
            return None
        return self.json['results'][timestamp]

class NotebookMusic(Notebook):
    achievement_default = {
        'fixed': {'clear_type': None, 'dj_level': None},
        'S-RANDOM': {'clear_type': None, 'dj_level': None},
    }

    def __init__(self, musicname: str):
        '''曲名をエンコード&16進数変換してファイル名にする

        Args:
            musicname(str): 曲名
        Note:
            ファイル名から曲名にデコードする場合は
            bytes.fromhex('ファイル名').decode('UTF-8')
        '''
        self.filename = f"{musicname.encode('UTF-8').hex()}.json"
        super().__init__()
    
    def get_scoreresult(self, playtype: str, difficulty: str):
        '''対象のプレイモード・難易度の記録を取得する

        Args:
            playtype (str): SP か DP か DP BATTLE
            difficulty (str): NORMAL か HYPER か ANOTHER か BEGINNER か LEGGENDARIA
        Returns:
            list: レコードのリスト
        '''
        if not playtype in self.json.keys():
            return None
        if not difficulty in self.json[playtype].keys():
            return None
        
        target = self.json[playtype][difficulty]
        if 'timestamps' in target.keys() and len(target['timestamps']) > 0:
            generate = not 'achievement' in target.keys() or not 'fromhistoriesgenerate_lastversion' in target['achievement'].keys()
            if not generate:
                generate = version_isold(
                    target['achievement']['fromhistoriesgenerate_lastversion'],
                    regenerateachievement_fromhistories_version,
                )

            if generate:
                self.generate_achievement_from_histories(target)
                self.save()
        
        return target

    def delete(self):
        if exists(self.filepath):
            remove(self.filepath)
    
    def insert_latest(self, target: dict[int | dict[str, dict | list]], result: Result, options: dict[str, str | bool | None]):
        target['latest'] = {
            'timestamp': result.timestamp,
            'clear_type': {
                'value': result.details.clear_type.current,
                'new': result.details.clear_type.new,
            },
            'dj_level': {
                'value': result.details.dj_level.current,
                'new': result.details.dj_level.new,
            },
            'score': {
                'value': result.details.score.current,
                'new': result.details.score.new,
            },
            'miss_count': {
                'value': result.details.miss_count.current,
                'new': result.details.miss_count.new,
            },
            'options': options,
            'playspeed': result.informations.playspeed,
        }

    def insert_history(self, target: dict[int | dict[str, dict | list]], result: Result, options: dict[str, str | bool | None]):
        if not 'timestamps' in target.keys():
            target['timestamps'] = []
        target['timestamps'].append(result.timestamp)

        if not 'history' in target.keys():
            target['history'] = {}
        target['history'][result.timestamp] = {
            'clear_type': {
                'value': result.details.clear_type.current,
                'new': result.details.clear_type.new,
            },
            'dj_level': {
                'value': result.details.dj_level.current,
                'new': result.details.dj_level.new,
            },
            'score': {
                'value': result.details.score.current,
                'new': result.details.score.new,
            },
            'miss_count': {
                'value': result.details.miss_count.current,
                'new': result.details.miss_count.new,
            },
            'options': options,
            'playspeed': result.informations.playspeed,
        }

    def check_new_of_battle(self, result: Result):
        '''更新の有無をチェックする

        オプションにBATTLEを含む場合はNewアイコンが出ないため、独自に評価する。
        ただし配置オプションにH-RANが含まれている場合は評価しない。
        等倍以外のプレイ時も評価しない。

        Args:
            result(Result): 対象のリザルト
        '''
        if result.informations.playspeed is not None:
            return
        if result.details.options.arrange is not None and 'H-RAN' in result.details.options.arrange:
            return

        update_all = False
        if not 'DP BATTLE' in self.json.keys():
            update_all = True
        else:
            target = self.json['DP BATTLE']

        if not update_all:
            if not result.informations.difficulty in target.keys():
                update_all = True
            else:
                target = target[result.informations.difficulty]

        if not update_all:
            if not 'best' in target.keys():
                update_all = True
            else:
                target = target['best']

        targets = {
            'clear_type': result.details.clear_type,
            'dj_level': result.details.dj_level,
            'score': result.details.score,
            'miss_count': result.details.miss_count,
        }
        for key, value in targets.items():
            if value.current is None:
                continue

            update = update_all

            if not update and not key in target.keys():
                update = True

            if not update and target[key]['value'] is None:
                update = True
            
            if not update:
                if key in ['clear_type', 'dj_level']:
                    if key == 'clear_type':
                        value_list = define.value_list['clear_types']
                    if key == 'dj_level':
                        value_list = define.value_list['dj_levels']
                    
                    nowbest_index = value_list.index(target[key]['value'])
                    current_index = value_list.index(value.current)
                    if nowbest_index < current_index:
                        update = True
                
                if key in ['score', 'miss_count']:
                    if value.current > target[key]['value']:
                        update = True

            if update:
                value.new = True

    def update_best_result(self, target: dict[int | dict[str, dict | list]], result: Result, options: dict[str, str | bool | None]):
        '''ベスト記録を更新する

        BATTLEの場合はゲームに記録が残らず「New」アイコンが出なため独自に更新の有無を評価する。

        Args:
            target(dict): 対象の記録テーブル
            result(Result): 対象のリザルト
            options(dict): 記録用のオプションdict

        Return:
            bool: 更新時にTrue
        '''
        if not 'best' in target.keys() or not 'latest' in target['best'].keys():
            target['best'] = {}
        
        target['best']['latest'] = result.timestamp

        targets = {
            'clear_type': result.details.clear_type,
            'dj_level': result.details.dj_level,
            'score': result.details.score,
            'miss_count': result.details.miss_count,
        }
        updated = False
        for key, value in targets.items():
            if value.new:
                target['best'][key] = {
                    'value': value.current,
                    'timestamp': result.timestamp,
                    'options': options
                }
                updated = True
            else:
                if not key in target['best'].keys() and value.best is not None:
                    target['best'][key] = {
                        'value': value.best,
                        'timestamp': None,
                        'options': None
                    }
                    updated = True
        
        return updated

    def generate_achievement_from_histories(self, target):
        '''達成記録を過去の記録データから作成する

        理論値を記録していたら MAX と記録する
        F-COMBOとAAAの同時記録をしていたら F-COMBO & AAA と記録する
        Args:
            target (dict): 記録の対象部分
        '''
        target['achievement'] = deepcopy(self.achievement_default)
        achievement = target['achievement']

        targetkeys = {
            'clear_type': define.value_list['clear_types'],
            'dj_level': define.value_list['dj_levels']
        }
        for timestamp in target['timestamps']:
            record = target['history'][timestamp]

            if not 'options' in record.keys() or record['options'] is None:
                continue

            achievement_key = None
            if record['options']['arrange'] in (None, 'MIRROR', 'OFF/MIR', 'MIR/OFF', 'MIR/MIR',):
                achievement_key = 'fixed'
            if record['options']['arrange'] in ('S-RANDOM', 'S-RAN/S-RAN',):
                achievement_key = 'S-RANDOM'
            if achievement_key is None:
                continue

            if not 'MAX' in achievement[achievement_key].keys():
                if 'notes' in target.keys() and record['score'] == target['notes'] * 2:
                    achievement[achievement_key]['MAX'] = True

            if not 'F-COMBO & AAA' in achievement[achievement_key] == 'F-COMBO & AAA':
                if record['clear_type']['value'] == 'F-COMBO' and record['dj_level']['value'] == 'AAA':
                    achievement[achievement_key]['F-COMBO & AAA'] = True

            if achievement[achievement_key] is None:
                achievement[achievement_key] = {'clear_type': None, 'dj_level': None}
            
            for key, valuelist in targetkeys.items():
                value = record[key]['value']

                is_updated = achievement[achievement_key][key] is None
                if not is_updated:
                    index_current = valuelist.index(value)
                    index_recorded = valuelist.index(achievement[achievement_key][key]) if achievement[achievement_key][key] is not None else None
                    if index_recorded is not None and index_current > index_recorded:
                        is_updated = True
                if is_updated:
                    achievement[achievement_key][key] = value
        
        achievement['fromhistoriesgenerate_lastversion'] = version
        
    def update_achievement(self, target: dict[int | dict[str, dict | list]], result: Result) -> bool:
        '''達成記録を更新する

        Args:
            target (dict): 記録の対象部分
            result (Result): 対象のリザルト
        
        Returns:
            bool: 更新があった
        '''
        if not 'achievement' in target.keys():
            target['achievement'] = deepcopy(self.achievement_default)
        achievement = target['achievement']
        
        informations = result.informations
        details = result.details

        if details.options is None:
            return False

        arrange = details.options.arrange

        achievement_key = None
        if arrange in [None, 'MIRROR', 'OFF/MIR', 'MIR/OFF', 'MIR/MIR']:
            achievement_key = 'fixed'
        if arrange in ['S-RANDOM', 'S-RAN/S-RAN']:
            achievement_key = 'S-RANDOM'

        if achievement_key is None:
            return False
        
        updated = False

        if not 'MAX' in achievement[achievement_key].keys():
            if informations is not None and informations.notes is not None and details.score.current == informations.notes * 2:
                achievement[achievement_key]['MAX'] = True
                updated = True

        if not 'F-COMBO & AAA' in achievement[achievement_key].keys():
            if details.clear_type.current == 'F-COMBO' and details.dj_level.current == 'AAA':
                achievement[achievement_key]['F-COMBO & AAA'] = True
                updated = True

        results = [
            ('clear_type', define.value_list['clear_types'], details.clear_type.current),
            ('dj_level', define.value_list['dj_levels'], details.dj_level.current)
        ]
        for key, valuelist, value in results:
            is_updated = achievement[achievement_key][key] is None
            if not is_updated:
                index_current = valuelist.index(value)
                index_recorded = valuelist.index(achievement[achievement_key][key]) if achievement[achievement_key][key] is not None else None
                if index_recorded is not None and index_current > index_recorded:
                    is_updated = True
            if is_updated:
                achievement[achievement_key][key] = value
                updated = True
        
        return updated

    def insert(self, result: Result):
        '''対象のリザルトを記録に追加する

        Args:
            result (Result): 追加対象のリザルト
        '''
        if result.playtype is None:
            return
        if result.informations.notes is None:
            return
        
        target = self.json

        playtype = result.playtype
        if not playtype in target.keys():
            target[playtype] = {}
        target = target[playtype]

        difficulty = result.informations.difficulty
        if not difficulty in target.keys():
            target[difficulty] = {}
        target = target[difficulty]

        target['notes'] = result.informations.notes

        if result.details is not None and result.details.options is not None:
            options_value = {
                'arrange': result.details.options.arrange,
                'flip': result.details.options.flip,
                'assist': result.details.options.assist,
                'battle': result.details.options.battle,
                'special': result.details.options.special,
            }
        else:
            options_value = None

        updated = False
        if not result.dead or result.has_new_record():
            self.insert_latest(target, result, options_value)
            self.insert_history(target, result, options_value)
            updated = True

        if self.update_best_result(target, result, options_value):
            updated = True
        
        if self.update_achievement(target, result):
            updated = True

        if updated:
            self.save()
    
    def update_best_musicselect(self, values: dict):
        '''選曲画面から取り込んだ認識結果からベスト記録を更新する

        Args:
            values (dict): 認識結果
        '''
        updated = False

        playtype = values['playtype']
        difficulty = values['difficulty']
        if not playtype in self.json.keys():
            self.json[playtype] = {}
            updated = True
        if not difficulty in self.json[playtype].keys():
            self.json[playtype][difficulty] = {'timestamps': [], 'history': {}, 'best': {}}
            updated = True
        if not 'best' in self.json[playtype][difficulty].keys():
            self.json[playtype][difficulty]['best'] = {}
            updated = True
        target = self.json[playtype][difficulty]['best']
        for key in ['clear_type', 'dj_level', 'score', 'miss_count']:
            selfkey = key.replace('_', '')
            if values[selfkey] is not None:
                if not key in target.keys() or target[key] is None or target[key]['value'] != values[selfkey]:
                    target[key] = {
                        'value': values[selfkey],
                        'timestamp': None,
                        'options': None
                    }
                    updated = True
        return updated
    
    def delete_scoreresult(self, playtype: str, difficulty: str):
        '''指定の譜面記録を削除する

        Args:
            playtype: プレイの種類(SP or DP or DP BATTLE)
            difficulty: 難易度(NORMAL - LEGGENDARIA)
        '''
        if not playtype in self.json.keys():
            return
        if not difficulty in self.json[playtype].keys():
            return
        
        del self.json[playtype][difficulty]

        self.save()
    
    def delete_playresult(self, playtype: str, difficulty: str, timestamp: str):
        '''指定のプレイ記録を削除する

        対象の記録が現在のベスト記録の場合はベストから削除して
        それより古い記録に遡り、直近のベスト記録を探して
        見つかった場合はそれにする。

        Args:
            playtype: プレイの種類(SP or DP or DP BATTLE)
            difficulty: 難易度(NORMAL - LEGGENDARIA)
            timestamp: 削除対象のタイムスタンプ
        '''
        if not playtype in self.json.keys():
            return
        if not difficulty in self.json[playtype].keys():
            return
        
        target: dict[str, int | str | list[str] | dict[str, str | dict]] = self.json[playtype][difficulty]

        if not 'best' in target.keys():
            target['best'] = {}

        search_targets = []
        for key in ['clear_type', 'dj_level', 'score', 'miss_count']:
            if key in target['best'].keys() and target['best'][key] is not None:
                if timestamp == target['best'][key]['timestamp']:
                    target['best'][key] = None
                    search_targets.append(key)
            else:
                search_targets.append(key)
    
        trimmed_timestamps = target['timestamps'][:target['timestamps'].index(timestamp)]
        trimmed_timestamps.reverse()

        while len(search_targets):
            key = search_targets[0]
            for ref_timestamp in trimmed_timestamps:
                ref_result = target['history'][ref_timestamp]
                if ref_result[key]['new']:
                    target['best'][key] = {
                        'value': ref_result[key]['value'],
                        'timestamp': ref_timestamp
                    }
                    # ref_resultにoptionsがないこともある
                    if 'options' in ref_result.keys():
                        target['best'][key]['options'] = ref_result['options']
                    break
            del search_targets[0]

        if timestamp in target['timestamps']:
            target['timestamps'].remove(timestamp)
        if timestamp in target['history']:
            del target['history'][timestamp]

        self.save()

class NotebookSummary(Notebook):
    def __init__(self):
        self.filename = summary_filename
        super().__init__()
    
    def import_allmusics(self, version: str):
        '''全曲の記録を取り込む

        Args:
            version (str): 実行したバージョン
        '''
        self.json = {}
        for musicname in resource.musictable['musics'].keys():
            notebook = NotebookMusic(musicname)
            self.import_targetmusic(musicname, notebook)
        
        self.json['last_allimported'] = version
    
    def import_targetmusic(self, musicname: str, notebook: NotebookMusic):
        '''対象の曲の記録を取り込む
        
        Args:
            musicname (str): 曲名
            notebook (NotebookMusic): 対象曲の記録
        '''
        if not 'musics' in self.json.keys():
            self.json['musics'] = {}

        self.json['musics'][musicname] = {}

        music_item = resource.musictable['musics'][musicname]
        for playtype in Playtypes.values:
            self.json['musics'][musicname][playtype] = {}

            for difficulty in define.value_list['difficulties']:
                playmode = 'SP' if playtype in ('SP', 'DP BATTLE', ) else 'DP'
                if not difficulty in music_item[playmode].keys() or music_item[playmode][difficulty] is None:
                    continue

                r = notebook.get_scoreresult(playtype, difficulty)
                if r is None:
                    continue

                self.json['musics'][musicname][playtype][difficulty] = {}
                target = self.json['musics'][musicname][playtype][difficulty]
                if 'latest' in r.keys() and 'timestamp' in r['latest'].keys():
                    target['latest'] = r['latest']['timestamp']
                else:
                    target['latest'] = None

                if 'timestamps' in r.keys():
                    target['playcount'] = len(r['timestamps'])
                else:
                    target['playcount'] = None

                if 'best' in r.keys():
                    target['best'] = {}
                    targets = [
                        ['cleartype', 'clear_type'],
                        ['djlevel', 'dj_level'],
                        ['score', 'score'],
                        ['misscount', 'miss_count'],
                    ]
                    for key1, key2 in targets:
                        target['best'][key1] = r['best'][key2] if key2 in r['best'].keys() else None
                else:
                    target['best'] = None
                
                if 'achievement' in r.keys():
                    target['achievement'] = {
                        'fixed': r['achievement']['fixed'],
                        'S-RANDOM': r['achievement']['S-RANDOM'],
                    }
                    if 'MAX' in r['achievement'].keys():
                        target['achievement']['MAX'] = True
                    if 'F-COMBO & AAA' in r['achievement'].keys():
                        target['achievement']['F-COMBO & AAA'] = True
                else:
                    target['achievement'] = None
    
    def count(self):
        if not 'musics' in self.json.keys():
            return

        result = {}
        for playmode in Playmodes.values:
            result[playmode] = {}
            for difficulty in define.value_list['difficulties']:
                result[playmode][difficulty] = {'total': 0, 'datacount': 0}
                for cleartype in define.value_list['clear_types']:
                    result[playmode][difficulty][cleartype] = 0
                for djlevel in define.value_list['dj_levels']:
                    result[playmode][difficulty][djlevel] = 0
            for level in define.value_list['levels']:
                result[playmode][level] = {'total': 0, 'datacount': 0}
                for cleartype in define.value_list['clear_types']:
                    result[playmode][level][cleartype] = 0
                for djlevel in define.value_list['dj_levels']:
                    result[playmode][level][djlevel] = 0
            
        for musicname in resource.musictable['musics'].keys():
            for playmode in Playmodes.values:
                for difficulty, level in resource.musictable['musics'][musicname][playmode].items():
                    result[playmode][difficulty]['total'] += 1
                    result[playmode][level]['total'] += 1

                    target = self.json['musics']
                    if not musicname in target.keys():
                        continue

                    target = target[musicname]
                    if not playmode in target.keys():
                        continue

                    target = target[playmode]
                    if not difficulty in target.keys():
                        continue

                    target = target[difficulty]
                    if not 'best' in target.keys():
                        continue

                    target = target['best']

                    if 'cleartype' in target.keys():
                        cleartype = target['cleartype']
                        if cleartype is not None and cleartype['value'] is not None:
                            result[playmode][difficulty]['datacount'] += 1
                            result[playmode][level]['datacount'] += 1

                            cleartypevalue = cleartype['value']
                            result[playmode][difficulty][cleartypevalue] += 1
                            result[playmode][level][cleartypevalue] += 1
                    
                    if 'djlevel' in target.keys():
                        djlevel = target['djlevel']
                        if djlevel is not None and djlevel['value'] is not None:
                            djlevelvalue = djlevel['value']
                            result[playmode][difficulty][djlevelvalue] += 1
                            result[playmode][level][djlevelvalue] += 1
        
        return result

class Notebooks():
    notebooks: dict[str, NotebookMusic] = {}

    def get_notebook(self, musicname: str):
        if not musicname in self.notebooks:
            self.load_targetnotebook(musicname)

        if musicname in self.notebooks:
            return self.notebooks[musicname]
        
        return None
    
    def delete_notebook(self, musicname: str):
        if musicname in self.notebooks:
            self.notebooks[musicname].delete()
            del self.notebooks[musicname]
    
    def load_targetnotebook(self, musicname):
        self.notebooks[musicname] = NotebookMusic(musicname)

def rename_allfiles(musics: list[str]):
    '''短縮された記録ファイルのファイル名を修正する

    Note:
        曲名をエンコードし文字列変換したものをファイル名としている
        version0.7.0.1以前はファイル名を最大128文字と制限をしていたが
        それだとファイル名から曲名へ逆変換が不可能になって不具合を起こしたので
        該当曲のファイル名をすべて変更する

    Args:
        musics (list (string)): 曲名のリスト
    '''
    string_max_length = 128

    for music in musics:
        string = music.encode('UTF-8').hex()
        if len(string) > string_max_length:
            omitted_filename = f'{string[:string_max_length]}.json'
            omitted_filepath = join(records_basepath, omitted_filename)
            if exists(omitted_filepath):
                full_filename = f'{string}.json'
                full_filepath = join(records_basepath, full_filename)
                rename(omitted_filepath, full_filepath)
                logger.info(f'Rename {music}')
                logger.info(f'From(length: {len(omitted_filename)})\t{omitted_filename}')
                logger.info(f'To(length: {len(full_filename)})\t\t{full_filename}')

def rename_changemusicname():
    '''曲名の誤っていた記録ファイルのファイル名を修正する

    Note:
        曲名が誤っていた場合にファイル名を変更する
        INFINITASしかなかった曲がACに収録されて
        公式サイトからダウンロードしたCSVファイルの曲名が誤っていたとき等に対応する
        万一変更後のファイル名のファイルは既に存在する場合は削除してしまう
    '''
    filepath = join(resources_dirname, musicnamechanges_filename)
    if not exists(filepath):
        return
    
    try:
        with open(filepath, encoding='UTF-8')as f:
            convertlist = json.load(f)
    except Exception as ex:
        logger.exception(ex)
        return
    
    changed = []
    for target, renamed in convertlist:
        target_encoded = target.encode('UTF-8').hex()
        target_filepath = join(records_basepath, f'{target_encoded}.json')
        if exists(target_filepath):
            renamed_encoded = renamed.encode('UTF-8').hex()
            renamed_filepath = join(records_basepath, f'{renamed_encoded}.json')
            if exists(renamed_filepath):
                remove(renamed_filepath)
            rename(target_filepath, renamed_filepath)
            logger.info(f'Rename {target} to {renamed}')
            changed.append((target, renamed))
    
    return changed

