# Análisis del Problema — Futbot

**Futbot** es un juego de fulbito 2D. Emula partidos 3v3 de fulbito con 4 tiempos, en el que a los jugadores se les asignan comportamientos. Los jugadores **no se controlan con controles**, sino que se controlan mediante código.

## Partes del sistema

### El partido

Es un evento que dura una cantidad de tiempo y se compone de 4 lapsos (dura 4 tiempos de misma duración). Durante el partido hay 3 pausas: las dos de hidratación y el entretiempo.

Cada partido se juega entre dos usuarios, y cada usuario representa un equipo llamado **club**. Cada equipo se compone de 6 jugadores: tres titulares y tres suplentes, que han de pertenecer a un club.

No tienen un rol definido; todo el comportamiento depende del código de control (+ stats).

**Reglas del partido:**
- La pelota no puede irse.
- No hay faltas.
- No hay laterales.
- No hay lesiones.
- No hay stamina.
- No hay tarjetas amarillas ni rojas.
- No hay corners.
- No hay penales.
- No hay roles predeterminados fuera del comportamiento.
- Solo hay saques de media cancha, goles y cambios.

### Los cambios

Hay 1 (y solo 1) cambio por ventana, y hay una (y solo una) ventana por tiempo pausado. Como hay 3 pausas, hay en total 3 ventanas y por ende 3 cambios.

El comportamiento de los jugadores puede reasignarse durante el partido.

Se da un **"tiempo de gracia"** antes del partido (a definir por nosotros) en donde los usuarios pueden cambiar la formación y reasignar comportamientos si quieren.

> **PREGUNTAR:** dónde arrancan los jugadores.

### Qué se debe ver durante el partido

- Tus jugadores, con sus nombres, comportamientos y stats.
- Los jugadores rivales, con sus nombres y stats (**no** comportamientos).
- Los nombres de los usuarios y de los clubes.

> **Preguntar:** si también se muestra el avatar de los clubes.

Se pueden jugar partidos en ligas o amistosos.

> Queda a decisión nuestra el manejo de las colisiones.

---

### Las Ligas

Tienen: nombre, admin, privacidad (pública o privada), contraseña (si son privadas), clubes, mínimo de clubes, máximo de clubes, y duración de partido (con la duración de sus tiempos).

**Estados de una liga:**
1. Sin arrancar
2. Canceladas
3. Arrancadas
4. Finalizadas

**Creación:** para existir, debe ser creada por un usuario, que va a ser el **admin**. El admin define:
- El nombre.
- La privacidad (y la contraseña, en caso de ser necesario).
- El mínimo (no puede ser menor a 3).
- El máximo (N, a definir).

Al ser creada, comienza en el estado "sin arrancar".

**Estado "sin arrancar":**
- Los clubes pueden unirse y abandonar, siempre y cuando no se supere el máximo.
- El admin puede cancelarla, por lo que la liga no se podrá jugar.

> **Preguntar:** una vez cancelada, ¿una liga queda cerrada para siempre?

**Arranque de la liga:** si la cantidad de clubes está entre el mínimo y el máximo, el admin puede arrancarla.

**Estado "arrancada":**
- Los clubes no pueden unirse ni abandonar.
- El admin no puede cancelar la liga.
- La liga se juega hasta que se terminan todos los partidos.

**Puntuación:**
- Ganar: 3 puntos.
- Empatar: 1 punto.
- Perder: 0 puntos.

Es un **todos contra todos**. Por ende, si hay N clubes, se juegan:

$$(N - 1) \times N / 2 \text{ partidos}$$

Hay un fixture y hay tabla de posiciones.

> **Preguntar** bien el fixture.

> **Detalle:** reducir tiempo de liga.

Un club puede jugar varias ligas a la vez.

**Condiciones para unirse a una liga:**
Un usuario solo se puede unir a una liga si tiene al menos 6 jugadores y al menos un comportamiento. Para unirse, debe elegir 6 jugadores y, una vez elegidos, no pueden ser sustituidos por otros del plantel.

Cuando se eligen los jugadores, se eligen también comportamientos por defecto y (creemos que hay que preguntar) su posición, y así se genera un equipo por defecto asociado al usuario.

> **Preguntar:** si entre partidos puede cambiar ese equipo por defecto.

---

### Los usuarios

**Atributos:**
- Nombre de usuario (único).
- Mail (único).
- Contraseña.
- Nombre de club.
- Avatar.

> **Preguntar:**
> - ¿Un usuario puede cambiarse el nombre de club? ¿Y el avatar?
> - El nombre de club no debería repetirse.
> - ¿Son todos los parámetros del usuario modificables?

**Los usuarios pueden:**
- Crear ligas.
- Cancelar ligas si las crearon y no están arrancadas.
- Crear y eliminar jugadores (**no** editar).
- CRUD de comportamientos (deben ser validados).
- Unirse a ligas.
- Abandonar ligas si no están arrancadas.
- Asignar comportamientos a jugadores.
- Jugar partidos amistosos.
- Ver partidos ajenos (de ligas públicas).

> **Preguntar** sobre amistosos públicos y privados.

---

### Los jugadores

Tienen nombre (único por usuario) y atributos, los **PACSS**:

| Atributo | Descripción |
|---|---|
| **P** | Power |
| **A** | Agility (agilidad) |
| **C** | Control |
| **S** | Strength |
| **S** | Speed |

**Reglas de los PACSS:**
- Deben sumar exactamente 300 entre todos (ni más ni menos).
- Cada uno va de 20 a 100.

Una vez se define un jugador, **sus atributos quedan sin poder ser editados**.

---

### Los comportamientos

Existen independientemente de los jugadores. Tienen un nombre (único por usuario) y un código.

**Validación del código:**
- El código tiene que ser validado.
- Está prohibido inyectar código que pueda afectar la integridad del sistema.

**Deberíamos incluir:**
- Una guía explicando cómo deberían programar el comportamiento y qué cosas son inválidas.
- Comandos primitivos para armar comportamientos.
- Comportamientos por defecto (correr).

Para programar un comportamiento se puede usar la posición de la pelota, de los jugadores y de cualquier punto de la cancha.

**Lo que NO se puede hacer:** programar un comportamiento a partir de otro. Por ejemplo
 ```python
  if(Jugador 2 tiene la pelota && Jugador 2 menos de mitad de cancha):
    AvanzarHacia(Area de penales)
    PedirPase()
 ```

