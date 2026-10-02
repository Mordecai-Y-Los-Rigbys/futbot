## Despliegue: un solo worker

La app debe correr con **1 worker**. `MatchConnectionManager` guarda las
conexiones WebSocket en memoria de un solo proceso: con varios workers, el REST
que une al rival y el socket del creador pueden caer en procesos distintos y el
creador no recibiría nunca los `tick`.

- Si `WEB_CONCURRENCY` es mayor que 1, la app aborta al arrancar.
- No agregar `--workers` al comando de uvicorn.
- Todo envío a conexiones pasa por `MatchConnectionManager.subscribers()`. Ese es
  el punto de enganche si se incorpora un bus (por ejemplo Redis pub/sub).

## WebSocket: ping/pong

Uvicorn corre con `--ws websockets --ws-ping-interval 20 --ws-ping-timeout 20`.
Una conexión muerta libera su cupo y su suscripción en unos 40 s como máximo.

> Hoy el comando de arranque vive solo en `docker-compose.yml`. Si se despliega
> la imagen sin compose, agregar un `CMD` al Dockerfile con los mismos flags
> (`--ws websockets --ws-ping-interval 20 --ws-ping-timeout 20`) y sin `--workers`,
> y extender `test_start_command_has_no_workers_flag_and_sets_ws_ping` para que
> también lea el Dockerfile.