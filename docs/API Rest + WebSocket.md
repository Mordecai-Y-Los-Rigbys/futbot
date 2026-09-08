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
    - Resumen: Obtener jugadores del usuario autenticado, opcionalmente filtrados por nombre (Casos de Uso 11 y 13\)  
    - Parámetros:  
    - Nombre: nombre  
     Origen: Query  
    - Obligatorio: no
    - Descripción: Si se provee, filtra jugadores cuyo nombre contenga este texto. Devuelve hasta 50 resultados.  
    - Respuesta:  
      - '200' OK:  
        - Descripción: Lista de hasta 50 jugadores del usuario (todos si no se envía "nombre", o los que matchean si se envía). 
        Cada jugador incluye sus estadísticas y un flag "eliminable" para que el frontend sepa si mostrar el botón de Eliminar (CU11, CU13). Si la lista da vacía, se muestra el mensaje que corresponda según haya o no query de búsqueda (CU13 \- 2a / 2b).  
      - '401' No autorizado:  
        -  Descripción: El usuario no está autenticado.

  - **POST:**  
    - Resumen: Crear jugador (Caso de Uso 12\)  
    - Cuerpo\_de\_request:  
      - Obligatorio: sí  
      - Contenido:
        -  dict(nombre: String, poder: Int \[20-100\], agilidad: Int \[20-100\], control: Int \[20-100\],  
        fuerza: Int \[20-100\], velocidad: Int \[20-100\])  
    - Respuesta:	  
      - '201' Creado:  
        - Descripción: Jugador creado correctamente.  
      - '400' Petición errónea:  
        - Descripción: Nombre demasiado largo (CU12 \- 4a), formulario incompleto (CU12 \- 4b), alguna estadística fuera del rango 20-100 (CU12 \- 4c), o la suma de estadísticas supera 300 (CU12 \- 4d).  
      - '401' No autorizado:  
       	- Descripción: El usuario no está autenticado.

### `/jugadores/{jugador_id}`  

  - **DELETE:**  
    - Resumen: Eliminar un jugador (Caso de Uso 14\)  
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
        - Descripción: El jugador es integrante de un equipo participante de una liga (CU14 \- 4a) o está jugando un partido en este momento (CU14 \- 4b). En ambos casos el sistema no lo elimina y desactiva la opción ‘Eliminar’ para este jugador.

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
    - Resumen: Eliminar un comportamiento (Caso de Uso 10\)  
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

