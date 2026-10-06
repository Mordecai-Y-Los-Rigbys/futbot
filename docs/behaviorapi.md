# API DE CÓDIGO DE COMPORTAMIENTOS
Esta API define el código que el usuario puede escribir como comportamiento de un jugador y las primitivas que el sistema le provee.
## Reglas de validez
Se considera **inválido** cualquier código que contenga:
- `import` de cualquier tipo.
- Llamadas de la forma `nombre()` a algo que no sea una primitiva del sistema. Incluye definir funciones (`def`, `lambda`), definir o construir clases y objetos (`class`), y llamar a funciones nativas de Python como `abs`, `min`, `max`, `len`, `round` o `print`.
- Estructuras de repetición: `for`, `while`, comprensiones (de listas, diccionarios o conjuntos) y generadores.
- Más de 250 líneas.
- Errores de sintaxis de Python.
Se permite:
- Asignaciones y lectura de variables.
- `if` / `elif` / `else`.
- Operadores aritméticos, de comparación y lógicos (`and`, `or`, `not`).
- Literales: números, strings (`"speed"`), `True`, `False` y `None`.
- Tuplas y acceso por índice (`p[0]`).

## Ejecución
- El código de cada jugador se ejecuta completo una vez por tick, desde cero: las variables no se conservan de un tick al siguiente.
- Los comportamientos no se ejecutan durante las pausas ni las cuentas regresivas. Después de un gol, los jugadores y la pelota vuelven al instante a sus posiciones iniciales y el juego sigue en el tick siguiente. 
- **Una acción de cada tipo por tick:** se aplica como máximo una acción de movimiento (`move_in_direction` o `go_to`) y una de patada (`kick` o `kick_to`). Si se llama más de una del mismo tipo, vale la última.
- **Errores y límite de tiempo:** si una primitiva alza un error, Python alza un error, o la ejecución supera el límite de tiempo por tick, la ejecución se corta. Las acciones de ese tick se descartan y el jugador se queda quieto ese tick. El partido continúa. 

## Sistema de coordenadas
Todas las coordenadas están en unidades de cancha y son **relativas al equipo del jugador**:
- El origen `(0, 0)` es la esquina inferior izquierda, del lado del arco propio.
- `x` crece hacia el arco rival, de 0 a `field_length`.
- `y` crece hacia arriba, de 0 a `field_width`.
- El arco propio está siempre en `x = 0` y el rival siempre en `x = field_length`, sin importar de qué lado de la cancha juegue el equipo. El servidor hace la traducción, así que el mismo comportamiento funciona igual de local y de visitante.
- Las direcciones también son relativas: `move_in_direction(1, 0)` es siempre avanzar hacia el arco rival y `move_in_direction(0, 1)` es siempre ir hacia arriba.
Las primitivas aceptan coordenadas enteras o con decimales, y devuelven posiciones con decimales.

## Stats y su efecto
| Stat       | Afecta a |
|------------|----------|
| `power`    | Velocidad de la pelota al patear (`kick`, `kick_to`). |
| `agility`  | Tiempo mínimo entre dos patadas (cooldown). |
| `control`  | Distancia a la que el jugador alcanza la pelota. |
| `strength` | Quién empuja a quién en un choque entre jugadores, y quién se queda con la pelota cuando varios la alcanzan. |
| `speed`    | Velocidad de movimiento. |

## Posesión de la pelota 
Un jugador puede ganar la pelota si está dentro de su alcance, que depende de la stat control. Si varios la alcanzan a la vez, la gana el de mayor strength; si empatan, el más cercano; si también empatan, se sortea. Quien gana la pelota no puede perderla durante medio segundo. Quien patea no puede volver a agarrarla durante un cuarto de segundo. Mientras un jugador tiene la pelota, la lleva delante suyo, en la dirección en la que se movió por última vez. 

## Constantes
Valores iniciales:

    field_length  = 100
    field_width   = 60
    goal_width    = 16      # ancho del arco, centrado en y = field_width / 2
    player_radius = 2
    ball_radius   = 1

    my_goal       = (0, field_width / 2)
    opponent_goal = (field_length, field_width / 2)
    field_center  = (field_length / 2, field_width / 2)

    bottom_left_corner  = (0, 0)
    bottom_right_corner = (field_length, 0)
    top_left_corner     = (0, field_width)
    top_right_corner    = (field_length, field_width)

## Primitivas

### Numeración de jugadores
Los titulares de cada equipo se numeran del 1 al 3. Un suplente que entra hereda el número del titular al que reemplaza.

### Movimiento
#### `move_in_direction(dir_x: float, dir_y: float) -> None`
El jugador se mueve en la dirección (dir_x, dir_y) a la velocidad dada por speed. Solo importa la dirección, no el tamaño: (3, 1), (6, 2) y (0.3, 0.1) producen el mismo movimiento. Con (0, 0), el jugador se queda quieto. 

#### `go_to(x: float, y: float) -> None`
El jugador se mueve hacia `(x, y)` a la velocidad dada por `speed` y se detiene al llegar. Si `x` o `y` quedan fuera de la cancha, se ajustan al borde (`x` entre 0 y `field_length`, `y` entre 0 y `field_width`).

### Patadas a la pelota
Si el jugador no tiene la pelota, o no pasó el tiempo mínimo entre patadas (`agility`), las patadas no hacen nada. 
La velocidad de la pelota depende de dos valores: 
- La stat `power` del jugador: su potencia máxima. 
- El parámetro `force`: qué porcentaje de esa potencia máxima usa en este tiro, de 1 a 100. Es opcional; si no se indica, vale 100 (potencia máxima). Valores fuera del rango se ajustan a 1 o a 100. 

#### `kick(force: int = 100) -> None`
Patea la pelota hacia adelante, en la línea que forman el jugador y la pelota. 
#### `kick_to(x: float, y: float, force: int = 100,) -> None`
Patea la pelota hacia `(x, y)`. Si `x` o `y` quedan fuera de la cancha, se ajustan al borde. Si `(x, y)` queda detrás del jugador (respecto de la línea que forman él y la pelota),patea de costado: a 90° de esa línea, hacia el lado donde está `(x, y)`. 

### Información del propio jugador
#### `my_position() -> (float, float)`
Devuelve la posición `(x, y)` del propio jugador.
#### `my_number() -> int`
Devuelve el número del propio jugador (1 a 3).
#### `i_have_ball() -> bool`
Devuelve `True` si el propio jugador tiene la pelota.

### Información de otros jugadores
#### `teammate_position(num: int) -> (float, float)`
Devuelve la posición `(x, y)` del compañero titular número `num`. Si `num` es el número propio, devuelve la posición propia. Alza un error si `num` no está entre 1 y 3.
#### `opponent_position(num: int) -> (float, float)`
Devuelve la posición `(x, y)` del rival titular número `num`. Alza un error si `num` no está entre 1 y 3.
#### `teammate_stat(num: int, stat: str) -> int`
Devuelve el valor de `stat` del compañero titular número `num`. Alza un error si `num` no está entre 1 y 3, o si `stat` no es `"power"`, `"agility"`, `"control"`, `"strength"` o `"speed"`.
#### `opponent_stat(num: int, stat: str) -> int`
Igual que `teammate_stat`, para el rival titular número `num`.

### Pelota
#### `ball_position() -> (float, float)`
Devuelve la posición `(x, y)` de la pelota.
#### `teammate_has_ball() -> bool`
Devuelve `True` si algún compañero (sin contar al propio jugador) tiene la pelota.
#### `opponent_has_ball() -> bool`
Devuelve `True` si algún rival tiene la pelota.
#### `nobody_has_ball() -> bool`
Devuelve `True` si ningún jugador tiene la pelota, incluido el propio.

### Utilidades
#### `distance(x1: float, y1: float, x2: float, y2: float) -> float`
Devuelve la distancia entre `(x1, y1)` y `(x2, y2)`.

### Tiempo
El reloj cuenta solo el tiempo de juego efectivo del partido entero: no avanza durante las pausas ni durante: 
las pausas (hidratación y entretiempo) 
la cuenta regresiva previa a cada período
Durante esos momentos los comportamientos no se ejecutan. 
#### `elapsed_time() -> float`
Devuelve los segundos de juego transcurridos desde el inicio del partido.
#### `remaining_time() -> float`
Devuelve los segundos de juego que faltan para el final del partido.
#### `current_period() -> int`
Devuelve el período actual, de 1 a 4.


