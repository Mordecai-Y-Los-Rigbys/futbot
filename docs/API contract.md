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

