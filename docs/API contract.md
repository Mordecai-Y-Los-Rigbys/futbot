info:  
  title: FutBot  
  description: \>  
    Laboratorio 2026 \- Ingeniería del Software. API para gestionar usuarios jugadores, ligas y comportamientos.  
  version: 1.0.0

servers:  
  \- url: (aun no definida)  
    description: Servidor local

***USUARIO***  
**—----------------------------------------------------------------------**  
paths:  
/users   
   post: registrar usuario  
responses:  
‘201’ creado con éxito  
‘409’	email repetido  
‘400’ Bad request formulario incompleto → el sistema deberá validar

/auth/login  
	post: Ingresar al sistema  
	   responses:   
		‘201’ ingresó con éxito  
		‘400’ Bad request formulario incompleto  
		‘422’ formulario incompleto

		

**—----------------------------------------------------------------------**

***JUGADORES***  
**—----------------------------------------------------------------------**

  /**users/{id}/players**:  
	**get:**  
	summary: Obtener jugadores del usuario autentificado.  
	operation\_id: get\_players  
response:  
   ‘200’:  
   description: players list.  
   ‘401’:  
   description: user isn’t authenticated  
**/**

  /**user/{id}/players**:  
    **post**:  
      summary: Crear un jugador con PACSS  
	operation\_id: create\_players  
	RequestBody:  
		required: True  
	Parameters:  
		Name: String  
		Power: Int (min:20, max:100)    |  
Agility: Int (min:20, max:100)  |  
Control: Int (min:20, max:100)  | Pacss \= 300  
Strength Int (min:20, max:100)  |  
		Speed: Int (min:20, max:100)    |  
	Response:  
		‘201’:  
		description: Jugador creado correctamente.  
		content:  
			PlayerID: INT  
			Name: String  
			Power: Int (min:20, max:100)    |  
Agility: Int (min:20, max:100)  |  
Control: Int (min:20, max:100)  | Pacss \= 300  
Strength Int (min:20, max:100)  |  
			Speed: Int (min:20, max:100)    |  
		‘400’:  
		description: Datos de jugador invalidos.  
**/**

**/users/{id}/players/{id}:**  
	**delete:**  
	summary: Eliminar un jugador.  
	operation\_id: delete\_players  
	RequestBody:  
		required: True  
	Parameters:  
		name: PlayerID  
		in: Path  
	Responses:  
		‘204’:  
			description: Jugador eliminado.  
		‘401’:  
			description: Usuario no autentificado.  
		‘404’:  
			description: Jugador no encontrado.  
		‘409’:  
			description: El jugador participa en una liga iniciada.  
**/**  
	  
**—----------------------------------------------------------------------**

***COMPORTAMIENTOS***  
**—----------------------------------------------------------------------**

/**users/{id}/behaviors**:  
	**get:**  
	summary: Obtener comportamientos del usuario autentificado.  
	operation\_id: get\_behaviors  
response:  
  	‘200’:  
description: Lista de comportamientos.  
  	‘401’:  
  	 	description: Usuario no identificado.  
/

/**users/{id}/behaviors**:  
    **post**:  
      summary: Crear un comportamiento.  
	operation\_id: create\_behaviors  
	RequestBody:  
		required: True  
	Parameters:  
		Name: String  
		Code: ??? String? (phyton?)  
	Response:  
		‘201’:  
		description: Comportamiento creado correctamente.  
		content:  
			BehaviorID: INT  
			Name: String  
			Power: Int  
Agility: Int   
Control: Int	  
Strength Int  
			Speed: Int  
		‘400’:  
		description: Datos de jugador invalidos.  
/  
/**users/{id}/behaviors/{id}**:  
    **patch**:  
	summary: Modificar un comportamiento.  
/

/**users/{id}/behaviors/{id}**:  
    **delete**:  
	summary: Eliminar un comportamiento.  
/

**—----------------------------------------------------------------------**

***PARTIDOS***  
**—----------------------------------------------------------------------**  
**—----------------------------------------------------------------------**

**LIGAS**  
**—----------------------------------------------------------------------**  
**/league**  
**get:**  
	summary: Muestra las ligas.  
	operation\_id: view\_leagues  
	response:  
		‘200’:  
		description: ligas.  
		‘401’:  
		description: Usuario no autentificado.  
**/**

**/league**  
**post:**  
	summary: Crear un liga.  
	operation\_id: create\_league  
		‘200’:  
		description: liga creada exitosamente.  
		content:  
			leagueID: INT  
		‘401’:  
		description: Usuario no autentificado.  
	  
**—----------------------------------------------------------------------**

**RANKING**  
**—----------------------------------------------------------------------**  
**/ranking**  
**get:**  
	summary: Muestra el ranking global de usuarios.  
	operation\_id: view\_ranking  
	response:  
   ‘200’:  
   description: ranking globar.  
   ‘401’:  
   description: usuario no autentificado.  
**/**  
**—----------------------------------------------------------------------**

## PARTIDOS \- EMPAREJAMIENTO  
  
Direcciones:

###  `/emparejamiento`  
  - **POST:**  
    - Resumen: Buscar un partido amistoso (Caso de Uso 30\)  
    -  Cuerpo\_de\_request:  
      - Obligatorio: si  
	    - Contenido: dict(integrantes: List\[dict(jugador\_id: Int, titularidad: Enum\[suplente, delantero, mediocampo, defensa\], comportamiento\_id: Int)\])  
    - Respuesta:  
      - '202' Aceptado:  
        - Descripción: El usuario entra a la cola de emparejamiento con su equipo conformado. La confirmación de partido encontrado y el partido\_id resultante no se devuelven en esta respuesta (no hay polling): se notifican vía el WebSocket general del usuario, ver /ws/usuario más abajo.  
      - '400' Petición errónea:  
        - Descripción: El usuario no tiene 6 jugadores propios, no cumple la precondición del CU30.  
      - '401' No autorizado:  
        - Descripción: El usuario no está autenticado.  
      - '409' Conflicto:  
        - Descripción: El usuario ya se encuentra en la cola de emparejamiento.

  - **DELETE:**  
    - Resumen: Cancelar la búsqueda de partido amistoso antes de ser emparejado.  
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
    - Resumen: Conexión en tiempo real a un partido (amistoso o de liga), en calidad de jugador o espectador según corresponda (Casos de Uso 21, 22 y 23 para la conexión en sí).  
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
