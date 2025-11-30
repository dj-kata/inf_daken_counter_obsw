from datetime import datetime
from logging import getLogger

from define import Playmodes,Playtypes

logger_child_name = 'result'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded result.py')

results_dirname = 'results'
filtereds_dirname = 'filtered'

class ResultInformations():
    def __init__(self, play_mode: str, difficulty: str, level: str, notes: int, playspeed: float | None, music: str):
        self.play_mode = play_mode
        self.difficulty = difficulty
        self.level = level
        self.notes = notes
        self.playspeed = playspeed
        self.music = music

class ResultValues():
    def __init__(self, best: str | int, current: str | int, new: bool):
        self.best = best
        self.current = current
        self.new = new

class ResultOptions():
    def __init__(self, arrange: str, flip: str, assist: str, battle: bool):
        self.arrange: str = arrange
        '''配置オプション'''

        self.flip: str = flip
        '''DPオンリー 左右の譜面が入れ替わる'''

        self.assist: str = assist
        '''A-SCR or LEGACY'''

        self.battle: bool = battle
        '''DP時にBATTLEがON 両サイドがSP譜面になる'''

        self.special: bool = (arrange is not None and 'H-RAN' in arrange) or self.battle
        '''H-RAN or BATTLE'''

class ResultDetails():
    def __init__(self, graphtype: str, options: ResultOptions, clear_type: ResultValues, dj_level: ResultValues, score: ResultValues, miss_count: ResultValues, graphtarget: str):
        self.graphtype = graphtype
        self.options = options
        self.clear_type = clear_type
        self.dj_level = dj_level
        self.score = score
        self.miss_count = miss_count
        self.graphtarget = graphtarget

class Result():
    def __init__(self, play_side: str, rival: bool, dead: bool, informations: ResultInformations | None, details: ResultDetails | None):
        self.play_side: str = play_side
        self.rival: bool = rival
        self.dead: bool = dead

        self.informations: ResultInformations | None = informations
        self.details: ResultDetails | None = details

        self.set_playtype()

        now = datetime.now()
        self.timestamp = f'{now.strftime("%Y%m%d-%H%M%S")}'
    
    def set_playtype(self):
        '''プレイの種類をセットする
        
        DPでなおかつBATTLEの場合は'DP BATTLE'とする
        '''
        self.playtype = None

        if self.informations is None:
            return
        if self.informations.play_mode is None:
            return
        if self.informations.difficulty is None:
            return
        
        if self.informations.play_mode == Playmodes.SP:
            self.playtype = Playmodes.SP
            return
        
        if self.details is None:
            return
        if self.details.options is None:
            return
        
        if not self.details.options.battle:
            self.playtype = Playmodes.DP
        else:
            self.playtype = Playtypes.DPBATTLE
        
    def has_new_record(self):
        return any([
            self.details.clear_type is not None and self.details.clear_type.new,
            self.details.dj_level is not None and self.details.dj_level.new,
            self.details.score is not None and self.details.score.new,
            self.details.miss_count is not None and self.details.miss_count.new
        ])

class RecentResult():
    class NewFlags():
        cleartype: bool = False
        djlevel: bool = False
        score: bool = False
        misscount: bool = False
    
    timestamp: str
    musicname: str = None
    playtype: str = None
    difficulty: str = None
    news: NewFlags = None
    latest: bool = False
    saved: bool = False
    filtered: bool = False

    def __init__(self, timestamp: str):
        self.timestamp = timestamp
        self.news = self.NewFlags()
    
    def encode(self):
        return {
            'timestamp': self.timestamp,
            'musicname': self.musicname,
            'playtype': self.playtype,
            'difficulty': self.difficulty,
            'news_cleartype': self.news.cleartype,
            'news_djlevel': self.news.djlevel,
            'news_score': self.news.score,
            'news_misscount': self.news.misscount,
            'latest': self.latest,
            'saved': self.saved,
            'filtered': self.filtered,
        }
