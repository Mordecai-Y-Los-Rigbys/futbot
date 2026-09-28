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

## Detalles fuera del alcance del proyecto

- No habrá una UI ni app para celulares, ni para ningún dispositivo que no sea una computadora de escritorio.
- No habrá una UI responsive.
- No van a haber partidos de más de dos usuarios ni de más de 3 jugadores en cancha, ni equipos de más de 6 jugadores.
- No va a haber sistema de amigos, por ende no van a haber partidos amistosos privados ni mensajes. Además, ningún usuario que no sea jugador de un partido amistoso va a poder verlo.
- No va a haber sistema de ELO ni de partidas clasificatorias.
- No va a haber ningún sistema de compraventa de ningún tipo.
- No va a haber cosméticos para los jugadores, diferentes canchas ni pelotas.
- No habrá modo 3D ni primera persona.
- No habrá un sistema de modificación de datos de usuario ni de modificación de datos de liga (más allá de iniciar o cancelar liga).
- No va a haber un chat de liga.
- No va a haber ninguna otra característica que no se haya mencionado explícitamente (o no se pueda inferir de manera obvia) en este documento.

## Requisitos Funcionales

Están cubiertos en detalle en los casos de uso. En esta sección de alcance nombraremos las funciones que el sistema debe proveer al usuario (divididas por sistema), junto con sus casos de uso (CUs) correspondientes en donde se explica al detalle qué se requiere para cada función:

1. **Sistema de Registro y Autenticación de Usuarios:**
   1. Registro de usuarios: CU 1
   2. Inicio de Sesión: CU 2
2. **Sistema Principal:**
   1. Cierre de Sesión: CU 3
   2. Acceso al sistema de Comportamientos: CU 4
   3. Acceso al sistema de Jugadores: CU 10
   4. Acceso al sistema de Ligas: CU 14
   5. Búsqueda de Partido Amistoso: CU 29
   6. Ver Ranking Global: CU 30
3. **Sistema de Comportamientos:**
   1. Creación de Comportamiento: CU 5
   2. Búsqueda de Comportamientos (propios): CU 6
   3. Ver código de un Comportamiento (propio): CU 7
   4. Modificación de Comportamientos (propios): CU 8
   5. Eliminación de Comportamiento (propio): CU 9
   6. Acceso al Sistema Principal: CU 35
4. **Sistema de Jugadores:**
   1. Creación de Jugador: CU 11
   2. Búsqueda de Jugadores (propios): CU 12
   3. Eliminación de Jugador (propio): CU 13
   4. Acceso al Sistema Principal: CU 35
5. **Sistema de Ligas:**
   1. Creación de Liga: CU 15
   2. Búsqueda de Liga: CU 16
   3. Unirse a Ligas: CUs 17 y 18
   4. Iniciación de Liga: CU 19
   5. Entrar a Jugar Partido de Liga: CU 20
   6. Ver Partido de Liga: CUs 21 y 22
   7. Ver Fixture de Liga: CUs 23 y 24
   8. Ver Ranking de Liga: CUs 25 y 26
   9. Abandonar Liga: CU 27
   10. Cancelación de Liga: CU 28
   11. Acceso al Sistema Principal: CU 35
6. **Partido en tiempo real:**
   1. Pedir Cambio de Jugador: CU 31
   2. Ver Comportamiento de Titular: CU 32
   3. Reasignar Comportamiento de Titular: CU 33
   4. Seleccionar Equipo para Partido Amistoso: CU 34

## Restricciones de diseño

* **Servidor:** El desarrollo de la API y la lógica del servidor se implementará utilizando el framework FastAPI.  
* **Persistencia de Datos:** El modelado relacional y la interacción con la base de datos se implementará a través del ORM SQLAlchemy.  
* **Front-end:** la interfaz de usuario será una aplicación web construida utilizando React.  
* **Comunicación Cliente-Servidor**: No será posible la utilización de técnicas de **polling** de ningún tipo para la sincronización de datos.  
* **Entorno de Ejecución:** El back se ejecutará en una computadora servidor, el front se ejecutará en la computadora del usuario. Las modificaciones a registros y los partidos en tiempo real se ejecutarán en el servidor.  
* **Compatibilidad con otros sistemas:** el back debe ser compatible con linux; el front debe ser compatible con los principales buscadores para computadoras de escritorio: Google Chrome, Firefox y Safari.  
* **Limitaciones de Hardware:** ninguna ha sido requerida; el front requerirá al menos 4GB de RAM para un funcionamiento fluido.  
* **Concurrencia:** se debe poder acceder al sistema desde múltiples buscadores al mismo tiempo (en particular, un usuario debe poder acceder a su cuenta desde múltiples dispositivos), por lo que se debe tener en cuenta cualquier condición de carrera en el acceso a datos.  
* **Confiabilidad y tolerancia a fallos:**   
  * Se debe usar un motor de base de datos **ACID** tal que, si el sistema se cae en el medio de un registro de información, el motor se encargue de la recuperación.  
  * Si el sistema se cae en el medio de un partido, se recuperará utilizando checkpoints. Se debe guardar un checkpoint:  
    * En cada pausa.  
    * En cada reasignación de comportamiento (con un límite de un checkpoint cada 5 segundos).  
    * En cada gol.  
* **Seguridad:**   
  * **Control de acceso:** el usuario solo puede acceder sin autenticarse al sistema de registro y autenticación de usuarios, pudiendo únicamente registrarse e iniciar sesión. Cualquier otra acción requiere que se autentique previamente. 

    La autenticación se realiza al registrarse o al iniciar sesión (en cualquiera de los dos casos, ingresando una contraseña). La autenticación se maneja como una cookie de sesión.

    Las acciones que los usuarios pueden realizar que no conllevan niveles de acceso (más allá de la autenticación) son:

    * gestionar jugadores y comportamientos propios.  
    * buscar partidos amistosos.  
    * ver el ranking global.  
    * buscar y ver información resumida de ligas (nombre, creador, estado, cantidad de participantes, máximo de clubes, privacidad).

    Para las ligas, hay tres niveles de acceso:

    * Creador: puede iniciar o cancelarla. Puede unirse como participante, ver partidos, fixture y ranking sin contraseña, independientemente de la privacidad de la liga.  
    * Participante: no puede iniciar o cancelarla. Puede abandonarla, dejando de ser participante. Puede ver partidos, fixture y ranking sin contraseña, independientemente de la privacidad de la liga.   
    * Ajeno: no puede iniciar ni cancelar una liga.  
      * Si la liga es pública, puede unirse, ver partidos, fixture y/o ranking sin contraseña.  
      * Si la liga es privada, puede unirse, ver partidos, fixture y/o ranking ingresando la contraseña de la liga. Si no la ingresa correctamente, no puede realizar ninguna de las acciones anteriores.

    En un partido, un usuario tiene dos niveles de acceso:

    * Espectador: puede ver:  
      * La cancha con las líneas de campo, los arcos, los jugadores en cancha y la pelota.  
      * El marcador en la esquina superior izquierda.  
      * Los nombres y PACSS de todos los jugadores de ambos equipos.  
    * Jugador: puede ver lo mismo que el espectador y también puede:  
      * Ver y reasignar comportamientos sobre sus jugadores titulares.  
      * Pedir un cambio de jugador.

    Un usuario nunca puede:

    * Gestionar jugadores y comportamientos de otros usuarios.  
    * Unir o echar clubes participantes de ligas (en particular, el creador tampoco puede unir o echar participantes).  
    * De un equipo que no es suyo, durante un partido:  
      * Ver y reasignar comportamientos sobre jugadores titulares.  
      * Pedir un cambio de jugador.  
    * Ver el mail y contraseña de usuarios (en particular, tampoco puede ver su mail ni contraseña).  
    * Ver la contraseña de ligas (en particular, el creador de una liga tampoco puede ver su contraseña).  
  * **Control contra IDOR (Insecure Direct Object Reference):** Cada solicitud que acceda a recursos internos se validará en el backend, comprobando el rol del usuario y la pertenencia del recurso, sin confiar nunca en el identificador enviado por el usuario. Estas solicitudes maliciosas no son contempladas como casos de uso, pero sí están contempladas en el contrato de la API.  
  * **Manejo de contraseñas:** se usará una librería de manejo de contraseñas (con métodos de encriptación y comparación) – estas nunca se guardarán como texto plano en el sistema, siempre se guardarán encriptadas, y se hará la comprobación de contraseñas usando una función de comparación provista por la librería – el sistema no trabajará con ellas sin usar la librería.  
  * **Prevención de Inyección (SQLi):** Toda interacción con la base de datos se realiza exclusivamente a través del ORM SQLAlchemy, que genera consultas parametrizadas (prepared statements) en lugar de concatenar strings directamente en el texto de la query. Esto garantiza que cualquier dato ingresado por el usuario (por ejemplo, el email al iniciar sesión o el nombre de un jugador) se trate siempre como un valor literal y nunca como parte ejecutable del SQL. No se permite el uso de SQL crudo (raw SQL) ni de la función `text()` de SQLAlchemy con interpolación manual de strings; si en algún caso puntual fuera necesario, deberá hacerse exclusivamente mediante bind parameters (`:parametro`) provistos por el propio framework.

## **Comportamiento del sistema** 

* **Rendimiento y tiempos de respuesta:** El servidor procesa los partidos en tiempo real a razón de 20 ticks por segundo. El cálculo de cada tick y su emisión a los clientes conectados vía WebSocket no debe superar una cantidad de 100 ms bajo condiciones normales de carga; se toleran hasta 200 ms de respuesta bajo carga pico.  
* **Aislamiento de comportamientos de usuario:** El código enviado por un usuario como comportamiento pasa por dos capas de control antes y durante su ejecución. La primera es un parseo estricto al momento de crear o modificar el comportamiento, que rechaza cualquier código que no cumpla con los requisitos de validez (ver API de comportamientos); la segunda capa es un límite de tiempo y recursos por tick durante la ejecución en partido: si la evaluación del comportamiento de un integrante excede el tiempo asignado dentro del tick, el sistema la interrumpe y continúa con el cálculo del resto de los jugadores, evitando que un comportamiento muy pesado afecte el rendimiento.  
* **Seguridad:** para que el usuario pueda interactuar con cualquier funcionalidad del sistema, debe estar previamente autenticado, ya sea habiéndose registrado por primera vez o iniciando sesión. Además, varias funciones del sistema conllevan niveles de acceso; ver el apartado de seguridad en restricciones de diseño.

