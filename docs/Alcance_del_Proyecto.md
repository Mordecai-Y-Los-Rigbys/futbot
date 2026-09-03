# FUTBOT: Alcance del proyecto

## ¿Qué es Futbot?

Futbot es un juego y simulador de partidos de fútbol web de dos dimensiones, donde dos Usuarios o más podrán competir en ligas mediante partidos de 3 contra 3.

Lo que hace particularmente especial a este sistema es que al momento de controlar a los jugadores en cancha solamente se podrán utilizar set de código que los usuarios deberán diseñar con antelación.

## PARTES PRINCIPALES DEL SISTEMA

### Usuarios y Clubes

- Todos los jugadores registrados tendrán su propio Club con nombre y avatar.
- El Usuario podrá administrar jugadores, diseñar comportamientos y jugar contra otros clubes.

### Futbolistas y Atributos

Cada Usuario deberá crear sus propios jugadores. Cada futbolista será definido con 5 atributos que una vez guardados, no podrán ser modificados.

- **Power**: Fuerza con la que patea el jugador.
- **Agility**: Cooldown en la que patea el jugador.
- **Control**: Distancia desde la que puede tocar la pelota.
- **Strength**: Cuanto se impone en el choque contra otros jugadores.
- **Speed**: Velocidad a la cual el jugador se moverá.

Como regla obligatoria cada atributo debe estar en un valor entre 20 y 100 puntos de tal manera que la suma de los 5 sea exactamente igual a 300.

### Comportamientos

Cada Usuario deberá crear sus propios comportamientos. Cada comportamiento será definido con un nombre y código atributos que están abiertos a modificaciones.

- Nombre para identificar cada comportamiento (no repetible).
- Código deberá definir las acciones a hacer por el jugador descrito en python.

### Ligas

Cada Usuario podrá crear, administrar y participar en Ligas. Una liga es una competencia entre distintos clubes de distintos usuarios que se enfrentarán en un sistema de todos contra todos.

- Cada liga deberá contar con nombre, minimo de ligas, maximo de ligas y privacidad.
- Para que una liga pueda comenzar deberá tener un mínimo de 3 equipos participantes.
- Una vez iniciada la liga no podrá ser detenida ni reiniciada.

### Partidos

Los partidos serán públicos o privados y se efectuarán entre 2 usuarios quienes participaran con 6 jugadores c/u con la siguiente dinámica:

1. Se jugaran 4 tiempos de igual duración, separados por 3 pausas (dos pausas de hidratación y un entretiempo)
2. Antes del primer tiempo se dará un tiempo de gracia para que los usuarios modifiquen sus estrategias (cambios en el equipo).
3. Cada usuario podrá hacer un cambio en cada pausa, los cuales no son acumulables pero permiten sacar y meter al mismo jugador.
4. La pelota no será frenada en ningún momento aparte de las pausas, es decir no hay laterales, corners, penales ni tiros libres.
5. Pueden haber partidos en ligas asi como partidos amistosos
6. Será transmitido en directo para la vista de los Usuarios en juego, como para aquellos que sean parte de la Liga.
7. La victoria (en Ligas) otorga 3 puntos, empate 1 punto y la derrota no reparte puntos.

## ¿Qué cosas están fuera del alcance del proyecto?

- No va a ser compatible con environments mas allá de pc.
- No va a tener partidos de mas ni menos jugadores que 3.
- No va a haber sistema de amigos, por ende no van a haber partidos amistosos privados.
- No va a haber sistema de compra de jugadores.
- No va a haber cosméticos para los jugadores ni estadios/canchas.
- No va haber modo 3D ni primera persona


## Restricciones de diseño

- Servidor: El desarrollo de la API y la lógica del servidor se realizará obligatoriamente utilizando el framework FastAPI.
- Persistencia de Datos: El modelado relacional y la interacción con la base de datos se implementará de forma estricta a través del ORM SQLAlchemy.
- Frontend: La interfaz de usuario será una aplicación web construida exclusivamente sobre React.
- Comunicación Cliente-Servidor: No será posible la utilización técnicas de polling para la sincronización de datos.
