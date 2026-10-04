from datetime import timedelta
from app.services.league_validation import MAX_DURATION

MAX_FRIENDLY_WAIT = timedelta(minutes=15)  # espera máxima del creador
MAX_DURATION_TIMEDELTA = timedelta(minutes=MAX_DURATION)  # máximo de un partido de liga
WS_TOKEN_MARGIN = timedelta(minutes=10)  # cuenta regresiva, pausas, latencias, reconexiones

WS_TOKEN_TTL = MAX_FRIENDLY_WAIT + MAX_DURATION_TIMEDELTA + WS_TOKEN_MARGIN

FRIENDLY_COUNTDOWN = timedelta(seconds=10)  # cuenta regresiva desde que se une el rival