from datetime import timedelta

MAX_FRIENDLY_WAIT = timedelta(minutes=15)  # espera máxima del creador
MAX_MATCH_DURATION = timedelta(minutes=10)  # máximo de un partido de liga
WS_TOKEN_MARGIN = timedelta(minutes=10)  # cuenta regresiva, pausas, latencias, reconexiones

WS_TOKEN_TTL = MAX_FRIENDLY_WAIT + MAX_MATCH_DURATION + WS_TOKEN_MARGIN