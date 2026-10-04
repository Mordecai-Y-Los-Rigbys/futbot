import enum

class LeagueStatus(str, enum.Enum):
    preparation = "preparation"
    started = "started"
    cancelled = "cancelled"
    finished = "finished"
