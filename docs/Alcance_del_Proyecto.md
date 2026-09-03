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

## Requisitos funcionales

### RF-01: Registro de usuario

- **Descripción de Entradas:** el sistema requerirá un nombre de usuario, contraseña, correo electrónico, nombre de club y avatar.

- **Fuente y rango válido:** datos ingresados por el actor externo y validados estrictamente en el backend (API).
  - **Nombre de usuario:** alfanumérico, entre 4 y 15 caracteres.
  - **Nombre de club:** alfanumérico (permite espacios), entre 4 y 20 caracteres.
  - **Correo electrónico:** debe contener el símbolo `@` y un dominio válido. Debe ser único.
  - **Contraseña:** longitud mínima de 8 caracteres.
  - **Avatar:** debe ser un ID (número entero) que corresponda a un preset existente en el servidor.
  - **Restricción general:** ningún campo puede estar vacío o ser nulo.

- **Salidas esperadas:** el sistema generará el nuevo registro, emitirá un mensaje de confirmación y devolverá un token de autenticación para ingresar al usuario a la aplicación web ya autenticado.

- **Operaciones lógicas:** el sistema validará la completitud, formatos, longitudes y la unicidad de los campos consultando la base de datos. Tras pasar las validaciones, aplicará una función de hash a la contraseña y almacenará persistentemente los datos del nuevo usuario y su club.

- **Comportamiento en situaciones anormales (Errores en formato o longitud):** si la contraseña es corta, el email no tiene un formato válido, el ID del avatar no existe o hay campos en blanco, el sistema abortará la operación y retornará un error indicando exactamente qué campo falló.

- **Comportamiento en situaciones anormales (Datos duplicados):** si el correo electrónico ya existe en la base de datos, el sistema detendrá el registro e informará al usuario qué dato específico está en uso.

- **Comportamiento en situaciones anormales (Error en Backend):** en caso de no poder guardar persistentemente la información por pérdida de conexión a la base de datos o error interno, el sistema abortará el proceso y mostrará el mensaje: "Error interno: Intente nuevamente".


## Restricciones de diseño

- Servidor: El desarrollo de la API y la lógica del servidor se realizará obligatoriamente utilizando el framework FastAPI.
- Persistencia de Datos: El modelado relacional y la interacción con la base de datos se implementará de forma estricta a través del ORM SQLAlchemy.
- Frontend: La interfaz de usuario será una aplicación web construida exclusivamente sobre React.
- Comunicación Cliente-Servidor: No será posible la utilización técnicas de polling para la sincronización de datos.
