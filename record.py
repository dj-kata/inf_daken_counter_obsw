import json
from os import remove,mkdir,rename
from os.path import join,exists
from logging import getLogger
from threading import Thread
from copy import deepcopy

logger_child_name = 'record'

logger = getLogger().getChild(logger_child_name)
logger.debug(f'loaded resources.py')

#from version import version
from resources import resource,resources_dirname
from define import define

records_basepath = 'records'

musicnamechanges_filename = 'musicnamechanges.res'

recent_filename = 'recent.json'
summary_filename = 'summary.json'

if not exists(records_basepath):
    mkdir(records_basepath)

class Notebook():
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
    def __init__(self, maxcount):
        self.filename = recent_filename
        self.maxcount = maxcount
        super().__init__()

        if not 'version' in self.json.keys() or self.json['version'] != version:
            self.json = {'version': version}
            self.save()
            return
    
    def append(self, result, saved, filtered):
        if not 'timestamps' in self.json.keys():
            self.json['timestamps'] = []
        self.json['timestamps'].append(result.timestamp)

        if not 'results' in self.json.keys():
            self.json['results'] = {}
        if result.details.options is None:
            option = None
        else:
            option = ','.join([v for v in [result.details.options.arrange, result.details.options.flip] if v is not None])
        self.json['results'][result.timestamp] = {
            'play_mode': result.informations.play_mode,
            'difficulty': result.informations.difficulty,
            'music': result.informations.music,
            'clear_type_new': result.details.clear_type is not None and result.details.clear_type.new,
            'dj_level_new': result.details.dj_level is not None and result.details.dj_level.new,
            'score_new': result.details.score is not None and result.details.score.new,
            'miss_count_new': result.details.miss_count is not None and result.details.miss_count.new,
            'update_clear_type': result.details.clear_type.current if result.details.clear_type is not None and result.details.clear_type.new else None,
            'update_dj_level': result.details.dj_level.current if result.details.dj_level is not None and result.details.dj_level.new else None,
            'update_score': result.details.score.current - result.details.score.best if result.details.score is not None and result.details.score.new else None,
            'update_miss_count': result.details.miss_count.current - result.details.miss_count.best if result.details.miss_count is not None and result.details.miss_count.new and result.details.miss_count.best is not None else None,
            'option': option,
            'play_side': result.play_side,
            'has_loveletter': result.rival,
            'has_graphtargetname': result.details.graphtarget == 'rival',
            'saved': saved,
            'filtered': filtered
        }

        while len(self.json['timestamps']) > self.maxcount:
            del self.json['results'][self.json['timestamps'][0]]
            del self.json['timestamps'][0]
    
    @property
    def timestamps(self):
        if not 'timestamps' in self.json.keys():
            return []
        return self.json['timestamps']
    
    def get_result(self, timestamp):
        if not 'results' in self.json.keys() or not timestamp in self.json['results']:
            return None
        return self.json['results'][timestamp]

class NotebookSummary(Notebook):
    def __init__(self):
        self.filename = summary_filename
        super().__init__()
    
    def start_import(self):
        """全曲の記録の取り込みを開始する
        """
        self.counter = [None, None]
        Thread(target=self.import_async).start()
        return self.counter
    
    def import_async(self):
        """非同期で全曲の記録を取り込む
        """
        self.counter[0] = 0
        self.counter[1] = len(resource.musictable['musics'])
        for musicname in resource.musictable['musics'].keys():
            notebook = NotebookMusic(musicname)
            self.import_targetmusic(musicname, notebook)
            self.counter[0] += 1
    
    def import_targetmusic(self, musicname, notebook):
        """対象の曲の記録を取り込む
        
        Args:
            musicname (str): 曲名
            notebook (NotebookMusic): 対象曲の記録
        """
        if not 'musics' in self.json.keys():
            self.json['musics'] = {}
        self.json['musics'][musicname] = {'SP': {}, 'DP': {}}
        music_item = resource.musictable['musics'][musicname]
        for playmode in define.value_list['play_modes']:
            for difficulty in define.value_list['difficulties']:
                if not difficulty in music_item[playmode].keys() or music_item[playmode][difficulty] is None:
                    continue

                r = notebook.get_recordlist(playmode, difficulty)
                if r is None:
                    continue

                self.json['musics'][musicname][playmode][difficulty] = {}
                target = self.json['musics'][musicname][playmode][difficulty]
                if 'latest' in r.keys() and 'timestamp' in r['latest'].keys():
                    target['latest'] = r['latest']['timestamp']
                else:
                    target['latest'] = None

                if 'timestamps' in r.keys():
                    target['playcount'] = len(r['timestamps'])
                else:
                    target['playcount'] = None

                if 'best' in r.keys():
                    if 'clear_type' in r['best'].keys() and r['best']['clear_type'] is not None:
                        target['cleartype'] = r['best']['clear_type']['value']
                    else:
                        target['cleartype'] = None
                    
                    if 'dj_level' in r['best'].keys() and r['best']['dj_level'] is not None:
                        target['djlevel'] = r['best']['dj_level']['value']
                    else:
                        target['djlevel'] = None

                    if 'score' in r['best'].keys() and r['best']['score'] is not None:
                        target['score'] = r['best']['score']['value']
                    else:
                        target['score'] = None

                    if 'miss_count' in r['best'].keys() and r['best']['miss_count'] is not None:
                        target['misscount'] = r['best']['miss_count']['value']
                    else:
                        target['misscount'] = None
                else:
                    target['cleartype'] = None
                    target['djlevel'] = None
                    target['score'] = None
                    target['misscount'] = None

class NotebookMusic(Notebook):
    achievement_default = {
        'fixed': {'clear_type': None, 'dj_level': None},
        'S-RANDOM': {'clear_type': None, 'dj_level': None},
        'DBM': {'clear_type': None, 'dj_level': None}
    }

    def __init__(self, music):
        """曲名をエンコード&16進数変換してファイル名にする

        Note:
            ファイル名から曲名にデコードする場合は
            bytes.fromhex('ファイル名').decode('UTF-8')
        """
        self.filename = f"{music.encode('UTF-8').hex()}.json"
        super().__init__()
    
    def get_recordlist(self, play_mode, difficulty):
        """対象のプレイモード・難易度のレコードのリストを取得する

        Args:
            play_mode (str): SP か DP
            difficulty (str): NORMAL か HYPER か ANOTHER か BEGINNER か LEGGENDARIA

        Returns:
            list: レコードのリスト
        """
        if not play_mode in self.json.keys():
            return None
        if not difficulty in self.json[play_mode].keys():
            return None
        
        target = self.json[play_mode][difficulty]
        if 'timestamps' in target.keys() and len(target['timestamps']) > 0 and not 'achievement' in target.keys():
            self.generate_achievement_from_histories(target)
            self.save()
        
        return target

    def delete(self):
        if exists(self.filepath):
            remove(self.filepath)
    
    def insert_latest(self, target, result, options):
        target['latest'] = {
            'timestamp': result.timestamp,
            'clear_type': {
                'value': result.details.clear_type.current,
                'new': result.details.clear_type.new
            },
            'dj_level': {
                'value': result.details.dj_level.current,
                'new': result.details.dj_level.new
            },
            'score': {
                'value': result.details.score.current,
                'new': result.details.score.new
            },
            'miss_count': {
                'value': result.details.miss_count.current,
                'new': result.details.miss_count.new
            },
            'options': options
        }

    def insert_history(self, target, result, options):
        if not 'timestamps' in target.keys():
            target['timestamps'] = []
        target['timestamps'].append(result.timestamp)

        if not 'history' in target.keys():
            target['history'] = {}
        target['history'][result.timestamp] = {
            'clear_type': {
                'value': result.details.clear_type.current,
                'new': result.details.clear_type.new
            },
            'dj_level': {
                'value': result.details.dj_level.current,
                'new': result.details.dj_level.new
            },
            'score': {
                'value': result.details.score.current,
                'new': result.details.score.new
            },
            'miss_count': {
                'value': result.details.miss_count.current,
                'new': result.details.miss_count.new
            },
            'options': options
        }

    def update_best_result(self, target, result, options):
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
        """達成記録を過去の記録データから作成する

        Args:
            target (dict): 記録の対象部分
        """
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
            if not 'special' in record.keys() or record['options'].keys():
                continue

            achievement_key = None
            if not record['options']['special']:
                if record['options']['arrange'] in [None, 'MIRROR', 'OFF/MIR', 'MIR/OFF', 'MIR/MIR']:
                    achievement_key = 'fixed'
                if record['options']['arrange'] in ['S-RANDOM', 'S-RAN/S-RAN']:
                    achievement_key = 'S-RANDOM'
            else:
                if record['options']['battle'] and record['options']['arrange'] == 'OFF/MIR' and record['options']['assist'] == 'A-SCR':
                    achievement_key = 'DBM'
            if achievement_key is None:
                continue

            for key, valuelist in targetkeys.items():
                value = record[key]['value']
                is_updated = achievement[achievement_key][key] is None
                if not is_updated:
                    index_current = valuelist.index(value)
                    index_recorded = valuelist.index(achievement[achievement_key][key])
                    if index_current > index_recorded:
                        is_updated = True
                if is_updated:
                    achievement[achievement_key][key] = value
        
    def update_achievement(self, target, result):
        """達成記録を更新する

        Args:
            target (dict): 記録の対象部分
            result (Result): 対象のリザルト
        
        Returns:
            bool: 更新があった
        """
        if not 'achievement' in target.keys():
            target['achievement'] = deepcopy(self.achievement_default)
        
        details = result.details
        options = details.options

        achievement_key = None
        if not options.special:
            if options.arrange in [None, 'MIRROR', 'OFF/MIR', 'MIR/OFF', 'MIR/MIR']:
                achievement_key = 'fixed'
            if options.arrange in ['S-RANDOM', 'S-RAN/S-RAN']:
                achievement_key = 'S-RANDOM'
        else:
            if options.battle and options.arrange == 'OFF/MIR' and options.assist == 'A-SCR':
                achievement_key = 'DBM'
        if achievement_key is None:
            return False
        
        updated = False
        results = [
            ('clear_type', define.value_list['clear_types'], details.clear_type.current),
            ('dj_level', define.value_list['dj_levels'], details.dj_level.current)
        ]
        for key, valuelist, value in results:
            is_updated = target['achievement'][achievement_key][key] is None
            if not is_updated:
                index_current = valuelist.index(value)
                index_recorded = valuelist.index(target['achievement'][achievement_key][key])
                if index_current > index_recorded:
                    is_updated = True
            if is_updated:
                target['achievement'][achievement_key][key] = value
                updated = True
        
        return updated

    def insert(self, result):
        """対象のリザルトを記録に追加する

        Args:
            result (Result): 追加対象のリザルト
        """
        if result.informations.play_mode is None:
            return
        if result.informations.difficulty is None:
            return
        if result.informations.notes is None:
            return
        
        target = self.json

        if not result.informations.play_mode in target.keys():
            target[result.informations.play_mode] = {}
        target = target[result.informations.play_mode]

        if not result.informations.difficulty in target.keys():
            target[result.informations.difficulty] = {}
        target = target[result.informations.difficulty]

        target['notes'] = result.informations.notes

        options = result.details.options
        if options is not None:
            options_value = {
                'arrange': options.arrange,
                'flip': options.flip,
                'assist': options.assist,
                'battle': options.battle,
                'special': options.special
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
        
        if result.details.options is not None:
            if self.update_achievement(target, result):
                updated = True

        if updated:
            self.save()
    
    def update_best_musicselect(self, values):
        """選曲画面から取り込んだ認識結果からベスト記録を更新する

        Args:
            values (dict): 認識結果
        """
        updated = False

        playmode = values['playmode']
        difficulty = values['difficulty']
        if not playmode in self.json.keys():
            self.json[playmode] = {}
            updated = True
        if not difficulty in self.json[playmode].keys():
            self.json[playmode][difficulty] = {'timestamps': [], 'history': {}, 'best': {}}
            updated = True
        if not 'best' in self.json[playmode][difficulty].keys():
            self.json[playmode][difficulty]['best'] = {}
            updated = True
        target = self.json[playmode][difficulty]['best']
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

    def delete_history(self, play_mode, difficulty, timestamp):
        """指定の記録を削除する

        対象の記録が現在のベスト記録の場合はベストから削除して
        それより古い記録に遡り、直近のベスト記録を探して
        見つかった場合はそれにする。

        Args:
            play_mode: プレイモード(SP or DP)
            difficulty: 難易度(NORMAL - LEGGENDARIA)
            timestamp: 削除対象のタイムスタンプ
        """
        if not play_mode in self.json.keys():
            return
        if not difficulty in self.json[play_mode].keys():
            return
        
        target = self.json[play_mode][difficulty]

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

def rename_allfiles(musics):
    """短縮された記録ファイルのファイル名を修正する

    Note:
        曲名をエンコードし文字列変換したものをファイル名としている
        version0.7.0.1以前はファイル名を最大128文字と制限をしていたが
        それだとファイル名から曲名へ逆変換が不可能になって不具合を起こしたので
        該当曲のファイル名をすべて変更する

    Args:
        musics (list (string)): 曲名のリスト
    """
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
    """曲名の誤っていた記録ファイルのファイル名を修正する

    Note:
        曲名が誤っていた場合にファイル名を変更する
        INFINITASしかなかった曲がACに収録されて
        公式サイトからダウンロードしたCSVファイルの曲名が誤っていたとき等に対応する
        万一変更後のファイル名のファイルは既に存在する場合は削除してしまう
    """
    filepath = join(resources_dirname, musicnamechanges_filename)
    if not exists(filepath):
        return
    
    try:
        with open(filepath, encoding='UTF-8')as f:
            convertlist = json.load(f)
    except Exception as ex:
        logger.debug(ex)
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

