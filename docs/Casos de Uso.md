**Caso de Uso 1: Registrar un Usuario.**

* **Actor primario:** Actor Externo.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Registro y Autenticación de Usuarios.  
* **Escenario exitoso principal:**  
1. El actor externo selecciona la opción de registrar un usuario, solicitando la operación al sistema.  
2. El sistema le despliega al actor externo el formulario de registro de usuario.  
3. El actor externo rellena y envía el formulario de registro de usuario.  
4. El sistema valida el formulario, registra al usuario y avisa al actor externo que se registró su usuario exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) El mail ya fue registrado anteriormente.  
  	\* El sistema no registra el usuario y notifica al actor externo que el mail ya está registrado.  
   – 4 b) El formulario está incompleto.  
  	\* El sistema no registra el usuario y solicita al actor externo que reenvíe el formulario completo  
   – 4 c) El nombre de usuario, nombre de club o la contraseña superan los 20 caracteres.  
  	\* El sistema no registra el usuario y solicita al actor externo reenviar el formulario con datos correctos, indicando que revise los campos vacíos.  
   – 4 d) El mail supera los 254 caracteres.  
  	\* El sistema no registra el usuario y solicita al actor externo reenviar el formulario con datos correctos, indicando que revise los campos vacíos.  
  – 4 e) El avatar supera 2mb de tamaño.  
  	\* El sistema no registra el usuario y solicita al actor externo reenviar el formulario con datos correctos, indicando que revise los campos vacíos.

**Caso de Uso 2: Inicio de Sesión.**

* **Actor primario:** Actor Externo.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Registro y Autenticación de Usuarios.  
* **Escenario exitoso principal:**  
1. El actor externo selecciona la opción de inicio de sesión, solicitando la operación al sistema.  
2. El sistema le despliega al actor externo el formulario de inicio de sesión.  
3. El actor externo rellena y envía el formulario al sistema.  
4. El sistema valida los datos de inicio de sesión, autentica al usuario, le avisa al actor externo que se inició sesión exitosamente y lo redirige al menú principal.  
* **Escenarios excepcionales:**  
  – 4 a) El sistema no encuentra un usuario registrado que coincida con los datos del formulario de inicio de sesión.  
  	\* El sistema no autentica al usuario, no lo redirige al menú principal y le notifica que los datos no son correctos.  
   – 4 b) El formulario posee campos inválidos.  
  	 \* El sistema no registra el usuario y solicita al actor externo reenviar el formulario con datos correctos, indicando que revise los campos marcados con error.

**Caso de Uso 3: Cerrar Sesión.**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario está autenticado.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de cerrar sesión, solicitando la operación al sistema.  
2. El sistema cierra la sesión y redirige al actor externo al sistema de registro y autenticación de usuarios.  
* **Escenarios excepcionales:** Ninguno.

**Caso de Uso 4: Acceder al sistema de comportamientos.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de acceder al Sistema de Comportamientos, solicitando al sistema que le permita acceder.  
2. El sistema redirige al usuario al Sistema de comportamientos y le despliega hasta 50 comportamientos registrados asociados a éste.  
*  **Escenarios excepcionales:** Ninguno.

**Caso de Uso 5: Crear Comportamiento.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de crear un comportamiento, solicitando la operación al sistema.  
2. El sistema le despliega al usuario el formulario de creación de comportamientos.  
3. El usuario envía al sistema el formulario rellenado.  
4. El sistema lo valida, lo registra y notifica al usuario de que la operación se hizo exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) El código no es válido.  
  	\* El sistema no registra el comportamiento y le notifica al usuario que el código ingresado no cumple con las reglas de validez del sistema.  
  – 4 b) El nombre de comportamiento asociado al usuario ya está registrado.  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que .  
  – 4 c) El nombre no está entre 1 y 20 caracteres.  
  	\* El sistema no registra el comportamiento y le solicita al usuario reenviar el formulario con un nombre válido.

**Caso de Uso 6: Buscar comportamientos**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario rellena y envía al sistema el formulario de búsqueda con un nombre de comportamiento.  
2. El sistema busca hasta 50 comportamientos asociados al usuario cuyo nombre contenga el nombre escrito en la barra de búsqueda, y se los despliega al usuario junto a opciones de comportamiento.  
*  **Escenarios excepcionales:**  
  – 2 a) No hay comportamientos registrados asociados al usuario.  
  	\* El sistema no despliega los comportamientos registrados y le notifica al usuario que no tiene comportamientos.  
  – 2 b) No hay comportamientos registrados asociados al usuario cuyo nombre contenga el nombre ingresado en la barra de búsqueda.  
  	\* El sistema no despliega los comportamientos registrados y le notifica al usuario que no se encontraron comportamientos que coincidan con lo ingresado en la barra de búsqueda.

**Caso de Uso 7: Ver detalle de comportamiento**

* **Actor primario:** Usuario.  
* **Precondición:**  Hay al menos un comportamiento en la lista.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El sistema selecciona un comportamiento de la lista, solicitando ver el código al sistema.  
2. El sistema le despliega una ventana con el nombre del comportamiento y su código asociado.  
*  **Escenarios excepcionales:** Ninguno.

**Caso de Uso 8: Modificar Comportamiento.**

* **Actor primario:** Usuario.  
* **Precondición:** Hay al menos un comportamiento en la lista.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario selecciona un comportamiento de la lista y selecciona modificarlo, solicitando la operación al sistema.  
2. El sistema le despliega al usuario un formulario de modificación.  
3. El usuario rellena y envía el formulario al sistema.  
4. El sistema valida el formulario, accede al registro de comportamientos, guarda la modificación y le notifica al usuario que el comportamiento se actualizó exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) El código no es válido.  
  	\* El sistema no registra el comportamiento y le notifica al usuario que el código ingresado no cumple con las reglas de validez del sistema.  
  – 4 b) El nombre de comportamiento asociado al usuario ya está registrado.  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que el nombre ya está registrado.  
  – 4 c) El nombre no está entre 1 y 20 caracteres.  
  	\* El sistema no registra el comportamiento y le solicita al usuario reenviar el formulario con un nombre válido.  
  – 4 d) El comportamiento fue eliminado antes que el sistema obtuviera acceso al registro.  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que el comportamiento fue eliminado antes de poder modificarlo.

**Caso de Uso 9: Eliminar un Comportamiento.**

* **Actor primario:** Usuario.  
* **Precondición:**  Hay al menos un comportamiento en la lista.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario selecciona un comportamiento, selecciona eliminarlo y confirma la operación, enviando el pedido de eliminación al sistema.  
2. El sistema elimina el comportamiento y le notifica al usuario que la operación se realizó exitosamente.	  
* **Escenarios excepcionales:**	Ninguno.

**Caso de Uso 10: Acceder al sistema de jugadores.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de acceder al sistema de Jugadores, solicitando al sistema principal que le dé acceso.  
2. El sistema redirige al usuario al sistema de jugadores y le despliega hasta 50 jugadores registrados asociados a éste, con cada uno junto a sus estadísticas y una opción de ‘Eliminar’ si el jugador es eliminable.  
*  **Escenarios excepcionales:** Ninguno

**Caso de Uso 11: Crear un jugador.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Jugadores.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de creación de jugador, solicitando la operación al sistema.  
2. El sistema le despliega el formulario de creación de jugador.  
3. El usuario envía al sistema el formulario rellenado.  
4. El sistema lo valida, lo registra y le avisa al usuario de que la operación se hizo exitosamente.  
* **Escenarios excepcionales:**  
  **–** 4 a) El nombre tiene un largo inferior a 1 o superior a 20 caracteres.  
  	\* El sistema no registra al jugador y solicita al usuario que vuelva a rellenar el formulario con un nombre válido.  
  **–** 4 b) El usuario estableció una estadística con un valor inferior a 20 o superior a 100\.  
  	\* El sistema no registra al jugador y solicita al usuario que establezca las estadísticas correctamente en el intervalo de 20 y 100\.  
  **–** 4 c) La suma de las estadísticas del jugador no es igual a 300  
  	\* El sistema no registra al jugador e informa al usuario que la suma de las estadísticas debe ser igual a 300\.

**Caso de Uso 12: Buscar jugadores.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Jugadores.  
* **Escenario exitoso principal:**  
1. El usuario rellena y envía al sistema el formulario de búsqueda con un nombre de jugador.  
2. El sistema busca hasta 50 jugadores asociados al usuario cuyo nombre contenga el nombre escrito en la barra de búsqueda y se los despliega, cada uno con su nombre, sus estadísticas y una opción de ‘Eliminar’ en caso de que sean eliminables.  
* **Escenarios excepcionales:**  
  – 2 a) No hay jugadores registrados asociados al usuario.  
  	\* El sistema no despliega los jugadores registrados y le notifica al usuario que no tiene jugadores.  
  – 2 b) No hay jugadores registrados asociados al usuario cuyo nombre contenga el nombre ingresado en la barra de búsqueda.  
  	\* El sistema no despliega los jugadores registrados y le notifica al usuario que no se encontraron jugadores que coincidan con lo ingresado en la barra de búsqueda.

**Caso de Uso 13: Eliminar un jugador.**

* **Actor primario:** Usuario.  
* **Precondición:** Hay jugadores eliminables en la lista.  
* **Ámbito:** Sistema de Jugadores.  
* **Escenario exitoso principal:**  
1. El usuario selecciona un jugador, selecciona la opción de eliminarlo y confirma la operación, enviando el pedido de eliminación al sistema.  
2. El sistema valida que el jugador no pertenezca a ningún equipo, lo elimina y le notifica al usuario que la operación se realizó exitosamente.	  
* **Escenarios excepcionales:**

	– 2 a) El jugador se volvió integrante de un equipo después de que aparezca en la lista.  
		\* El sistema no elimina al jugador, le notifica al usuario que ese jugador es un integrante de un equipo, por lo que no puede eliminarse, y desactiva la opción de ‘Eliminar’ asociado a ese jugador.

**Caso de Uso 14: Acceder al sistema de Ligas**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario está autenticado.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de acceder al sistema de Ligas, solicitando al sistema principal que le permita acceder.  
2. El sistema redirige al usuario al sistema de ligas y le despliega hasta 50 ligas.  
*  **Escenarios excepcionales:** Ninguno.

**Caso de Uso 15: Crear una Liga.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de crear una liga, solicitando la operación al sistema.  
2. El sistema le despliega al usuario el formulario de creación de liga.  
3. El usuario rellena y envía al sistema el formulario.  
4. El sistema lo valida, registra la liga, registra al usuario como creador y participante y le avisa que la operación se hizo exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) El formulario está incompleto.  
  	\* El sistema no registra la liga y le solicita al usuario que reenvíe el formulario completo.  
  – 4 b) El mínimo de clubes establecido en el formulario es inferior a 3\.  
  	\* El sistema no registra la liga y le informa al usuario que no puede registrarse una liga con un mínimo de equipos menor que 3\.  
  – 4 c) El máximo de clubes es menor que el mínimo.  
  	\* El sistema no registra la liga y le informa al usuario que no puede registrarse una liga con un máximo de equipos menor que el mínimo.  
  – 4 d) El nombre de liga supera los 20 caracteres de largo.  
  	\* El sistema no registra la liga y le solicita al usuario reenviar el formulario con un nombre más corto. 

**Caso de Uso 16: Buscar Ligas.**

* **Actor primario:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**  
  1. El usuario envía al sistema el formulario de búsqueda rellenado con un nombre de liga.  
  2. El sistema busca hasta 50 ligas cuyo nombre contenga el nombre escrito en la barra de búsqueda, y se las despliega al usuario, cada una con su nombre, nombre de creador, cantidad de participantes, máximo de participantes y privacidad.  
* **Escenarios excepcionales:**  
  – 2 a) No hay ligas registradas.  
  	\* El sistema no despliega las ligas registradas y le notifica al usuario que no hay ligas para mostrar.  
  – 2 b) No hay ligas registradas cuyo nombre contenga el nombre ingresado en la barra de búsqueda.  
  	\* El sistema no despliega las ligas registradas y le notifica al usuario que no se encontraron ligas que coincidan con lo ingresado en la barra de búsqueda.

**Caso de Uso 17: Unirse a una Liga que no necesita contraseña.**

* **Actor primario:** Usuario.  
* **Precondición:**    
  * Hay al menos una liga en la lista que:  
    * No está iniciada, y  
    * No está llena, y  
    * Es pública.  
  * El usuario tiene al menos seis jugadores registrados.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario selecciona una liga de la lista (que cumple la precondición) y selecciona la opción de unirse, solicitando al sistema la operación.  
2. La liga despliega al usuario el sistema de elección de equipo.  
3. El usuario forma un equipo y envía los datos.  
4. El sistema valida el equipo, solicita acceso al registro de ligas, valida que la liga no esté llena y registra al equipo como participante de la liga.  
* **Escenarios excepcionales:**  
  – 4 a) El equipo formado no está completo  
  	\* El sistema no une al usuario a la liga y le solicita que forme un equipo válido.  
  – 4 b) La liga se llenó antes de que el sistema pueda registrar al participante.  
  	\* El sistema no une al usuario a la liga y le informa que la liga no permite más participantes.

**Caso de Uso 18: Unirse a Liga que necesita Contraseña.**

* **Actor primario:** Usuario.  
* **Precondición:**    
  * Hay al menos una liga en la lista que:  
    * Es privada, y  
    * No está llena , y  
    * No está iniciada.  
  * El usuario tiene, al menos, seis jugadores registrados.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario selecciona una liga de la lista (que cumple la precondición) y selecciona la opción de unirse, solicitando al sistema la operación.  
2. El sistema le despliega un formulario para que el usuario ingrese la contraseña de la liga.  
3. El usuario rellena y envía el formulario con la contraseña de la liga.  
4. El sistema valida la contraseña y despliega al usuario el sistema de elección de equipo.  
5. El usuario forma un equipo y envía los datos.  
6. El sistema valida el equipo formado, solicita acceso al registro de ligas, valida que la liga no esté llena y registra al equipo como participante de la liga.  
* **Escenarios excepcionales:**  
  – 4 a) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no une al usuario a la liga y le notifica que las contraseñas no coinciden.  
  – 6 a) El equipo formado no está completo.  
  	\* El sistema no une al usuario a la liga y le solicita que forme un equipo válido.  
  – 6 b) La liga se llenó antes de que el sistema pueda registrar al participante.  
  	\* El sistema no une al usuario a la liga y le informa que la liga no permite más participantes.

**Caso de Uso 19: Iniciar una Liga.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * Hay suficientes clubes unidos en la liga.  
  * La liga no está iniciada.  
  * El usuario es el creador de la liga.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**   
1. El usuario selecciona la liga de la lista y selecciona la opción ‘Iniciar Liga’, solicitando al sistema la operación.  
2. El sistema accede al registro de ligas, inicia la liga y guarda el fixture.   
* **Escenarios excepcionales:**   
  – 2 a) La cantidad de participantes es inferior al mínimo.  
  	\* El sistema no inicia la liga y le notifica al usuario que faltan jugadores para llegar al mínimo.

**Caso de Uso 20: Entrar a Jugar un Partido de Liga**

* **Actor principal:** Usuario.  
* **Precondición:**  Hay al menos una liga en la lista que:  
  * Está iniciada, y  
  * El usuario es participante de ella.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista (que cumple la precondición) y selecciona la opción de ‘Partidos de Liga en Vivo’. solicitando al sistema la operación.  
2. El sistema busca partidos de la liga en vivo y le despliega una ventana con una lista de ellos. Al menos uno de los partidos que le despliega es un partido que el usuario puede jugar. Cada partido que el usuario puede jugar es desplegado con una opción de ‘Jugar Partido’.  
3. El usuario selecciona la opción de ‘Jugar Partido’ del partido que quiera jugar.  
4. El sistema redirige al usuario al partido en vivo en calidad de jugador.  
* **Escenarios excepcionales:**  
  – 2 a) No hay partidos de la liga en vivo.  
  	\* El sistema le muestra la lista vacía al usuario y le notifica que no hay partidos de la liga en vivo en el momento.  
  – 2 b) No hay partidos en vivo que el usuario pueda jugar.  
  	\* El sistema le muestra la lista al usuario con partidos que puede ver, pero el usuario no podrá jugar ningún partido de la lista.  
  – 4 a) El partido terminó después de que el sistema lo desplegara pero antes que el sistema pudiera redirigirlo  
  	\* El sistema no redirige al usuario y le notifica que el partido ya terminó.

NOTA: el caso de uso supone por precondición que el usuario es participante, por lo que no necesita contraseña aunque la liga sea privada. No vamos a cubrir el caso de que el usuario quiera jugar un partido de liga sin ser participante porque nos parece demasiado específico y no tendría un escenario exitoso. 

**Caso de Uso 21: Ver partido de una Liga que no necesita contraseña.**

* **Actor principal:** Usuario.  
* **Precondición:**  Hay al menos una liga en la lista que está iniciada, y  
  * Es pública, o  
  * El usuario es participante, o  
  * El usuario es su creador.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga (que cumpla la precondición) de la lista, y selecciona la opción de ‘Partidos de Liga en Vivo’, solicitando al sistema la operación.  
2. El sistema busca partidos en vivo y le despliega una ventana con una lista de ellos.  
3. El usuario selecciona la opción de ‘Ver Partido’ del partido que quiera ver.  
4. El sistema redirige al usuario al partido en vivo en calidad de espectador.  
* **Escenarios excepcionales:**  
  – 2 a) No hay partidos en vivo.  
  	\* El sistema le muestra la lista vacía al usuario y le notifica que no hay partidos en vivo en el momento.  
  – 4 a) El partido terminó después de que el sistema lo desplegara pero antes que el sistema pudiera redirigirlo.  
  	\* El sistema no redirige al usuario y le notifica que el partido ya terminó.

NOTA: Contemplamos ‘Entrar a Jugar un Partido de Liga’ como un caso específico de ‘Ver partido de una liga pública o de la cual el usuario sea participante’ y no consideramos que todos los partidos en vivo sean jugables como escenario excepcional (si un partido se juega, se está espectando).

**Caso de Uso 22: Ver partido de una Liga que necesita contraseña.**

* **Actor principal:** Usuario.  
* **Precondición:** Hay al menos una liga en la lista que:  
  * Es privada, y  
  * Está iniciada , y  
  * El usuario no es su creador ni es participante.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista y selecciona la opción de ‘Partidos de Liga en Vivo’, solicitando al sistema la operación.   
2. El sistema le despliega un formulario para que ingrese la contraseña asociada a la liga.  
3. El usuario envía el formulario con la contraseña al sistema.  
4. El sistema valida la contraseña ingresada, busca partidos de la liga en vivo y le despliega una ventana con una lista de ellos.  
5. El usuario selecciona el partido que quiera ver.  
6. El sistema redirige al usuario al partido en vivo en calidad de jugador.  
* **Escenarios excepcionales:**  
  – 4 a) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no le muestra partidos en vivo al usuario y le notifica que la contraseña ingresada no corresponde a la de la liga.  
  – 4 b) No hay partidos en vivo.  
  	\* El sistema le muestra la lista vacía al usuario y le notifica que no hay partidos en vivo en el momento.  
  – 6 a) El partido terminó después de que el sistema lo desplegara pero antes que el sistema pudiera redirigirlo  
  	\* El sistema no redirige al usuario y le notifica que el partido ya terminó.

**Caso de Uso 23: Ver fixture de una Liga que no necesita contraseña.**

* **Actor principal:** Usuario.  
* **Precondición:** Hay al menos una liga en la lista que está iniciada, y  
  * Es pública, o  
  * El usuario es participante, o  
  * El usuario es su creador.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista y selecciona la opción de ‘Ver Fixture’, solicitando al sistema la operación.  
2. El sistema le despliega el fixture de la liga al usuario.  
* **Escenarios excepcionales:** Ninguno.

**Caso de Uso 24: Ver fixture de una Liga que necesita contraseña.**

* **Actor principal:** Usuario.  
* **Precondición:** Hay al menos una liga en la lista que:  
  * Es privada, y  
  * Está iniciada, y  
  * El usuario no es su creador, y  
  * El usuario no es participante de ella.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista y selecciona la opción de ‘Ver Fixture’.  
2. El sistema le despliega un formulario al usuario y le solicita que ingrese la contraseña asociada a la liga.  
3. El usuario envía al sistema el formulario con la contraseña.  
4. El sistema valida la contraseña y le despliega el fixture de la liga al usuario.  
* **Escenarios excepcionales:**  
  – 4 a) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no le muestra el fixture de la liga al usuario y le notifica que la contraseña ingresada no corresponde a la de la liga.

**Caso de Uso 25: Ver ranking de una Liga que no necesita contraseña.**

* **Actor principal:** Usuario.  
* **Precondición:** Hay al menos una liga en la lista que está iniciada, y  
  * Es pública, o  
  * El usuario es participante, o  
  * El usuario es su creador.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista y selecciona la opción de ‘Ver Ranking’.  
2. El sistema le despliega el ranking de la liga al usuario: todos los participantes de la liga ordenados de mayor a menor respecto a su puntaje y diferencia de goles.  
* **Escenarios excepcionales:**  
  – 2 a) Ningún partido de la liga terminó aún.  
  	\* El sistema le notifica al usuario que no hay datos para mostrar el ranking.

**Caso de Uso 26: Ver ranking de una Liga que necesita contraseña.**

* **Actor principal:** Usuario.  
* **Precondición:** Hay al menos una liga en la lista que:  
  * Es privada, y  
  * Está iniciada, y  
  * El usuario no es su creador, y  
  * El usuario no es participante de ella.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista (que cumpla la precondición) y y selecciona la opción de ‘Ver Ranking’.  
2. El sistema le despliega un formulario al usuario y le solicita que ingrese la contraseña asociada a la liga.  
3. El usuario envía el formulario con la contraseña.  
4. El sistema le despliega el ranking de la liga al usuario: todos los participantes de la liga ordenados de mayor a menor respecto a su puntaje y diferencia de goles.  
* **Escenarios excepcionales:**  
  – 4 a) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no le muestra el ranking de la liga al usuario y le notifica que la contraseña ingresada no corresponde a la de la liga.  
  – 4 b) Ningún partido de la liga terminó aún.  
  	\* El sistema le notifica al usuario que no hay datos para mostrar el ranking.

**Caso de Uso 27: Abandonar una Liga.**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * Hay al menos una liga en la lista que:  
    * No esté iniciada, y  
    * En la que el usuario participe y no sea el creador.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**  
1. El usuario selecciona una liga (que cumpla la precondición) y selecciona la opción de ‘Abandonar’, solicitando al sistema la operación.  
2. El sistema lo elimina del registro de la liga y avisa al usuario. Si es el creador el único participante, además se cancela la liga.  
* **Escenarios excepcionales:**   
  – 2 a) La liga inició después de que el usuario mande la solicitud de operación pero antes de que el sistema pueda remover al participante.  
  	\* El sistema le notifica al usuario que no hay datos para mostrar el ranking.

**Caso de Uso 28: Cancelar una Liga.**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * Hay al menos una liga en la lista que:  
    * No esté iniciada, y  
    * Que el usuario haya creado.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga de la lista y selecciona la opción de ‘Cancelar Liga’.  
2. El sistema accede al registro de ligas, cancela la liga y le notifica al usuario que la liga fue cancelada exitosamente.  
* **Escenarios excepcionales:**   
  – 2 a) La liga inició después de que el usuario mande la solicitud de operación pero antes de que el sistema pueda cancelarla.  
  	\* El sistema le notifica al usuario que no hay datos para mostrar el ranking.

**Caso de Uso 29: Buscar un Partido Amistoso.**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario tiene al menos 6 jugadores.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**   
1. El usuario selecciona la opción de buscar un partido amistoso, solicitando un emparejamiento al sistema.  
2. El sistema busca otro usuario que esté buscando amistoso, los empareja y los redirige a la selección de equipo (CU 34).  
* **Escenarios excepcionales**: Ninguno.

**Caso de Uso 30: Ver ranking general.**

* **Actor principal:** Usuario.  
* **Precondición:** El usuario está autenticado.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**   
1. El usuario selecciona la opción de ver ranking general.  
2. El sistema le muestra al usuario el ranking general de los clubes ordenados por puntaje, diferencia de goles y partidos jugados.  
* **Casos excepcionales:**  
  – 2 a) Ningún usuario jugó un partido de liga.  
  	\* El sistema le notifica al usuario que no hay datos para mostrar un ranking general aún.

**Caso de Uso 31: Pedir cambio de Jugador.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El partido está iniciado (ya pasó el tiempo de gracia).  
  * El usuario está en calidad de jugador en el partido.  
* **Ámbito:** Partido en Tiempo Real  
* **Escenario exitoso principal:**   
1. El usuario selecciona la opción “Cambio”, seleccionando a un jugador titular y un suplente, enviando los datos al sistema.  
2. El sistema valida que el usuario tenga cambios disponibles y en la próxima pausa retira al jugador A como suplente y pone al jugador B como titular en la posición de jugador A.  
* **Casos excepcionales:**  
  – 2 a) El jugador no tiene cambios disponibles.  
  	\* El sistema anuncia la situación al usuario y no realiza el cambio.

**Caso de Uso 32: Ver comportamiento de Titular.**

* **Actor principal:** Usuario.  
* **Precondición:** El partido está iniciado.  
* **Ámbito:** Partido en Tiempo Real.  
* **Escenario exitoso principal:**   
1. El usuario selecciona un jugador titular.  
2. El sistema le despliega su comportamiento actual con su código.  
* **Casos excepcionales:**   
  – 2 a) El usuario no es jugador del partido.  
  	\* El sistema no le despliega al usuario el comportamiento del jugador seleccionado.  
  – 2 b) El usuario es jugador del partido pero el titular es del equipo rival.  
  	\* El sistema no le despliega al usuario el comportamiento del jugador seleccionado.

**Caso de Uso 33: Reasignar comportamiento de Titular.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El partido está iniciado.  
  * El usuario es jugador del partido.  
* **Ámbito:** Partido en Tiempo Real.  
* **Escenario exitoso principal:**   
1. El usuario selecciona un jugador titular, selecciona reasignar su comportamiento, selecciona un comportamiento y confirma la operación al sistema.  
2. El sistema, a partir del siguiente tick, usará al nuevo comportamiento seleccionado para determinar la lógica del jugador.  
* **Escenarios excepcionales:**  Ninguno.

**Caso de Uso 34: Seleccionar Equipo para Partido Amistoso.**

* **Actor principal:** Usuario.  
* **Precondición:** ninguna.  
* **Ámbito:** Selección de Equipo.  
* **Escenario exitoso principal:**   
1. El usuario selecciona seis integrantes con sus roles y comportamientos.  
2. El sistema espera a que ambos usuarios formen su equipo y, cuando eso ocurre, los redirige al partido en tiempo real.  
* **Casos excepcionales:**   
  – 2 a) El usuario rival no seleccionó un equipo en el plazo de 2 minutos.  
  	\* El sistema no inicia el partido, redirige a ambos jugadores al sistema principal y les notifica que un jugador no terminó su selección a tiempo.

**Caso de Uso 35: Acceder al Sistema Principal**

* **Actor principal:** Usuario.  
* **Precondición:** Ninguna.  
* **Ámbitos:** Sistema de Jugadores, Sistema de Comportamiento, Sistema de Ligas  
* **Escenario exitoso principal:**   
1. El usuario selecciona la opción de acceso al sistema principal.  
2. El sistema redirige al usuario al sistema principal.  
* **Casos excepcionales:** Ninguno.

**Caso de Uso 36: Cancelar Búsqueda de un Partido Amistoso.**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario está buscando un partido amistoso.  
* **Ámbito:** Sistema Principal.  
* **Escenario exitoso principal:**   
1. El usuario selecciona la opción de cancelar búsqueda de un partido amistoso, enviando laa solicitud al sistema.  
2. El sistema cancela la búsqueda del usuario.  
* **Escenarios excepcionales**: Ninguno.
