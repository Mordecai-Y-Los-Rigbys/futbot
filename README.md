# Futbot - Backend

Backend de Futbot, una plataforma donde cada usuario arma su club de jugadores, programa cómo se comportan en la cancha y los hace competir en partidos de fútbol 3 vs 3 simulados en tiempo real.

Trabajo para Ingeniería del Software (FAMAF, UNC), Laboratorio 2026. El frontend se desarrolla en un repositorio aparte.

## Qué hace

- **Usuarios y sesiones**: registro, inicio de sesión con contraseña cifrada (bcrypt) y sesión en una cookie `session_id` HttpOnly. Al registrarse, cada usuario recibe 3 comportamientos iniciales (Delantero, Mediocampista y Defensor).
- **Jugadores**: alta de jugadores con 5 atributos (`power`, `agility`, `control`, `strength`, `speed`), cada uno entre 20 y 100, que tienen que sumar exactamente 300.
- **Comportamientos**: scripts en un subconjunto de Python que deciden qué hace cada jugador en cada tick del partido. Se ejecutan en un sandbox con tiempo límite.
- **Ligas y amistosos**: creación de ligas públicas y privadas, y de amistosos que quedan esperando rival. Cuando el rival se une, el partido arranca solo.
- **Partidos en tiempo real**: un motor de simulación determinista calcula 20 ticks por segundo, y cada tick se transmite por WebSocket a los usuarios conectados.

## Stack

- Python 3.11 y FastAPI
- SQLAlchemy sobre PostgreSQL 15
- Pydantic para validación y esquemas
- Uvicorn con WebSockets
- Pytest para los tests
- Docker y Docker Compose

## Cómo levantar el proyecto

Requisitos: Docker y Docker Compose.

```bash
docker compose up --build
```

Esto levanta dos servicios:

| Servicio | Puerto | Descripción |
|---|---|---|
| `db` | 5432 | PostgreSQL 15. Al crear el volumen por primera vez también crea la base de tests `futbot_test`. |
| `api` | 8000 | La API, con hot-reload: los cambios en el código se aplican sin reiniciar el contenedor. |

Una vez levantado:

- API: http://localhost:8000
- Health check: http://localhost:8000/health

### Variables de entorno

Ya vienen configuradas en `docker-compose.yml`, así que para desarrollo no hace falta tocar nada.

| Variable | Para qué se usa |
|---|---|
| `DATABASE_URL` | Conexión a la base de desarrollo (obligatoria). |
| `FRONTEND_URL` | Origen permitido por CORS. Por defecto `http://localhost:3000`. |
| `TEST_DATABASE_URL` | Base de Postgres para los tests de integración. Tiene que terminar en `_test`. |

### Cambios en los modelos

El proyecto no usa migraciones: las tablas se crean con `Base.metadata.create_all` al arrancar la app. Esto crea las tablas que faltan, pero **no modifica las que ya existen**. Si se agrega o cambia una columna en un modelo, hay que recrear la base:

```bash
docker compose down -v
docker compose up --build
```

> `down -v` borra el volumen de Postgres, o sea, todos los datos de desarrollo.

## Tests

Los tests se corren dentro del contenedor de la API:

```bash
# Tests unitarios (usan SQLite en memoria y repositorios fake)
docker compose exec api pytest app/tests/unit

# Toda la suite, incluidos los de integración contra Postgres
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg2://futbot_user:futbot_pass@db:5432/futbot_test api pytest
```

- Si no se define `TEST_DATABASE_URL`, los tests marcados como `integration` se saltean.
- Como medida de seguridad, si `TEST_DATABASE_URL` no apunta a una base cuyo nombre termine en `_test`, los tests no arrancan. Esto evita borrar por error la base de desarrollo, ya que cada test hace `drop_all` al terminar.

## Estructura del proyecto

El código sigue los principios de Clean Architecture: la lógica de negocio no depende ni del framework HTTP ni de la base de datos.

```
app/
├── api/            # Rutas de FastAPI (REST y WebSocket) e inyección de dependencias
├── schemas/        # Modelos de Pydantic para requests y responses
├── services/       # Lógica de negocio y validaciones
├── repositories/   # Acceso a datos: interfaz abstracta (*_abstract.py) + implementación (*_sqlalchemy.py)
├── models/         # Modelos de SQLAlchemy (tablas)
├── domain/         # Enums y tipos del dominio, sin dependencias externas
├── simulation/     # Motor del partido: física, reglas y ejecución de comportamientos
│   └── behaviors/  # Sandbox, primitivas y comportamientos iniciales
├── helpers/        # Utilidades compartidas
├── tests/
│   ├── unit/        # Lógica aislada, sin I/O
│   └── integration/ # Ciclo completo HTTP + base de datos
├── database.py
├── errors.py       # ApiError y manejo del formato de errores del contrato
├── startup_checks.py
└── main.py         # Creación de la app, routers y lifespan
docs/               # Material del proyecto (alcance, casos de uso, diagramas)
docker/             # Script de inicialización de la base de tests
```

Cada endpoint pasa por las capas en el mismo orden: la ruta (`api/`) recibe el request y delega en un service, el service valida y aplica las reglas de negocio, y el repository se encarga de leer y escribir en la base. Los services reciben los repositories por su interfaz abstracta, lo que permite testearlos con repositorios fake.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/register` | Registro de usuario |
| `POST` | `/auth/log-in` | Inicio de sesión |
| `GET` | `/users/me` | Datos del usuario autenticado |
| `POST` | `/players` | Crear un jugador |
| `GET` | `/players/me` | Jugadores del usuario (paginado) |
| `GET` | `/behaviors/me` | Comportamientos del usuario (paginado) |
| `GET` | `/behaviors/{id}` | Detalle de un comportamiento |
| `GET` | `/leagues` | Listar ligas |
| `POST` | `/leagues` | Crear una liga |
| `GET` | `/friendlies` | Amistosos esperando rival |
| `POST` | `/friendlies` | Crear un amistoso |
| `POST` | `/friendlies/{id}/members` | Unirse a un amistoso como rival |
| `POST` | `/matches/{id}/connections` | Obtener el token para conectarse al WebSocket del partido |
| `WS` | `/ws/matches/{id}?token=...` | Transmisión en vivo del partido |

Los endpoints REST, salvo el registro, el inicio de sesión y `/health`, requieren la cookie `session_id`. Si falta o venció, la respuesta es `401`. El WebSocket no usa la cookie: se autentica con el token que devuelve `POST /matches/{id}/connections`.

## Contratos de la API

Algunas convenciones que conviene tener presentes al tocar un endpoint (el detalle completo está en el contrato REST):

- **Precedencia de errores**: `401` > `404` > `400` > `403` > `409`.
- **Un solo error por respuesta**: salvo en el registro, los `400` se evalúan en orden y se devuelve solo el primero: tipo de campo inválido (`invalidFieldType`), formulario incompleto (`incompleteForm`) y después las reglas de contenido.
- **Ids de ruta inválidos** (por ejemplo `/behaviors/abc`) devuelven `404`, nunca `422`.

## Motor de simulación

El partido se calcula en `app/simulation/`:

- `physics.py`: movimiento, choques, pelota, goles, posesión y patadas a la pelota.
- `match_rules.py`: cuenta regresiva, reinicio después de un gol y fin del partido (`MatchSession.advance()` calcula un tick).
- `behaviors/`: compila los comportamientos de los usuarios en un sandbox y los ejecuta con límite de tiempo por equipo.

El motor es **determinista**: con la misma semilla y los mismos equipos, el partido da exactamente los mismos ticks. La semilla de cada partido se guarda en la base y en el log, así que cualquier partido se puede reproducir.

En producción, `MatchRunner` (`app/services/match_runner.py`) corre cada partido en tiempo real y transmite los ticks. Para probar el motor sin levantar la app hay un script que simula un partido completo al instante, con dos equipos de ejemplo:

```bash
docker compose exec api python -m app.simulation.run --seed 7 --duration 60
```

## Despliegue: 

La app tiene que correr con **un solo worker**. `MatchConnectionManager` guarda las conexiones WebSocket en la memoria del proceso, y los partidos en curso también viven en ese proceso. Con varios workers, el request que une al rival y el socket del creador podrían caer en procesos distintos, y el creador nunca recibiría los ticks.

- Si `WEB_CONCURRENCY` es mayor que 1, la app aborta al arrancar (`startup_checks.py`).
- No hay que agregar `--workers` al comando de uvicorn.
- Todo envío a las conexiones pasa por `MatchConnectionManager.subscribers()`.

## WebSocket:

Uvicorn corre con `--ws websockets-sansio --ws-ping-interval 20 --ws-ping-timeout 20`. Así, una conexión muerta libera su cupo y su suscripción en 40 segundos como máximo.
