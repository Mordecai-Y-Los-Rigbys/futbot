# FUTBOT: Alcance del proyecto

*Mordecai y los Rigbys — Alcance*

Futbot es un juego y simulador web de partidos de fútbol 2D con vista cenital en donde, al momento de controlar a los jugadores en cancha, solamente se podrán utilizar bloques de código, llamados comportamientos – los usuarios deben programar a sus jugadores.

## Características Principales

### Usuarios y Clubes

Los usuarios se deben registrar con nombre, mail y contraseña. Al registrarse, crean su club con nombre de club y avatar. Los usuarios pueden:

- Administrar sus jugadores.
- Administrar sus comportamientos.
- Crear, administrar y participar en ligas.
- Jugar partidos amistosos y de ligas.
- Ver partidos y rankings de ligas.
- Ver el ranking global.

### Jugadores y Atributos

Cada Usuario deberá crear sus propios jugadores. Cada jugador será definido con un nombre y 5 atributos:

- **Power:** Fuerza con la que patea el jugador.
- **Agility:** Cooldown en la que patea el jugador.
- **Control:** Distancia desde la que puede tocar la pelota.
- **Strength:** Cuanto se impone en el choque contra otros jugadores.
- **Speed:** Velocidad a la cual el jugador se moverá.

Cada uno de estos atributos tendrá entre 20 y 100 puntos. El jugador debe tener estrictamente 300 puntos de atributos totales, es decir, los atributos deben sumar 300 entre todos.

### Comportamientos

Los comportamientos son bloques de código que definen el actuar de los jugadores durante un partido. Cada comportamiento tiene un nombre único y un código. El código debe estar escrito en Python y debe cumplir con el contrato de API de comportamientos.

Los comportamientos se administran (i.e. pueden ser creados, modificados y eliminados) independientemente de los jugadores y muchos jugadores pueden usar el mismo comportamiento en un partido.

### Ligas

Una liga es una competencia entre distintos clubes que se enfrentarán en una modalidad de todos contra todos. Cada usuario podrá crear, administrar y participar en Ligas.

Para crear una liga, el usuario deberá ingresar: nombre, mínimo (mayor o igual a 3) y máximo de participantes, privacidad (pública o privada con contraseña), duración de partidos y un equipo para jugar en ella. Una vez creada, se encuentra en estado de preparación. En este estado, el usuario creador puede cancelarla o iniciarla.

También en el estado de preparación, otros clubes pueden unirse a la liga mientras la cantidad de participantes no haya llegado al máximo. Para unirse, un club debe formar un equipo con seis integrantes y, si la liga es privada, ingresar correctamente la contraseña de la liga.

Los seis integrantes del equipo tienen un rol: tres son suplentes, uno es titular defensa, uno es titular mediocampo y uno es titular delantero. Una vez formado el equipo, el plantel queda fijo: no pueden usarse más jugadores en ningún partido que los seis elegidos (aunque se pueden reasignar sus comportamientos), y el club comienza a ser participante de la liga. Mientras la liga siga en estado de preparación, el club participante puede abandonarla. El creador no puede abandonar la liga.

Una vez se hayan unido al menos el mínimo de participantes, el creador puede iniciar la liga. Al iniciar, automáticamente se programan los partidos con su fecha y hora. Una vez la liga inició, no puede ser cancelada y los clubes no pueden unirse ni abandonarla.

Una liga iniciada tiene un fixture - una grilla con las fichas de partido; cada ficha de partido tiene su fecha, rivales, estado (sin iniciar, en juego o finalizado) y resultado. La liga iniciada también tiene una pestaña de partidos en vivo, que muestra los partidos que se están jugando, y un ranking: los clubes participantes ordenados por puntaje y diferencia de goles. Para el puntaje de un participante, los partidos ganados suman 3, los empatados suman 1 y los perdidos suman 0. La liga finaliza al haberse jugado todos los partidos - su estado pasa a finalizada.

El creador, los participantes y los usuarios ajenos a la liga podrán ver el fixture, el ranking y los partidos; pero, si la liga es privada, los usuarios ajenos deberán ingresar la contraseña de la liga para acceder a cualquiera de ellos.

### Partidos

Los partidos se juegan entre dos equipos de seis jugadores. Pueden ser amistosos o partidos de liga, y se componen de cuatro tiempos de igual duración, separados por 3 pausas (dos de hidratación y un entretiempo). Durante todo el partido, el usuario jugador puede ver y reasignar el comportamiento de cualquiera de sus titulares y pedir un cambio de jugador. Los cambios de jugador pedidos se efectúan en una pausa. Hay solo una ventana por pausa y solo se permite un cambio de jugador por ventana, por lo que en total se pueden hacer hasta tres cambios.

Al principio de cada tiempo, aparecen los jugadores en sus posiciones iniciales en la cancha. El tiempo se desarrolla por ticks: en cada tick, se calcula lo que hará el jugador en base a su comportamiento. El partido se detiene únicamente en caso de que termine el tiempo o en caso de un gol. Si ocurre un gol, los jugadores y la pelota vuelven a sus posiciones iniciales y el partido se reanuda. No hay laterales, corners, faltas, penales ni tiros libres - si la pelota toca el borde de la cancha, ésta rebotará.

Los partidos, una vez iniciados, se jugarán y terminarán independientemente de que el usuario esté conectado - los jugadores se van a manejar con sus comportamientos asignados durante todo el partido. Los partidos de liga, en particular, inician automáticamente en su fecha y hora establecidos.

Tanto los espectadores como los usuarios jugadores podrán ver:

- La cancha con las líneas de campo, los arcos, los jugadores en cancha y la pelota.
- El marcador que muestra el nombre y avatar de los clubes con sus goles y el tiempo transcurrido.
- Los nombres y PACSS de todos los jugadores de ambos equipos.

### Búsqueda de Partidos Amistosos

Para jugar un partido amistoso, se usará un sistema de matchmaking aleatorio: un usuario busca un partido y espera a que otro usuario esté buscando un partido amistoso. Una vez hayan dos en espera, se los empareja y se los envía a un menú de selección de equipo. Una vez ambos hayan seleccionado sus equipos, el partido amistoso inicia.

### Ranking Global

Cualquier usuario podrá ver un ranking global de clubes, en donde se ordenan a todos los clubes por puntaje, diferencia de goles y partidos jugados, de todas las ligas públicas. En este ranking no entran clubes que no hayan jugado ningún partido de liga.