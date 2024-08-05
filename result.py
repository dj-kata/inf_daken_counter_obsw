from datetime import datetime
from logging import getLogger

logger_child_name = 'result'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded result.py')

results_dirname = 'results'
filtereds_dirname = 'filtered'

class ResultInformations():
    def __init__(self, play_mode: str, difficulty: str, level: str, notes: int, music: str):
        self.play_mode = play_mode
        self.difficulty = difficulty
        self.level = level
        self.notes = notes
        self.music = music

class ResultValues():
    def __init__(self, best: str | int, current: str | int, new: bool):
        self.best = best
        self.current = current
        self.new = new

class ResultOptions():
    def __init__(self, arrange: str, flip: str, assist: str, battle: bool):
        self.arrange = arrange
        self.flip = flip
        self.assist = assist
        self.battle = battle
        self.special = (arrange is not None and 'H-RAN' in arrange) or self.battle

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
    def __init__(self, informations: ResultInformations, play_side: str, rival: bool, dead: bool, details: ResultDetails):
        self.informations: ResultInformations = informations
        self.play_side = play_side
        self.rival = rival
        self.dead = dead
        self.details: ResultDetails = details

        now = datetime.now()
        self.timestamp = f"{now.strftime('%Y%m%d-%H%M%S')}"
    
    def has_new_record(self):
        return any([
            self.details.clear_type is not None and self.details.clear_type.new,
            self.details.dj_level is not None and self.details.dj_level.new,
            self.details.score is not None and self.details.score.new,
            self.details.miss_count is not None and self.details.miss_count.new
        ])

