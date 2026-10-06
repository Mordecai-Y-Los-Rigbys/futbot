import os
from collections.abc import Mapping


def ensure_single_worker(environ: Mapping[str, str] | None = None) -> None:
    """Aborta si se configuró más de un worker.

    MatchConnectionManager guarda las conexiones en memoria de un solo
    proceso. Con varios workers, el REST que une al rival y el socket del
    creador pueden caer en procesos distintos y el creador no recibiría
    nunca los `tick`.
    """
    env = os.environ if environ is None else environ
    try:
        workers = int(env.get("WEB_CONCURRENCY", "1"))
    except ValueError:
        return
    if workers > 1:
        raise RuntimeError(
            f"La aplicación debe correr con 1 worker (WEB_CONCURRENCY={workers}): "
            "las conexiones WebSocket viven en memoria de un solo proceso."
        )
