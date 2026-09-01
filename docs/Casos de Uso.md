**Caso de Uso 1: Registrar un Usuario.**

* **Actor primario:** Actor Externo.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Registro y Autenticación de Usuarios.  
* **Escenario exitoso principal:**  
1. El actor externo selecciona la opción de registrar un usuario.  
2. El sistema despliega el formulario de registro de usuario.  
3. El usuario rellena el formulario de registro de usuario y presiona el botón de registrar.  
4. El sistema valida el formulario, registra al usuario y avisa al actor externo que se registró su usuario exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) El sistema detecta que el mail ya fue registrado anteriormente.  
   	\* El sistema no registra el usuario y notifica al actor externo que el mail ya está registrado.  
   – 4 b) El formulario enviado está incompleto.  
   	\* El sistema no registra el usuario y solicita al actor externo reenviar el formulario completo.  
   – 4 c) El formato de mail es incorrecto.  
  	\* El sistema no registra el usuario y solicita al actor externo reenviar .  
  – 4 d) El sistema falla en el proceso de validación.  
  	\* El sistema no registra el usuario y le avisa al actor externo que el registro no pudo realizarse y que espere unos segundos antes de intentarlo nuevamente. Luego, el sistema vuelve a desplegar el formulario sin rellenar.  
  – 4 e) No se puede establecer conexión con el sistema interno de validación.  
  	\* El sistema no registra el usuario.  
  – 4 f) El sistema falla al registrar el usuario.  
  \* El sistema no registra el usuario y le notifica al actor externo que ocurrió un error durante el registro.

**Caso de Uso 2: Inicio de Sesión.**

* **Actor primario:** Actor Externo.  
* **Precondición:** Ninguna.  
* **Ámbito:** Sistema de Registro y Autenticación de Usuarios.  
* **Escenario exitoso principal:**  
1. El actor externo presiona el botón de inicio de sesión.  
2. El sistema le despliega al actor externo el formulario de inicio de sesión.  
3. El actor externo rellena el formulario y presiona el botón de iniciar sesión.  
4. El sistema valida los datos de inicio de sesión,  autentica al usuario y le avisa al actor externo que se inició sesión exitosamente.  
5. El sistema redirige al actor al menú principal.  
* **Escenarios excepcionales:**  
  – 4 a) El sistema detecta que no hay un usuario registrado que coincida con los datos del formulario de inicio de sesión.  
  	\* El sistema no autentica al usuario, no lo redirige al menú principal y se lo notifica.  
  – 4 b) El formulario enviado está incompleto.  
  	\* El sistema no autentica al usuario, no lo redirige al menú principal y se lo notifica.  
  – 4 c) El formato de mail es incorrecto.  
  	\* El sistema no autentica al usuario, no lo redirige al menú principal y se lo notifica.  
  – 4 d) El sistema falla en el proceso de validación.  
  	\* El sistema no autentica al usuario, no lo redirige al menú principal y se lo notifica.   
  – 4 e) No se puede establecer conexión con el sistema interno de validación.  
  	\* El sistema no autentica al usuario y no lo redirige al menú principal. 

**Caso de Uso 3: El usuario cambia su contraseña.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de modificación de contraseña.  
2. El sistema le despliega el formulario de modificación de contraseña.  
3. El usuario envía al sistema el formulario rellenado.  
4. El sistema lo valida, lo registra y le avisa al usuario de que la operación se hizo exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) La contraseña no cumple los requisitos.						\* El sistema avisa al usuario la situación y vuelve a desplegar el formulario.

**Caso de Uso 4: Cierre de sesión.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de cerrar sesión.  
2. El sistema cierra la sesión y redirige al actor externo al sistema de registro y autenticación de usuarios.

**Caso de Uso 5: Acceder al sistema de comportamientos.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado.  
* **Ámbito:** Menú Principal  
* **Escenario exitoso principal:**  
1. El usuario presiona el botón llamado ‘Comportamientos’.  
2. El sistema redirige al usuario al sistema de comportamientos y le despliega hasta 50 comportamientos registrados asociados a éste.  
*  **Escenarios excepcionales:**  
  Ninguno.

**Caso de Uso 6: Crear Comportamiento.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario se haya autenticado.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de crear un comportamiento.  
2. El sistema le despliega al usuario el menú de gestión de comportamientos.  
3. El usuario envía al sistema el formulario rellenado de creación de comportamiento.  
4. El sistema lo valida, lo registra y le avisa al usuario de que la operación se hizo exitosamente.  
* **Escenarios excepcionales:**  
  – 4 a) El código no es válido.  
  	\* El sistema no registra el comportamiento y le notifica al usuario que el código ingresado no cumple con las reglas de validez del sistema.  
  – 4 b) El nombre de comportamiento asociado al usuario ya está registrado.  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que .  
  – 4 c) El nombre es demasiado largo  
  	\* El sistema no registra el comportamiento y le solicita al usuario reducir el largo del nombre.  
  – 4 d) El formulario está incompleto  
  	\* El sistema no registra el comportamiento y le solicita al usuario enviar el formulario completo.  
  – 4 f) El sistema falla al registrar el comportamiento.  
  \* El sistema no registra el comportamiento y le notifica al usuario que ocurrió un error durante el registro.

**Caso de Uso 7: Buscar comportamientos**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario escribe en el buscador un nombre de comportamiento.  
2. El sistema busca hasta 50 comportamientos asociados al usuario cuyo nombre contenga el nombre escrito en la barra de búsqueda, y se los despliega al usuario, cada uno con un botón de ‘Eliminar’.  
*  **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de comportamientos.  
  	\* El sistema no despliega los comportamientos registrados.  
  – 2 b) No hay comportamientos registrados asociados al usuario.  
  	\* El sistema no despliega los comportamientos registrados y le notifica al usuario que no tiene comportamientos.  
  – 2 c) No hay comportamientos registrados asociados al usuario cuyo nombre contenga el nombre ingresado en la barra de búsqueda.  
  	\* El sistema no despliega los comportamientos registrados y le notifica al usuario que no se encontraron comportamientos que coincidan con lo ingresado en la barra de búsqueda.

**Caso de Uso 8: Ver detalle de comportamiento**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado y hayan comportamientos en la lista.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El sistema hace click en un comportamiento de la lista de comportamientos.  
2. El sistema le despliega una ventana con el nombre del comportamiento y su código asociado.  
*  **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de comportamientos.  
  	\* El sistema no despliega la ventana.

**Caso de Uso 9: Modificar Comportamiento.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado y que haya comportamientos en la lista de comportamientos.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario selecciona un comportamiento de la lista de comportamientos.  
2. El sistema le despliega un formulario de modificación con el nombre del comportamiento y su código asociado rellenados con sus valores actuales.  
3. El usuario modifica el formulario y selecciona la opción de guardar cambios, enviándolo al sistema.  
4. El sistema valida el formulario, pide acceso al registro de comportamientos, guarda la modificación cuando obtiene el acceso y le notifica al usuario que el comportamiento se actualizó exitosamente.  
* **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de comportamientos.  
  	\* El sistema no despliega la ventana.  
  – 4 a) El código no es válido  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que el código ingresado no cumple con los requisitos de validez.  
  – 4 b) El nombre de comportamiento asociado al usuario ya está registrado.  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que .  
  – 4 c) El sistema no logra establecer conexión con el registro de comportamientos.  
  	\* El sistema no actualiza el comportamiento.  
  – 4 d) El comportamiento fue eliminado antes que el sistema obtuviera acceso al registro.  
  	\* El sistema no actualiza el comportamiento y le notifica al usuario que el comportamiento fue eliminado antes de poder modificarlo.  
  – 4 f) El sistema falla al guardar la modificación.  
  \* El sistema no actualiza el comportamiento y le notifica al usuario que ocurrió un error durante la actualización.

**Caso de Uso 10: Eliminar un Comportamiento.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado y que haya comportamientos en la lista de comportamientos.  
* **Ámbito:** Sistema de Comportamientos.  
* **Escenario exitoso principal:**  
1. El usuario selecciona el botón de eliminar un comportamiento.  
2. El sistema le pide al usuario que confirme la operación.  
3. El usuario confirma la operación.  
4. El sistema elimina el comportamiento y le notifica al usuario que la operación se realizó exitosamente.	  
* **Escenarios excepcionales:**	  
  – 4 a) El sistema no logra establecer conexión con el registro de comportamientos.  
  	\* El sistema no elimina el comportamiento.  
  – 4 b) El sistema falla al guardar la eliminación.  
  \* El sistema no elimina el comportamiento y le notifica al usuario que ocurrió un error durante la eliminación.

**Caso de Uso 11: Acceder al sistema de jugadores.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado.  
* **Ámbito:** Menú Principal  
* **Escenario exitoso principal:**  
1. El usuario presiona el botón llamado ‘Jugadores’.  
2. El sistema redirige al usuario al sistema de jugadores y le despliega hasta 50 jugadores registrados asociados a éste, con cada uno junto a sus estadísticas y un botón de ‘Eliminar’ si el jugador es eliminable.  
*  **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de jugadores.  
  	\* El sistema no despliega los jugadores registrados.

**Caso de Uso 12: Crear un jugador.**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario se haya autenticado.  
* **Ámbito:** Sistema de Jugadores.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de creación de jugador.  
2. El sistema le despliega el formulario de creación de jugador.  
3. El usuario envía al sistema el formulario rellenado.  
4. El sistema lo valida, lo registra y le avisa al usuario de que la operación se hizo exitosamente.  
* **Escenario excepcionales:**  
  **–** 4 a) El nombre es demasiado largo.  
  	\* El sistema no registra al jugador y solicita al usuario que vuelva a rellenar el formulario con un nombre más corto.  
  **–** 4 b) El formulario está incompleto.  
  	\* El sistema no registra al jugador y solicita al usuario que rellene el formulario completo.  
  **–** 4 c) El usuario estableció una estadística con un valor inferior a 20 o superior a 100\.  
  	\* El sistema no registra al jugador y solicita al usuario que establezca las estadísticas correctamente entre el intervalo de 20 y 100  
  **–** 4 d) La suma de las estadísticas del jugador supera 300  
  	\* El sistema no registra al jugador y solicita al usuario que establezca las estadísticas correctamente.  
  – 4 e) El sistema no logró establecer conexión con el registro de jugadores.  
  	\* El sistema no elimina al jugador.  
  – 4 f) El sistema falla al registrar al jugador.  
  \* El sistema no registra al jugador y le notifica al usuario que ocurrió un error durante el registro.

**Caso de Uso 13: Buscar jugadores.**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario inició sesión.  
* **Ámbito:** Sistema de Jugadores.  
* **Escenario exitoso principal:**  
1. El usuario escribe en el buscador un nombre de jugador.  
2. El sistema busca hasta 50 jugadores asociados al usuario cuyo nombre contenga el nombre escrito en la barra de búsqueda, y se los despliega al usuario, cada uno con su nombre, sus estadísticas y un botón de ‘Eliminar’ en caso de que sean eliminables.  
* **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de jugadores.  
  	\* El sistema no despliega los jugadores registrados.  
  – 2 b) No hay jugadores registrados asociados al usuario.  
  	\* El sistema no despliega los jugadores registrados y le notifica al usuario que no tiene jugadores.  
  – 2 c) No hay jugadores registrados asociados al usuario cuyo nombre contenga el nombre ingresado en la barra de búsqueda.  
  	\* El sistema no despliega los jugadores registrados y le notifica al usuario que no se encontraron jugadores que coincidan con lo ingresado en la barra de búsqueda.

**Caso de Uso 14: Eliminar un jugador.**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario inició sesión y hay jugadores eliminables en la lista.  
* **Ámbito:** Sistema de Jugadores.  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de eliminar un jugador.  
2. El sistema le pide al usuario que confirme la operación.  
3. El usuario confirma la operación.  
4. El sistema valida que el jugador no pertenezca a ningún equipo, lo elimina y le notifica al usuario que la operación se realizó exitosamente.	  
* **Escenarios excepcionales:**

	– 4 a) El jugador es integrante de un equipo.

		\* El sistema no elimina al jugador, le notifica al usuario que ese jugador es un integrante de un equipo, por lo que no puede eliminarse, y desactiva el botón de ‘Eliminar’ asociado a ese jugador.

– 4 b) El sistema no logra establecer conexión con el registro de jugadores.  
	\* El sistema no elimina al jugador.

– 4 c) El sistema falla al registrar la eliminación.

\* El sistema no registra la eliminación del jugador y le notifica al usuario que ocurrió un error durante el registro.

**Caso de Uso 15: Acceder al sistema de Ligas**

* **Actor primario:** Usuario.  
* **Precondición:** Que el usuario esté autenticado.  
* **Ámbito:** Menú Principal  
* **Escenario exitoso principal:**  
1. El usuario presiona el botón llamado ‘Ligas’.  
2. El sistema redirige al usuario al sistema de ligas y le despliega hasta 50 ligas.  
*  **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de ligas.  
  	\* El sistema no despliega ligas registradas

**Caso de Uso 16: Crear una Liga.**

* **Actor primario:** Usuario.  
* **Precondición:** El usuario está autenticado.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario selecciona la opción de crear una liga.  
2. El sistema le despliega el formulario de creación de liga.  
3. El usuario rellena y envía al sistema el formulario.  
4. El sistema lo valida, lo registra y le avisa al usuario de que la operación se hizo exitosamente.   
* **Escenarios excepcionales:**  
  – 4 a) El formulario está incompleto.  
  	\* El sistema no registra la liga y le solicita al usuario que reenvíe el formulario completo.  
  – 4 b) El mínimo de clubes establecido en el formulario es inferior a 3\.  
  	\* El sistema no registra la liga y le informa al usuario que no puede registrarse una liga con un mínimo de equipos menor que 3\.  
  – 4 c) El máximo de clubes es menor que el mínimo.  
  	\* El sistema no registra la liga y le informa al usuario que no puede registrarse una liga con un máximo de equipos menor que el mínimo.  
  – 4 d) El sistema no logra establecer conexión con el registro de ligas.  
  	\* El sistema no registra la liga.  
  – 4 e) El nombre de liga es demasiado largo.  
  	\* El sistema no registra la liga y le solicita al usuario reenviar el formulario con un nombre más corto.  
  – 6 c) El sistema falla al registrar la liga.  
  	\* El sistema no crea la liga y le informa al usuario que hubo un error durante el registro.

**Caso de Uso 17: Buscar Ligas.**

* **Actor primario:** Usuario  
* **Precondición:** El usuario está autenticado.  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario escribe en el buscador un nombre de liga.  
2. El sistema busca hasta 50 ligas cuyo nombre contenga el nombre escrito en la barra de búsqueda, y se las despliega al usuario, cada una con su nombre, y un botón de ‘Eliminar’ en caso de que sean eliminables.  
* **Escenarios excepcionales:**  
  – 2 a) El sistema no logra establecer conexión con el registro de ligas  
  	\* El sistema no despliega las ligas registradas.  
  – 2 b) No hay ligas registradas.  
  	\* El sistema no despliega las ligas registradas y le notifica al usuario que no hay ligas para mostrar.  
  – 2 c) No hay ligas registradas cuyo nombre contenga el nombre ingresado en la barra de búsqueda.  
  	\* El sistema no despliega las ligas registradas y le notifica al usuario que no se encontraron ligas que coincidan con lo ingresado en la barra de búsqueda.

**Caso de Uso 18: Unirse a una Liga Pública.**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * Hay al menos una liga pública en la lista  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario selecciona una liga pública de la lista  
2. El sistema le despliega al usuario un menú de opciones de liga, dentro de las cuales hay un botón llamado ‘Unirse’.  
3. El usuario presiona el botón de unirse a la liga.  
4. La liga despliega al usuario el sistema de elección de equipo.  
5. El usuario forma un equipo y envía los datos.  
6. El sistema valida el equipo, solicita acceso al registro de ligas, valida que la liga no esté llena y registra al equipo como participante de la liga.  
* **Escenarios excepcionales:**  
  – 2 a) La liga está llena.  
  	\* El sistema desactiva el botón ‘Unirse’, por lo que el usuario no puede unirse a la liga.  
  – 2 b) El usuario no tiene 6 jugadores.  
  	\* El sistema desactiva el botón ‘Unirse’, por lo que el usuario no puede unirse a la liga.  
  – 6 a) El equipo formado no es válido (más información en el caso de uso de formar un equipo).  
  	\* El sistema no une al usuario a la liga y le solicita que forme un equipo válido.  
  – 6 b) La liga se llenó antes de que el sistema tuviera acceso al registro de participantes.  
  	\* El sistema no une al usuario a la liga y le informa que la liga no permite más participantes.  
  – 6 c) El sistema falla al registrar al participante.  
  	\* El sistema no une al usuario a la liga y le informa que hubo un error durante el .

**Caso de Uso 19: Unirse a Liga Privada.**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * Hay una liga privada en la lista  
* **Ámbito:** Sistema de Ligas  
* **Escenario exitoso principal:**  
1. El usuario selecciona una liga privada de la lista  
2. El sistema le despliega al usuario un menú de opciones de liga, dentro de las cuales hay un botón llamado ‘Unirse’.  
3. El usuario presiona el botón de unirse a la liga.  
4. La liga le despliega una ventana con un campo para que el usuario ingrese la contraseña de la liga.  
5. El usuario ingresa la contraseña de la liga.  
6. La liga valida la contraseña y despliega al usuario el sistema de elección de equipo.  
7. El usuario forma un equipo y envía los datos.  
8. El sistema valida el equipo, solicita acceso al registro de ligas, valida que la liga no esté llena y registra al equipo como participante de la liga.  
* **Escenarios excepcionales:**  
  – 2 a) La liga está llena.  
  	\* El sistema desactiva el botón ‘Unirse’, por lo que el usuario no puede unirse a la liga.  
  – 2 b) El usuario no tiene 6 jugadores.  
  	\* El sistema desactiva el botón ‘Unirse’, por lo que el usuario no puede unirse a la liga.  
  – 4 a) No se pudo establecer conexión con el registro.  
  	\* El sistema no une al usuario a la liga.  
  – 4 b) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no  une al usuario a la liga y le notifica que las contraseñas no coinciden.  
  – 8 a) El equipo formado no es válido (más información en el caso de uso de formar un equipo).  
  	\* El sistema no une al usuario a la liga y le solicita que forme un equipo válido.  
  – 8 b) La liga se llenó antes de que el sistema tuviera acceso al registro de participantes.  
  	\* El sistema no une al usuario a la liga y le informa que la liga no permite más participantes.  
  – 8 c) El sistema falla al registrar al participante.  
  	\* El sistema no une al usuario a la liga y le informa que hubo un error durante el registro.

**Caso de Uso 16: Cambiar privacidad de liga**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * El usuario es owner de una liga no arrancada.  
* **Ámbito:** Sistema de Ligas  
* **Caso exitoso principal:**   
1. El usuario ingresa a la sección de configuración de la liga.  
2. El sistema despliega la configuración actual de la liga.  
3. El usuario modifica la privacidad de la liga.  
4. El sistema guarda el cambio y notifica al usuario.  
* **Escenarios excepcionales:**  
  	3a) El usuario cambia a privado pero no ingresa la contraseña  
  	\*Se le avisa al usuario que no ingresó contraseña y no se guarda el cambio.

**Caso de Uso 17: Cambiar contraseña de liga**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * El usuario es owner de una liga no arrancada.  
* **Caso exitoso principal:**   
1. El usuario ingresa a la sección de configuración de la liga.  
2. El sistema despliega la configuración actual de la liga.  
3. El usuario modifica la contraseña de la liga.  
4. El sistema guarda el cambio y notifica al usuario.  
* **Escenarios excepcionales:**  
  	3a) El usuario ingresa una contraseña invalida  
  	\*Se le avisa al usuario y no se guarda el cambio.

**Caso de Uso 18: Cambiar máximo de participantes de liga.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * El usuario es owner de una liga no arrancada.  
* **Caso exitoso principal:**   
1. El usuario ingresa a la sección de configuración de la liga.  
2. El sistema despliega la configuración actual de la liga.  
3. El usuario modifica el maximo de participantes de la liga.  
4. El sistema guarda el cambio y notifica al usuario.  
* **Escenarios excepcionales:**  
  	3a) El usuario ingresa una cantidad invalida  
  	\*Se le avisa al usuario y no se guarda el cambio.

**Caso de Uso 19: Cambiar duración de partidos de liga.**

* **Actor principal:** Usuario.  
* **Ámbito:** Sistema de Ligas  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay ligas en la lista  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga privada de la lista  
2. El sistema le despliega al usuario un menú de opciones de liga, dentro de las cuales hay un botón llamado ‘Cambiar Duración de Partidos’.  
3. El usuario presiona el botón de cambiar duración.  
4. El sistema le despliega una ventana con un campo para que el usuario ingrese la duración de los partidos en minutos, y un botón de confirmar.  
5. El usuario ingresa la duración en minutos y presiona el botón de confirmar.  
6. El sistema accede al registro de ligas y guarda la nueva duración.  
* **Escenarios excepcionales:**  
  – 2 a) El usuario no es administrador de la liga  
  	\* En el menú desplegado, no se encuentra el botón ‘Cambiar Duración de Partidos de Liga’ y el usuario no puede cambiar la duración.  
  – 2 b) La liga ya inició  
  	\* En el menú desplegado, no se encuentra el botón ‘Cambiar Duración de Partidos de Liga’ y el usuario no puede cambiar la duración.  
  – 6 a) No se pudo establecer conexión con el registro.  
  	\* El sistema no cambia la duración de los partidos.  
  – 6 b) La liga fue iniciada antes de que el sistema pudiera acceder al registro.  
  	\* El sistema no cambia la duración de los partidos, notifica al usuario que la liga fue iniciada y refresca el menú para no mostrar el menú de liga sin iniciar.

**Caso de Uso 20: Iniciar una liga.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * Hay suficientes clubes unidos en la liga.  
  * La liga no está iniciada.  
* **Ámbito:** Sistema de Ligas  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga.  
2. El sistema le despliega un menú de opciones de administrador de liga, entre ellas un botón ‘Iniciar Liga’.  
3. El usuario presiona el botón ‘Iniciar Liga’.  
4. El sistema accede al registro de ligas, inicia la liga y guarda el fixture.   
* **Escenarios excepcionales:**  
  – 2 a) El usuario no es administrador de la liga  
  	\* Dentro del menú de opciones, no se encuentra el botón de ‘Iniciar una liga’ y el usuario no podrá jugar un partido de Liga.  
  – 4 a) No se pudo establecer conexión con el registro.  
  	\* El sistema no inicia a la liga.  
  – 4 b) El sistema falló al guardar el fixture.  
  	\* El sistema no inicia a la liga y le notifica al usuario que no se pudo iniciar la liga por un error al guardar el fixture.

**Caso de Uso 21: Entrar a Jugar un Partido de Liga**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * Hay al menos una liga en la lista  
* **Ámbito:** Sistema de Ligas  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga de la lista.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Partidos de Liga en Vivo’  
3. El usuario selecciona la opción de ‘Partidos de Liga en Vivo’   
4. El sistema busca partidos de la liga en vivo y le despliega una ventana con una lista de ellos. Al menos uno de los partidos que le despliega es un partido que el usuario puede jugar. Cada partido que el usuario puede jugar es desplegado con un botón de ‘Jugar Partido’.  
5. El usuario presiona el botón de ‘Jugar Partido’ del partido que quiera jugar.  
6. El sistema redirige al usuario al partido en vivo en calidad de jugador.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón de ‘Partidos de Liga en Vivo’ y el usuario no podrá jugar un partido de Liga.  
  – 4 a) No se puede establecer conexión con el registro de partidos.  
  	\* El sistema no le muestra partidos en vivo al usuario.  
  – 4 b) No hay partidos de la liga en vivo.  
  	\* El sistema le muestra la lista vacía al usuario y le notifica que no hay partidos de la liga en vivo en el momento.

  – 4 c) No hay partidos en vivo que el usuario pueda jugar.

  	\* El sistema le muestra la lista al usuario con partidos que puede ver, pero el usuario no podrá jugar ningún partido de la lista.

  – 6 a) No se puede establecer conexión con el partido en vivo.  
  	\* El sistema no redirige al usuario al partido en vivo hasta que se recupere la conexión.

**Caso de Uso 22: Ver partido de una liga pública o de la cual el usuario sea participante.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay al menos una liga pública o una liga de la cual el usuario sea participante en la lista.  
* **Ámbito:** Sistema de Ligas  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga pública o una liga de la cual el usuario sea participante de la lista.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Partidos de Liga en Vivo’  
3. El usuario selecciona la opción de ‘Partidos de Liga en Vivo’   
4. El sistema busca partidos en vivo y le despliega una ventana con una lista de ellos.  
5. El usuario presiona el botón de ‘Ver Partido’ del partido que quiera ver.  
6. El sistema redirige al usuario al partido en vivo en calidad de espectador.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón de ‘Partidos de Liga en Vivo’ y el usuario no podrá ver un partido de Liga.  
  – 4 a) No se puede establecer conexión con el registro de partidos.  
  	\* El sistema no le muestra partidos en vivo al usuario.  
  – 4 b) No hay partidos en vivo.  
  	\* El sistema le muestra la lista vacía al usuario y le notifica que no hay partidos en vivo en el momento.  
  – 6 a) No se puede establecer conexión con el partido en vivo.  
  	\* El sistema no redirige al usuario al partido en vivo hasta que se recupere la conexión.

NOTA: Contemplamos ‘Entrar a Jugar un Partido de Liga’ como un caso específico de ‘Ver partido de una liga pública o de la cual el usuario sea participante’ y no consideramos que todos los partidos en vivo sean jugables como escenarios excepcionales (si un partido se juega, se está espectando).

**Caso de Uso 23: Ver partido de una liga privada de la cual el usuario no es participante.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay al menos una liga privada de la cual el usuario no es participante en la lista.  
* **Ámbito:** Sistema de Ligas  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga, de la cual el usuario no es participante, de la lista.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Partidos de Liga en Vivo’  
3. El usuario selecciona la opción de ‘Partidos de Liga en Vivo’   
4. El sistema le despliega una ventana con un campo y un botón de confirmar y le solicita al usuario que ingrese la contraseña asociada a la liga.  
5. El usuario presiona el botón confirmar.  
6. El sistema valida la contraseña ingresada, busca partidos de la liga en vivo y le despliega una ventana con una lista de ellos.  
7. El usuario presiona el botón de ‘Ver Partido’ del partido que quiera ver.  
8. El sistema redirige al usuario al partido en vivo en calidad de jugador.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón de ‘Partidos de Liga en Vivo’ y el usuario no podrá ver un partido de Liga.  
  – 4 a) No se pudo establecer conexión con el registro.  
  	\* El sistema no le muestra partidos en vivo al usuario hasta reanudar la conexión.  
  – 4 b) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no le muestra partidos en vivo al usuario y le notifica que la contraseña ingresada no corresponde a la de la liga.  
  – 6 a) No se puede establecer conexión con el registro de partidos.  
  	\* El sistema no le muestra partidos en vivo al usuario.  
  – 6 b) No hay partidos en vivo.  
  	\* El sistema le muestra la lista vacía al usuario y le notifica que no hay partidos en vivo en el momento.  
  – 8 a) No se puede establecer conexión con el partido en vivo.  
  	\* El sistema no redirige al usuario al partido en vivo hasta que se recupere la conexión.

**Caso de Uso 24: Ver fixture de una liga pública o en la que el usuario participe.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay al menos una liga pública o en la que el usuario participe  
* **Ámbito:** Sistema de Ligas.  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga privada en la que no participe  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Fixture’  
3. El usuario selecciona la opción de ‘Fixture’   
4. El sistema le despliega el fixture de la liga al usuario.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Fixture’ y el usuario no podrá ver un partido de Liga.  
  – 4 a) No se puede establecer conexión con el registro de partidos.  
  	\* El sistema no le muestra el fixture de la liga al usuario.

**Caso de Uso 25: Ver fixture de una liga privada en la que el usuario no participe.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay al menos una liga privada, en la que el usuario no participe, en la lista.  
* **Ámbito:** Sistema de Ligas.  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga pública o una liga en la que el usuario participe de la lista.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Fixture’  
3. El usuario selecciona la opción de ‘Fixture’.  
4. El sistema le despliega una ventana con un campo y un botón de confirmar y le solicita al usuario que ingrese la contraseña asociada a la liga.  
5. El usuario presiona el botón confirmar.  
6. El sistema valida la contraseña y le despliega el fixture de la liga al usuario.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Fixture’ y el usuario no podrá ver el fixture.  
  – 4 a) No se puede establecer conexión con el registro de ligas.  
  	\* El sistema no le muestra el fixture de la liga al usuario.  
  – 4 b) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no le muestra el fixture de la liga al usuario y le notifica que la contraseña ingresada no corresponde a la de la liga.  
  – 6 a) No se puede establecer conexión con el registro de partidos.  
  	\* El sistema no le muestra el fixture de la liga al usuario.

**Caso de Uso 26: Ver ranking de una liga pública o en la que el usuario participe.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario inició sesión  
  * El usuario pertenece a una liga en estado arrancada.  
* **Ámbito:** Sistema de Ligas.  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga pública o en la que participa.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Ver ranking’.  
3. El usuario selecciona la opción de ‘Ver Ranking’   
4. El sistema le despliega el ranking de la liga al usuario: todos los participantes de la liga ordenados de mayor a menor respecto a su puntaje y diferencia de goles.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Ver Ranking’ y el usuario no podrá ver el ranking de la liga.  
  – 4 a) No se puede establecer conexión con el registro de partidos de liga.  
  	\* El sistema no le muestra el ranking de la liga al usuario.

**Caso de Uso 27: Ver ranking de una liga privada en la que el usuario no participe.**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay al menos una liga privada, en la que el usuario no participe, en la lista.  
* **Ámbito:** Sistema de Ligas.  
* **Caso exitoso principal:**   
1. El usuario selecciona una liga privada en la que no participa.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Ver ranking’.  
3. El usuario selecciona la opción de ‘Ver Ranking’   
4. El sistema le despliega una ventana con un campo y un botón de confirmar y le solicita al usuario que ingrese la contraseña asociada a la liga.  
5. El usuario presiona el botón confirmar.  
6. El sistema le despliega el ranking de la liga al usuario: todos los participantes de la liga ordenados de mayor a menor respecto a su puntaje y diferencia de goles.  
* **Escenarios excepcionales:**  
  – 2 a) La liga no está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Ver Ranking’ y el usuario no podrá ver el ranking de la liga.  
  – 4 a) No se puede establecer conexión con el registro de ligas.  
  	\* El sistema no le muestra el ranking de la liga al usuario.  
  – 4 b) La contraseña que ingresó el usuario no coincide con la contraseña de la liga.  
  	\* El sistema no le muestra el ranking de la liga al usuario y le notifica que la contraseña ingresada no corresponde a la de la liga.  
  – 6 a) No se puede establecer conexión con el registro de partidos de liga.  
  	\* El sistema no le muestra el ranking de la liga al usuario.

**Caso de Uso 28: Abandonar una Liga.**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay ligas seleccionables en la lista.  
* **Ámbito:** Sistema de Ligas.  
* **Escenario exitoso principal:**  
1. El usuario selecciona una liga.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Abandonar’.  
3. El usuario presiona el botón ‘Abandonar’.  
4. El sistema le pide al usuario que confirme la operación.  
5. El usuario confirma la operación.  
6. El sistema lo elimina del registro de la liga y avisa al usuario.  
* **Escenarios excepcionales:**  
  – 2 a) La liga está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Abandonar’ y el usuario no podrá ver el ranking de la liga.  
  – 2 b) El usuario no es participante de la liga.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Abandonar’ y el usuario no podrá ver el ranking de la liga.  
  – 6 a) No se puede establecer conexión con el registro de ligas.  
  	\* El sistema no elimina al participante de la liga.

**Caso de Uso 29: Cancelar una liga.**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * Hay ligas seleccionables en la lista.  
* **Escenario exitoso principal:**   
1. El usuario selecciona una liga en la lista.  
2. El sistema le despliega un menú de opciones de liga, dentro del cual hay un botón de ‘Cancelar Liga’.  
3. El usuario presiona el boton ‘Cancelar’  
4. El sistema accede al registro de ligas, cancela la liga y le notifica al usuario que la liga fue cancelada exitosamente.  
* **Escenarios excepcionales:**  
  – 2 a) La liga está iniciada.  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Cancelar’ y el usuario no puede cancelar la liga.   
  – 2 b) El usuario no es el administrador  
  	\* Dentro del menú de opciones, no se encuentra el botón ‘Cancelar’ y el usuario no puede cancelar la liga. 

**Caso de Uso 30: Buscar un Partido Amistoso**

* **Actor primario:** Usuario.  
* **Precondición:**   
  * El usuario está autenticado.  
  * El usuario tiene al menos 6 jugadores.  
* **Ámbito:** Menú Principal  
* **Escenario exitoso principal:**   
1. El usuario selecciona la opción buscar partido amistoso.  
2. El sistema busca otro usuario que esté buscando amistoso, los empareja y los ingresa al partido.  
* **Escenarios excepcionales**  
  – 2 a) No se logra establecer conexión con el sistema de emparejamiento.

	\* El usuario no encontrará un partido.  
– 2 b) No se logra establecer conexión con el sistema de partidos en tiempo real.  
	\* Los usuarios no ingresarán al partido.

**Caso de Uso 31: Cambiar jugador en partido**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El partido está iniciado (ya pasó el tiempo de gracia.  
  * El usuario está autenticado.  
  * El jugador A es titular y el jugador B es suplente.  
* **Caso exitoso principal:**   
1. El usuario anuncia el cambio de un jugador A titular por otro jugador suplente B.  
2. El sistema valida que el usuario tenga cambios disponibles y en la próxima pausa retira al jugador A como suplente y pone al jugador B como titular en la posición de jugador A.  
* **Casos excepcionales:**  
  – 2 a) El jugador no tiene cambios disponibles.  
  	\* El sistema anuncia la situación al usuario y no realiza el cambio.  
  – 2 b) No se logra establecer conexión con el partido en tiempo real  
  	\* El sistema no realiza el cambio.

**Caso de Uso 32 Reasignar comportamiento de Titular en Partido**

* **Actor principal:** Usuario.  
* **Precondición:**   
  * El partido está iniciado.  
  * El usuario está autenticado.  
  * El comportamiento A es el comportamiento actualmente asignado al jugador.  
  * El comportamiento B fue creado previo al inicio del tiempo de gracia del partido.   
  * El jugador a quien se le reasignará el cambio es titular.  
* **Caso exitoso principal:**   
1. El usuario anuncia que reasignará el comportamiento A de un jugador titular determinado por un comportamiento B.  
2. El sistema, a partir del siguiente tick, usará al comportamiento B para determinar la lógica del jugador.  
* **Casos excepcionales:**  
  – 2 a) No se logra establecer conexión con el partido en tiempo real  
  \* El sistema no realiza la reasignación.

**Caso de Uso 33 Ver ranking global:**

* **Actor principal:** Usuario.  
* **Precondición:** El usuario está autenticado.  
* **Ámbito:** Menú principal  
* **Caso exitoso principal:**   
1. El usuario selecciona la opción de ver ranking global.  
2. El sistema le muestra al usuario el ranking global de los jugadores ordenados por puntaje, diferencia de goles y partidos jugados.  
* **Casos excepcionales:**  
  – 2 a) No se logra establecer conexión con el registro de partidos  
  \* El sistema no le muestra al usuario el ranking global.  
  – 2 b) Ningún usuario jugó un partido de liga.  
  \* El sistema le notifica al usuario que no hay datos para mostrar un ranking global aún.

* Registrar un Usuario.   
* Inicio de Sesión.   
* El usuario cambia su contraseña.   
* Crear Comportamiento  
* Crear una Liga.   
* El usuario crea un jugador.   
*  El usuario elimina un jugador.  
*  Modificar Comportamiento.   
* Eliminar un Comportamiento   
*  Unirse a una Liga  
* Abandonar una liga  
* Borrar una liga.  
* Iniciar una liga.  
*  Iniciar un partido  
* Cambiar jugador en partido   
* Cambiar comportamiento en partido

