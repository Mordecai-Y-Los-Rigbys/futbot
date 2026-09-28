Información:  
  - Titulo: FutBot  
  - Descripción: 
  ## Laboratorio 2026 \- Ingeniería del Software. API para gestionar usuarios, jugadores, ligas, comportamientos y partidos.  
  - versión: 1.2.0

Servidores:  
  - url: (aún no definida)  
  - descripción: Servidor local

## USUARIO  
Direcciones:
### `/usuarios`
  - **POST:**  
    - Resumen: Registrar usuario (Caso de Uso 1\)  
    - Cuerpo\_de\_request:  
	    - Obligatorio: sí  
      - Contenido: dict(nombre\_usuario: String, contraseña: String, email: String, nombre\_club: String, avatar: String)  
    - Respuesta:  
      - '201' Creado:  
        - Descripción: Usuario y club creados con éxito.  
        - Establecer-Cookie: Sesión iniciada.
      - '400' Petición errónea:
        - Descripción: Formulario incompleto (CU1 \- 4b) o formato de mail incorrecto (CU1 \- 4c).
      - '409' Conflicto:
        - Descripción: El mail ya está registrado (CU1 \- 4a).

### `/auth/inciar-sesion`

  - **POST:**  
    - Resumen: Iniciar sesión (Caso de Uso 2\)  
    - Cuerpo\_de\_request:  
     	- Obligatorio: sí  
     	- Contenido: dict(email: String, contraseña: String)
    - Respuesta:  
      - '200' OK:
        - Descripción: Sesión iniciada con éxito, redirige al menú principal.
        - Contenido:  
          - Establecer-Cookie: Sesión iniciada con el ID del usuario.
      - '400' Petición errónea:
        - Descripción: Formulario incompleto (CU2 \- 4b) o formato de mail incorrecto (CU2 \- 4c).
      - '401' No autorizado:  
        - Descripción: No existe usuario que coincida con esas credenciales (CU2 \- 4a).

### `/auth/salir`  
  - **POST:**  
    - Resumen: Cerrar sesión (Caso de Uso 3\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: no	  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Sesión cerrada, redirige al sistema de autenticación.
        - Contenido:  
          - Establecer-Cookie: Cookie expirada.  
      - '401' No autorizado:  
        - Descripción: No había sesión vigente.

  
## JUGADORES  

Direcciones:

### `/jugadores`  
  - **GET:**  
    - Resumen: Obtener jugadores del usuario autenticado, opcionalmente filtrados por nombre (Casos de Uso 10 y 12\)  
    - Parámetros:  
    - Nombre: nombre  
     Origen: Query  
    - Obligatorio: no
    - Descripción: Si se provee, filtra jugadores cuyo nombre contenga este texto. Devuelve hasta 50 resultados.  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Lista de hasta 50 jugadores del usuario (todos si no se envía "nombre", o los que matchean si se envía). 
        Cada jugador incluye sus estadísticas y un flag "eliminable" para que el frontend sepa si mostrar el botón de Eliminar (CU10, CU12). Si la lista da vacía, se muestra el mensaje que corresponda según haya o no query de búsqueda (CU12 \- 2a / 2b).  
      - '401' No autorizado:  
        -  Descripción: El usuario no está autenticado.

  - **POST:**  
    - Resumen: Crear jugador (Caso de Uso 11\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido:
        -  dict(nombre: String, poder: Int \[20-100\], agilidad: Int \[20-100\], control: Int \[20-100\],  
        fuerza: Int \[20-100\], velocidad: Int \[20-100\])  
    - Respuesta:	  
      - '201' Creado:  
        - Descripción: Jugador creado correctamente.  
      - '400' Petición errónea:  
        - Descripción: Nombre demasiado largo (CU11 \- 4a), formulario incompleto (CU11 \- 4b), alguna estadística fuera del rango 20-100 (CU11 \- 4c), o la suma de estadísticas supera 300 (CU11 \- 4d).  
      - '401' No autorizado:  
       	- Descripción: El usuario no está autenticado.

### `/jugadores/{jugador_id}`  

  - **DELETE:**  
    - Resumen: Eliminar un jugador (Caso de Uso 13\)  
    - Parámetros:  
      - Nombre: jugador\_id  
       Origen: Path  
    - Respuesta:  
      -  '204' Sin Contenido:  
        - Descripción: Jugador eliminado correctamente.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El jugador no pertenece al usuario autenticado.  
      - '404' No encontrado:  
        - Descripción: El jugador no existe.  
      - '409' Conflicto:  
        - Descripción: El jugador es integrante de un equipo participante de una liga (CU13 \- 2a) o está jugando un partido en este momento (CU13 \- 2b). En ambos casos el sistema no lo elimina y desactiva la opción ‘Eliminar’ para este jugador.

## COMPORTAMIENTOS  

Direcciones:

### `/comportamientos`  
  - **GET:**	  
    - Resumen: Obtener comportamientos del usuario autenticado, opcionalmente filtrados por nombre (Casos de Uso 4 y 6\)  
    - Parámetros:  
      - Nombre: nombre  
        Origen: Query  
      - Obligatorio: no  
      - Descripción: Si se provee, filtra comportamientos cuyo nombre contenga este texto. Devuelve hasta 50 resultados.  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Lista de hasta 50 comportamientos del usuario (todos si no se envía "nombre", o los que encuentra si se envía). Si la lista da vacía, se muestra el mensaje correspondiente según haya o no query de búsqueda (CU6 \- 2a / 2b).	  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.

  - **POST:**  
    - Resumen: Crear un comportamiento (Caso de Uso 5\)  
   	- Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido: dict(nombre: String, codigo: String)  
    - Respuesta:  
      - '201' Creado:  
        - Descripción: Comportamiento creado con éxito.  
      -  '400' Petición errónea:  
        - Descripción: Nombre demasiado largo (CU5 \- 4c) o formulario incompleto (CU5 \- 4d).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '409' Conflicto:  
        - Descripción: Ya existe un comportamiento con ese nombre asociado al usuario (CU5 \- 4b), el código no es válido según las reglas de la API de comportamientos (CU5 \- 4a), o el código es demasiado largo (CU5 \- 4e).

### `/comportamientos/{comportamiento_id}`
  - **GET:**  
    - Resumen: Obtener detalle de un comportamiento propio, nombre y código (Caso de Uso 7\)  
    - Parámetros:  
      - Nombre: comportamiento\_id  
       Origen: Path  
    - Respuesta:  
      - '200' OK:  
        -  Descripción: Nombre y código del comportamiento.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El comportamiento no pertenece al usuario autenticado.  
      - '404' No encontrado:  
        - Descripción: El comportamiento no existe.

  - **PATCH:**  
    - Resumen: Modificar un comportamiento (Caso de Uso 8\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido: dict(nombre: String, codigo: String)  
    - Parámetros:  
      - Nombre: comportamiento\_id  
       Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Comportamiento modificado con éxito.  
      - '400' Petición errónea:  
        - Descripción: Nuevo nombre demasiado largo (CU8 \- 4c).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El comportamiento no pertenece al usuario autenticado.  
      - '404' No encontrado:  
        - Descripción: El comportamiento no existe, o fue eliminado entre que el usuario abrió el formulario y el sistema obtuvo acceso al registro para guardar (CU8 \- 4d).  
      - '409' Conflicto:  
        Descripción: El código no es válido (CU8 \- 4a), ya existe otro comportamiento del usuario con el nuevo nombre (CU8 \- 4b), o el código es demasiado largo (CU8 \- 4e).

  - **DELETE:**  
    - Resumen: Eliminar un comportamiento (Caso de Uso 9\)  
    - Parámetros:  
      - Nombre: comportamiento\_id  
       Origen: Path  
    - Respuesta:  
      - '204' No Contenido:  
        - Descripción: Comportamiento eliminado con éxito.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El comportamiento no pertenece al usuario autenticado.  
      - '404' No encontrado:  
        - Descripción: Comportamiento no encontrado.  
      - '409' Conflicto:  
        - Descripción: El comportamiento está asignado a un jugador titular en un partido en curso.

##  LIGAS  
  
Direcciones:

### `/ligas`  
  - **GET:**  
    - Resumen: Buscar/listar ligas por nombre (Casos de Uso 14 y 16\)  
    - Parámetros:  
      - Nombre: nombre  
       Origen: Query  
      - Obligatorio: no  
      - Descripción: Si se provee, filtra ligas cuyo nombre contenga este texto. Devuelve hasta 50 resultados.  
    - Respuesta:  
      - '200' OK:  
        - Descripción:   Lista de hasta 50 ligas con su información resumida (nombre, creador, estado, cantidad de participantes, máximo de clubes, privacidad), accesible sin necesitar contraseña incluso si son privadas, ya que esta info no se considera sensible según el alcance. Si la lista da vacía, el frontend es responsable de mostrar el mensaje correspondiente según haya o no query de búsqueda (CU16 \- 2a / 2c).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.

  - **POST:**  
    - Resumen: Crear una liga (Caso de Uso 15)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido: dict(nombre: String, min\_participantes: Int, max\_participantes: Int, duracion\_partido: Int, privado: Bool, contraseña: String | Null)  
    - Respuesta:  
      - '201' Creado:  
        - Descripción: Liga creada con éxito, en estado "preparación".   
      - '400' Petición errónea:  
        - Descripción: Formulario incompleto (CU15 \- 4a), mínimo de clubes menor a 3 (CU15 \- 4b), máximo menor al mínimo (CU15 \- 4c), o nombre demasiado largo (CU15 \- 4d).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.

### `/ligas/{liga_id}`  
  - **GET:**  
    - Resumen: Muestra la información resumida de una liga puntual.  
    - Parámetros:  
      - Nombre: liga\_id  
        Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Información resumida de la liga (nombre, creador, estado, participantes, máximo, privacidad).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.

### `/ligas/{liga_id}/unirse`  
  - **POST:**  
    - Resumen: Unirse a una liga, pública o privada (Casos de Uso 17 y 18\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido: dict(contraseña: String | Null, integrantes: List\[dict(jugador\_id: Int, titularidad: Enum\[suplente,  delantero, mediocampo, defensa\], comportamiento\_id: Int)\])  
      - Descripción: "contraseña" solo es necesario si la liga es privada (CU18); se ignora si es pública o si el usuario es participante (CU17).  
      "integrantes" debe tener exactamente 6 elementos con jugador\_id distintos, uno por cada valor de "titularidad" (titular\_1, titular\_2, titular\_3 y suplente exactamente una vez cada uno... salvo "suplente", que se repite en los 3 restantes). No se envía una posición en cancha (coordenadas): la posición inicial de cada titular la calcula el sistema a partir de si es titular\_1, titular\_2 o titular\_3, según el Diccionario de Datos del DFD (Posición \= Posición X \+ Posición Y es un dato de Integrante, no algo que el usuario declare al formar el equipo).  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Equipo registrado, el club queda como participante de la liga.  
      - '400' Petición errónea:  
        - Descripción: El equipo formado no está completo o es inválido (CU17 \- 4a, CU18 \- 6a).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción:  La contraseña ingresada no coincide con la de la liga (CU17 \- 4b). Se devuelve 403 y no 400 porque el formulario en sí es válido, lo que falla es la autorización de acceso a la liga privada.  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: La liga está llena (CU17 \- 2a / CU18 \- 2a), el usuario no tiene 6 jugadores propios (CU17 \- 2b / CU18 \- 2b), alguno de los jugador\_id enviados no pertenece al usuario o la liga se llenó entre que el usuario empezó el flujo y el sistema obtuvo acceso al registro de participantes para confirmarlo (CU17 \- 4b / CU18 \- 6b, condición de carrera).

  - **DELETE:**  
    - Resumen: Abandonar una liga (Caso de Uso 27\)  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: El club deja de ser participante de la liga.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: el usuario no es participante de esa liga (CU27 \- 2b) o la liga ya está iniciada, por lo que no se puede abandonar (CU27 \- 2a).

### `/ligas/{liga_id}/iniciar`  
  - **POST:**  
    - Resumen: Iniciar una liga (Caso de Uso 19\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: no  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Liga iniciada, se genera y persiste el fixture con fecha y hora de los partidos. La liga pasa de estado "preparación" a "iniciada".  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El usuario no es el creador/administrador de la liga (CU19 \- 2a).  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: No se llegó al mínimo de participantes necesarios, o la liga ya estaba iniciada o cancelada.

### `/ligas/{liga_id}/cancelar`  
  - **POST:**  
    -  Resumen: Cancelar una liga (Caso de Uso 28\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: no  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Liga marcada como cancelada de forma permanente. No se elimina el registro (a diferencia de un DELETE), queda visible en estado "cancelada" y no admite más inicios ni nuevos participantes.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El usuario no es el creador/administrador de la liga (CU28 \- 2b).  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: La liga ya está iniciada, por lo que no puede cancelarse (CU28 \- 2a).

### `/ligas/{liga\_id}/fixture`  
  - **GET:**  
    - Resumen: Ver el fixture de una liga (Casos de Uso 23 y 24\)  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
      - Nombre: contraseña  
       Origen: Query  
      - Obligatorio: no  
        - Descripción: Solo necesaria si la liga es privada y el usuario no es participante (CU24). Se ignora si la liga es pública o si el usuario ya tiene acceso directo por su rol.  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Grilla de partidos con fecha, rivales, estado y resultado. Accesible directamente para el creador y los participantes, y para cualquier usuario si la liga es pública. Si es privada y el usuario es ajeno, requiere pasar "contraseña" y que coincida con la contraseña real de la liga (CU24).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: La liga es privada, el usuario no es creador ni participante, y "contraseña" no vino o no coincide con la contraseña de la liga (CU24 \- 4a).  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: La liga todavía no está iniciada, no existe fixture aún (CU23 \- 2a, CU24 \- 4a).

### `/ligas/{liga_id}/ranking`
  - **GET:**  
    - Resumen: Ver el ranking de participantes de una liga (Casos de Uso 25 y 26\)  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
      - Nombre: contraseña  
       Origen: Query  
      - Obligatorio: no  
      - Descripción: Solo necesaria si la liga es privada y el usuario no es participante (CU26). Se ignora si la liga es pública o si el usuario ya tiene acceso directo por su rol.  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Participantes de la liga, considerando únicamente sus partidos de liga ya finalizados, ordenados de mayor a menor por puntaje (victoria=3, empate=1, derrota=0) y diferencia de goles. Mismas reglas de acceso que /fixture: directo para creador/participantes o liga pública; si es privada y el usuario es ajeno, requiere "contraseña" coincidente (CU26).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: Liga privada, usuario ajeno, y "contraseña" no vino o no coincide con la contraseña de la liga (CU26 \- 4b).  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: La liga todavía no está iniciada, no hay ranking que mostrar (CU25 \- 2a, CU26 \- 4b).

### `/ligas/{liga\_id}/partidos`  
  - **GET:**  
    - Resumen: Listar los partidos en vivo de una liga (Casos de Uso 20, 21 y 22). De la lista devuelta, el sistema distingue con el campo "jugable" si al usuario le corresponde el botón "Jugar Partido" o "Ver Partido". Corresponde directamente a "Datos para ver Partido de Liga" del Diccionario de Datos del DFD.  
    - Parámetros:  
      - Nombre: liga\_id  
       Origen: Path  
      - Nombre: contraseña  
        Origen: Query  
      - Obligatorio: No  
      - Descripción: Solo necesaria si la liga es privada y el usuario no es creador ni participante (CU23). Se ignora si la liga es pública o si el usuario ya tiene acceso directo por su rol.  
    - Respuesta:  
      - '200' OK:  
        -  Descripción: Lista de partidos en vivo de la liga, cada uno con un flag "jugable" (true si el usuario es participante de alguno de los dos clubes de ese partido y todavía no fue jugado por él en calidad de jugador). Mismas reglas de acceso que /fixture y /ranking. Si no hay partidos en vivo, la lista da vacía y es responsabilidad del sistema avisarlo (CU20 \- 2b, CU21 \- 2b, CU22 \- 4b).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: Liga privada, usuario ajeno, y "contraseña" no vino o no coincide con la contraseña de la liga (CU22 \- 4a).  
      - '404' No encontrado:  
        - Descripción: Liga no encontrada.  
      - '409' Conflicto:  
        - Descripción: El partido terminó, el botón correspondiente no debería estar disponible (CU20 \- 4a, CU21 \- 4a, CU22 \- 6a).

  
## RANKING GLOBAL  
  
Direcciones:

### `/ranking`  
  -  **GET:**  
    - Resumen: Muestra el ranking global de clubes (Caso de Uso 30\)  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Todos los clubes que tienen al menos un partido de liga finalizado, ordenados por puntaje, diferencia de goles y partidos jugados. Los clubes sin partidos finalizados quedan excluidos.  
      - '204' No Contenido:  
        - Descripción: Ningún club tiene un partido de liga finalizado todavía, no hay datos para el ranking (CU30 \- 2a).  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.


## PARTIDOS \- EMPAREJAMIENTO  
  
Direcciones:

###  `/emparejamiento`  
  - **POST:**  
    - Resumen: Buscar un partido amistoso (Caso de Uso 29\)  
    -  Cuerpo\_de\_request:  
      - Obligatorio: si  
	    - Contenido: dict(integrantes: List\[dict(jugador\_id: Int, titularidad: Enum\[suplente, delantero, mediocampo, defensa\], comportamiento\_id: Int)\])  
    - Respuesta:  
      - '202' Aceptado:  
        - Descripción: El usuario entra a la cola de emparejamiento con su equipo conformado. La confirmación de partido encontrado y el partido\_id resultante no se devuelven en esta respuesta (no hay polling): se notifican vía el WebSocket general del usuario, ver /ws/usuario más abajo.  
      - '400' Petición errónea:  
        - Descripción: El usuario no tiene 6 jugadores propios, no cumple la precondición del CU29.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '409' Conflicto:  
        - Descripción: El usuario ya se encuentra en la cola de emparejamiento.

  - **DELETE:**  
    - Resumen: Cancelar la búsqueda de partido amistoso antes de ser emparejado (CU 36).  
    - Respuesta:  
      - '200' OK:  
        - Descripción: El usuario sale de la cola de emparejamiento.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '409' Conflicto:  
        - Descripción: El usuario no se encontraba en la cola (ya fue emparejado o nunca la inició).

### `/partidos/{partido_id}/comportamiento`  
  - **GET:**  
    - Resumen: Ver el comportamiento actual de un jugador titular propio durante un partido (Caso de Uso 32\)  
    - Parámetros:  
      - Nombre: partido\_id  
        Origen: Path  
      - Nombre: jugador\_id  
        Origen: Query  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Nombre y código del comportamiento asignado actualmente al jugador.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El usuario no es jugador de este partido, o el jugador\_id no es un titular de su equipo (CU32 \- 2a).  
      - '404' No encontrado:  
        - Descripción: Partido o jugador no encontrado.

  - **PATCH:**  
    - Resumen: Reasignar el comportamiento de un jugador titular propio durante un partido (Caso de Uso 33\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido: dict(jugador\_id: Int, comportamiento\_id: Int)  
    - Parámetros:  
      - Nombre: partido\_id  
        Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Comportamiento reasignado. A partir del siguiente tick, el sistema usa el nuevo comportamiento para determinar la lógica del jugador (CU33, último paso).  
      - '400' Petición errónea:  
        - Descripción: Surgió error con el sistema.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El usuario no es jugador de este partido, o el jugador\_id no es un titular de su equipo (CU33 \- 2a).  
      - '404' No encontrado:  
        - Descripción: Partido o jugador no encontrado.

### `/partidos/{partido_id}/sustituir`  
  - **POST:**  
    - Resumen: Pedir un cambio de jugador durante un partido (Caso de Uso 31\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido: dict(titular\_id: Int, suplente\_id: Int)  
    - Parámetros:  
      - Nombre: partido\_id  
        Origen: Path  
    - Respuesta:  
      - '202' Aceptado:  
        - Descripción: Cambio agendado. Se hará efectivo en la próxima pausa.  
      - '400' Petición errónea:  
        - Descripción: titular\_id no es titular actual, o suplente\_id no es suplente actual, del equipo del usuario.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El usuario no es jugador de este partido.  
      - '404' No encontrado:  
        - Descripción: Partido no encontrado.  
      - '409' Conflicto:  
        - Descripción: El usuario ya no tiene cambios disponibles (CU31 \- 6a).

### `/partido/{partido_id}/unirse`  
 - **POST:**  
    - Resumen: Solicita autorización y un token temporal para conectarse al WebSocket del partido en vivo.  
    - Cuerpo\_de\_request:  
      - Obligatorio: no  
      - Contenido: dict(contraseña: String)   
 	    - Descripción: Mismo criterio que en GET /ligas/{liga\_id}/partidos: solo se evalúa si el partido es de una liga privada y el usuario es ajeno (no creador ni participante); se ignora en cualquier otro caso.  
    - Parámetros:  
      - Nombre: partido\_id  
        Origen: Path  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Autorización exitosa. Devuelve el token de un solo uso que el frontend deberá enviar para abrir la conexión WebSocket.  
        - Contenido: dict(token\_ws: String)  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El partido es de una liga privada, el usuario es ajeno, y "password" no vino o no coincide con la contraseña de la liga (CU23 \- 4a); o el partido es amistoso y el usuario no es uno de los dos jugadores (el alcance prohíbe que un usuario ajeno vea un amistoso que no es suyo).  
      - '404' No encontrado:  
        - Descripción: Partido no encontrado.

## **PARTIDOS \- TIEMPO REAL (WebSocket)**  

### `ws://partidos/{partido\_id}/live`
  - **WS:**   
    - Resumen: Conexión en tiempo real a un partido (amistoso o de liga), en calidad de jugador o espectador según corresponda (Casos de Uso 20, 21, 22 y 34 para la conexión en sí).  
    - Parámetros:  
      - Nombre: partido\_id  
       Origen: Path  
      - Nombre: token  
       Origen: Query  
       Obligatorio: si  
       Descripción: Token temporal de un solo uso obtenido previamente en POST /partidos/{partido\_id}/unirse.   

    - "Respuesta": 
    > Al conectar, rechaza la conexión con:  
    
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '403' Prohibido:  
        - Descripción: El usuario no tiene permisos para acceder a este partido.  
      - '404' No encontrado:  
        - Descripción: Partido no encontrado, o ya finalizado.  
  
    - **Mensajes emitidos por el servidor (Server → Cliente), una vez conectado:**  
      - tick: posiciones de jugadores y pelota, actualizadas en cada tick del juego.  
      - marcador: goles de cada club y tiempo transcurrido, se emite en cada cambio.  
      - gol: evento puntual con el club que convirtió y reseteo de posiciones (según el alcance).  
      - inicio\_tiempo: se emite al empezar cada uno de los 4 tiempos, incluye la cuenta regresiva de 3 segundos.  
      - pausa: se emite al llegar a una de las 3 pausas (hidratación x2, entretiempo), habilita la ventana para efectuar UN cambio de jugador por pausa.  
      - fin\_partido: resultado final, cierra la conexión del lado del servidor.  
  
    - **Mensajes que el cliente puede enviar (Cliente → Servidor), solo si el usuario está en calidad de jugar el partido:**  
      - No se envían acciones de juego por este canal: pedir cambio, reasignar comportamiento e intercambiar titularidad se hacen por los endpoints REST puntuales de arriba, para mantener la separación entre "stream de datos" y "comandos". El servidor sí empuja por acá el resultado de esas acciones cuando corresponda (por ejemplo, un cambio de jugador efectivizado en la siguiente pausa se ve reflejado en el próximo mensaje de tick).
