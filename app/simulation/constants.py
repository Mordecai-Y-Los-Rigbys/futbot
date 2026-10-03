"""Parámetros del motor de simulación.

Todas las constantes numéricas del motor viven acá: el resto de los módulos
las importa. Los valores son iniciales.

Unidades: distancias en "unidades de cancha" (u), tiempo en ticks.
"""

# --- Tiempo ------------------------------------------------------------------

TICKS_PER_SECOND = 20
SECONDS_PER_TICK = 1 / TICKS_PER_SECOND  # segundos por tick => 0,05s por tick

# --- Cancha y cuerpos ----------------------------------------------------------

FIELD_LENGTH = 100.0  # eje x: del arco propio al arco rival
FIELD_WIDTH = 60.0  # eje y
GOAL_WIDTH = 16.0  # ancho del arco, centrado en y = FIELD_WIDTH / 2
GOAL_Y_MIN = (FIELD_WIDTH - GOAL_WIDTH) / 2 # Palo de abajo: y=22
GOAL_Y_MAX = (FIELD_WIDTH + GOAL_WIDTH) / 2 # Palo de arriba: y=38

PLAYER_RADIUS = 2.0
BALL_RADIUS = 1.0

# --- Stats -------------------------------------------------------------
# Agregué valores base para que un jugador con pocos puntos en una stat no sea inútil
# El coeficiente marca la diferencia entre un jugador con pocos o muchos puntos en esa stat.

# speed: 
PLAYER_BASE_SPEED = 5.0
PLAYER_SPEED_PER_POINT = 0.15
# velocidad del jugador = 5 + speed * 0,15 (u/s)

# power: 
KICK_BASE_SPEED = 20.0
KICK_SPEED_PER_POINT = 0.4 
# velocidad máxima de patada = 20 + power * 0,4 (u/s)

# control: 
REACH_PER_CONTROL_POINT = 0.02
# alcance = PLAYER_RADIUS + BALL_RADIUS + control * REACH_PER_CONTROL_POINT
#                 2       +     1       + control *         0,02 (u)

# agility: 
KICK_COOLDOWN_BASE_TICKS = 30
KICK_COOLDOWN_TICKS_PER_POINT = 0.25
# cooldown = 30 - agility * 0,25 (ticks)

# --- Pelota ------------------------------------------------------------------------

BALL_FRICTION_PER_TICK = 0.98  # la velocidad se multiplica por esto cada tick
BALL_MIN_SPEED = 0.1  # por debajo (u/s) la pelota se detiene
WALL_RESTITUTION = 0.8  # fracción de velocidad que conserva al rebotar

# --- Patadas y posesión ----------------------------------------------------------

MIN_KICK_FORCE = 1
MAX_KICK_FORCE = 100
POSSESSION_PROTECTION_TICKS = 10  # nadie puede robar la pelota recién ganada
KICKER_REGAIN_BLOCK_TICKS = 5  # el pateador no puede recuperarla enseguida

# Al ganar la pelota, en vez de aparecerle de golpe al frente, se le acerca a esta velocidad.
BALL_CARRY_SPEED = 40.0 # (u/s)

# --- Choques ------------------------------------------------------------------------

COLLISION_PASSES = 10  # iteraciones maximas para resolver superposiciones de varios jugadores
DISTANCE_EPSILON = 1e-9  # dos distancias más cercanas que esto se consideran iguales

# --- Posiciones iniciales ----------------------------------------------------------

# Relativas al equipo (el visitante se espeja). 
# número del jugador: (1 = defensa, 2 = medio, 3 = delantero), 
# todos en fila sobre el eje central.
INITIAL_POSITIONS = {
    1: (12.0, FIELD_WIDTH / 2),
    2: (26.0, FIELD_WIDTH / 2),
    3: (40.0, FIELD_WIDTH / 2),
}
KICKOFF_BALL_POSITION = (FIELD_LENGTH / 2, FIELD_WIDTH / 2)

# --- Ejecución de comportamientos ---------------------------------------------------

# Tiempo máximo de ejecución del comportamiento de un jugador en un tick (segundos).
BEHAVIOR_TIME_LIMIT = 0.01
