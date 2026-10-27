from datetime import timedelta
from app.services.league_validation import MAX_DURATION

MAX_FRIENDLY_WAIT = timedelta(minutes=15)  # espera máxima del creador
MAX_DURATION_TIMEDELTA = timedelta(minutes=MAX_DURATION)  # máximo de un partido de liga
MAX_PAUSES = timedelta(seconds=45)  # 3 pausas de 15 s
WS_TOKEN_MARGIN = timedelta(minutes=9, seconds=15)  # cuentas regresivas, latencias, reconexiones

WS_TOKEN_TTL = MAX_FRIENDLY_WAIT + MAX_DURATION_TIMEDELTA + MAX_PAUSES + WS_TOKEN_MARGIN  # 35 min

FRIENDLY_COUNTDOWN = timedelta(seconds=3)  # cuenta regresiva desde que se une el rival