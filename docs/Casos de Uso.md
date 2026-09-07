# Casos de Uso

## Caso de Uso 1: Registrar un Usuario

- Actor primario: Actor Externo
- Precondición: Ninguna
- Alcance: Sistema de Registro y Autenticación de Usuarios
- Escenario exitoso principal:
  1. El actor externo selecciona la opción de registrar un usuario.
  2. El sistema le despliega el formulario de registro.
  3. El actor externo rellena y envía el formulario.
  4. El sistema valida el formulario, registra al usuario y notifica el registro exitoso.
- Escenarios excepcionales:
  - 4 a) El mail ya fue registrado anteriormente.
    - El sistema no registra el usuario y notifica que el mail ya está registrado.
  - 4 b) El formulario está incompleto.
    - El sistema no registra el usuario y solicita reenviar el formulario completo.
  - 4 c) El nombre de usuario, nombre de club o la contraseña superan los 20 caracteres.
    - El sistema no registra el usuario y solicita corregir los datos.
  - 4 d) El mail supera los 254 caracteres.
    - El sistema no registra el usuario y solicita corregir los datos.
  - 4 e) El avatar supera 2 MB.
    - El sistema no registra el usuario y solicita corregir los datos.

---
## Caso de Uso 2: Inicio de Sesión

- Actor primario: Actor Externo
- Precondición: Ninguna
- Alcance: Sistema de Registro y Autenticación de Usuarios
- Escenario exitoso principal:
  1. El actor externo selecciona inicio de sesión.
  2. El sistema le despliega el formulario.
  3. El actor externo rellena y envía el formulario.
  4. El sistema valida, autentica y redirige al menú principal.
- Escenarios excepcionales:
  - 4 a) No existe un usuario con esos datos.
    - El sistema no autentica al usuario y notifica que los datos no son correctos.
  - 4 b) El formulario posee campos inválidos.
    - El sistema no registra al usuario y solicita reenviar con los campos corregidos.

---
## Caso de Uso 3: Cerrar Sesión

- Actor primario: Usuario
- Precondición: El usuario está autenticado
- Alcance: Sistema Principal
- Escenario exitoso principal:
  1. El usuario selecciona cerrar sesión.
  2. El sistema cierra la sesión y redirige al sistema de registro y autenticación.
- Escenarios excepcionales: Ninguno

---
## Caso de Uso 4: Acceder al sistema de comportamientos

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema Principal
- Escenario exitoso principal:
  1. El usuario selecciona acceder al Sistema de Comportamientos.
  2. El sistema lo redirige y despliega hasta 50 comportamientos asociados.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 5: Crear Comportamiento

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Comportamientos
- Escenario exitoso principal:
  1. El usuario selecciona crear un comportamiento.
  2. El sistema despliega el formulario.
  3. El usuario envía el formulario completado.
  4. El sistema valida, registra y notifica éxito.
- Escenarios excepcionales:
  - 4 a) El código no es válido.
    - El sistema no registra el comportamiento y notifica que el código no cumple con las reglas.
  - 4 b) El nombre de comportamiento asociado al usuario ya está registrado.
    - El sistema no registra ni actualiza el comportamiento y notifica al usuario.
  - 4 c) El nombre no está entre 1 y 20 caracteres.
    - El sistema no registra el comportamiento y solicita un nombre válido.

---

## Caso de Uso 6: Buscar comportamientos

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Comportamientos
- Escenario exitoso principal:
  1. El usuario rellena y envía el formulario de búsqueda con un nombre.
  2. El sistema busca hasta 50 comportamientos asociados al usuario cuyo nombre contenga el texto ingresado.
  3. Los muestra junto a opciones de comportamiento.
- Escenarios excepcionales:
  - 2 a) No hay comportamientos registrados asociados al usuario.
    - El sistema no muestra comportamientos y notifica que no tiene comportamientos.
  - 2 b) No hay comportamientos cuyo nombre coincida con la búsqueda.
    - El sistema no muestra resultados y notifica que no se encontraron coincidencias.

---

## Caso de Uso 7: Ver detalle de comportamiento

- Actor primario: Usuario
- Precondición: Hay al menos un comportamiento en la lista
- Alcance: Sistema de Comportamientos
- Escenario exitoso principal:
  1. El sistema selecciona un comportamiento de la lista.
  2. El sistema muestra una ventana con el nombre y código asociado.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 8: Modificar Comportamiento

- Actor primario: Usuario
- Precondición: Hay al menos un comportamiento en la lista
- Alcance: Sistema de Comportamientos
- Escenario exitoso principal:
  1. El usuario selecciona un comportamiento y elige modificarlo.
  2. El sistema despliega el formulario de modificación.
  3. El usuario rellena y envía el formulario.
  4. El sistema valida, guarda la modificación y notifica éxito.
- Escenarios excepcionales:
  - 4 a) El código no es válido.
    - El sistema no actualiza el comportamiento.
  - 4 b) El nombre de comportamiento asociado al usuario ya está registrado.
    - El sistema no actualiza el comportamiento y notifica.
  - 4 c) El nombre no está entre 1 y 20 caracteres.
    - El sistema solicita un nombre válido.
  - 4 d) El comportamiento fue eliminado antes de que el sistema obtuviera acceso.
    - El sistema no actualiza el comportamiento y notifica que fue eliminado.

---

## Caso de Uso 9: Eliminar un Comportamiento

- Actor primario: Usuario
- Precondición: Hay al menos un comportamiento en la lista
- Alcance: Sistema de Comportamientos
- Escenario exitoso principal:
  1. El usuario selecciona un comportamiento.
  2. Elige eliminarlo y confirma.
  3. El sistema elimina el comportamiento y notifica éxito.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 10: Acceder al sistema de jugadores

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema Principal
- Escenario exitoso principal:
  1. El usuario selecciona acceder al sistema de Jugadores.
  2. El sistema lo redirige y despliega hasta 50 jugadores asociados con sus estadísticas y opción de “Eliminar” si son eliminables.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 11: Crear un jugador

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Jugadores
- Escenario exitoso principal:
  1. El usuario selecciona crear un jugador.
  2. El sistema despliega el formulario.
  3. El usuario envía el formulario.
  4. El sistema valida, registra y notifica éxito.
- Escenarios excepcionales:
  - 4 a) El nombre tiene menos de 1 o más de 20 caracteres.
    - El sistema no registra al jugador y solicita un nombre válido.
  - 4 b) Una estadística es menor a 20 o mayor a 100.
    - El sistema no registra al jugador y solicita valores correctos.
  - 4 c) La suma de las estadísticas no es igual a 300.
    - El sistema no registra al jugador y informa que la suma debe ser 300.

---

## Caso de Uso 12: Buscar jugadores

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Jugadores
- Escenario exitoso principal:
  1. El usuario rellena y envía el formulario de búsqueda con un nombre.
  2. El sistema busca hasta 50 jugadores asociados cuyos nombres contengan el texto.
  3. Los muestra con nombre, estadísticas y opción de eliminar si son eliminables.
- Escenarios excepcionales:
  - 2 a) No hay jugadores registrados asociados al usuario.
    - El sistema notifica que no tiene jugadores.
  - 2 b) No hay jugadores que coincidan con la búsqueda.
    - El sistema notifica que no se encontraron coincidencias.

---

## Caso de Uso 13: Eliminar un jugador

- Actor primario: Usuario
- Precondición: Hay jugadores eliminables en la lista
- Alcance: Sistema de Jugadores
- Escenario exitoso principal:
  1. El usuario selecciona un jugador y elige eliminarlo.
  2. Confirma la operación.
  3. El sistema valida que no pertenezca a ningún equipo, lo elimina y notifica éxito.
- Escenarios excepcionales:
  - 2 a) El jugador se volvió integrante de un equipo después de aparecer en la lista.
    - El sistema no lo elimina, notifica que es integrante de un equipo y desactiva la opción de eliminar.

---

## Caso de Uso 14: Acceder al sistema de Ligas

- Actor primario: Usuario
- Precondición: El usuario está autenticado
- Alcance: Sistema Principal
- Escenario exitoso principal:
  1. El usuario selecciona acceder al sistema de Ligas.
  2. El sistema lo redirige y despliega hasta 50 ligas.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 15: Crear una Liga

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona crear una liga.
  2. El sistema despliega el formulario.
  3. El usuario envía el formulario.
  4. El sistema valida, registra la liga, registra al usuario como creador y participante, y notifica éxito.
- Escenarios excepcionales:
  - 4 a) El formulario está incompleto.
    - El sistema no registra la liga y solicita completar el formulario.
  - 4 b) El mínimo de clubes es inferior a 3.
    - El sistema no registra la liga y informa que el mínimo debe ser al menos 3.
  - 4 c) El máximo de clubes es menor que el mínimo.
    - El sistema no registra la liga.
  - 4 d) El nombre de liga no está entre 1 y 20 caracteres.
    - El sistema no registra la liga y solicita un nombre válido.

---

## Caso de Uso 16: Buscar Ligas

- Actor primario: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario envía el formulario de búsqueda con un nombre de liga.
  2. El sistema busca hasta 50 ligas cuyo nombre contenga el texto.
  3. Las muestra con nombre, creador, cantidad de participantes, máximo de participantes y privacidad.
- Escenarios excepcionales:
  - 2 a) No hay ligas registradas.
    - El sistema notifica que no hay ligas para mostrar.
  - 2 b) No hay ligas que coincidan con la búsqueda.
    - El sistema notifica que no se encontraron ligas.

---

## Caso de Uso 17: Unirse a una Liga que no necesita contraseña

- Actor primario: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - no está iniciada,
    - no está llena,
    - es pública,
    - y el usuario tiene al menos seis jugadores registrados.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema despliega el menú de opciones.
  3. El usuario elige “Unirse”.
  4. La liga despliega el sistema de elección de equipo.
  5. El usuario forma un equipo y envía los datos.
  6. El sistema valida el equipo, verifica que la liga no esté llena y registra al usuario como participante.
- Escenarios excepcionales:
  - 6 a) El equipo formado no está completo.
    - El sistema no une al usuario a la liga y solicita un equipo válido.
  - 6 b) La liga se llenó antes del registro.
    - El sistema no une al usuario y informa que la liga no permite más participantes.

---

## Caso de Uso 18: Unirse a Liga que necesita Contraseña

- Actor primario: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - es privada,
    - no está llena,
    - no está iniciada,
    - y el usuario tiene al menos seis jugadores registrados.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema muestra el menú de opciones.
  3. El usuario elige “Unirse”.
  4. El sistema despliega un formulario para ingresar la contraseña.
  5. El usuario envía la contraseña.
  6. El sistema valida la contraseña y despliega el sistema de elección de equipo.
  7. El usuario forma un equipo y envía los datos.
  8. El sistema valida el equipo, verifica que la liga no esté llena y registra al usuario como participante.
- Escenarios excepcionales:
  - 6 a) La contraseña no coincide.
    - El sistema no une al usuario y notifica que las contraseñas no coinciden.
  - 8 a) El equipo formado no está completo.
    - El sistema no une al usuario y solicita un equipo válido.
  - 8 b) La liga se llenó antes del registro.
    - El sistema informa que la liga no permite más participantes.

---

## Caso de Uso 19: Iniciar una Liga

- Actor principal: Usuario
- Precondición:
  - Hay suficientes clubes unidos en la liga.
  - La liga no está iniciada.
  - El usuario es el creador.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema muestra un menú de administrador.
  3. El usuario elige “Iniciar Liga”.
  4. El sistema inicia la liga y guarda el fixture.
- Escenarios excepcionales:
  - 4 a) La cantidad de participantes es inferior al mínimo.
    - El sistema no inicia la liga y notifica que faltan jugadores.

---

## Caso de Uso 20: Entrar a Jugar un Partido de Liga

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - está iniciada,
    - y el usuario es participante.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema muestra un menú con opción “Partidos de Liga en Vivo”.
  3. El usuario la selecciona.
  4. El sistema busca partidos en vivo y muestra una lista.
  5. El usuario elige “Jugar Partido”.
  6. El sistema redirige al usuario al partido en vivo como jugador.
- Escenarios excepcionales:
  - 4 a) No hay partidos en vivo.
    - El sistema muestra lista vacía y notifica que no hay partidos.
  - 4 b) No hay partidos en vivo que el usuario pueda jugar.
    - El sistema le muestra partidos que puede ver, pero sin opción de jugar.

---

## Caso de Uso 21: Ver partido de una Liga que no necesita contraseña

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - está iniciada,
    - y es pública, o el usuario es participante, o el usuario es creador.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema muestra el menú de opciones.
  3. El usuario elige “Partidos de Liga en Vivo”.
  4. El sistema busca partidos en vivo y los muestra.
  5. El usuario selecciona “Ver Partido”.
  6. El sistema lo redirige como espectador.
- Escenarios excepcionales:
  - 4 b) No hay partidos en vivo.
    - El sistema muestra lista vacía y notifica que no hay partidos en vivo.

---

## Caso de Uso 22: Ver partido de una Liga que necesita contraseña

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - es privada,
    - está iniciada,
    - y el usuario no es creador ni participante.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema muestra “Partidos de Liga en Vivo”.
  3. El usuario lo selecciona.
  4. El sistema solicita la contraseña.
  5. El usuario la ingresa.
  6. El sistema valida la contraseña, busca partidos en vivo y los muestra.
  7. El usuario elige un partido.
  8. El sistema lo redirige en calidad de jugador.
- Escenarios excepcionales:
  - 6 a) La contraseña no coincide.
    - El sistema no muestra partidos y notifica que la contraseña no corresponde.
  - 6 b) No hay partidos en vivo.
    - El sistema muestra lista vacía y notifica.

---

## Caso de Uso 23: Ver fixture de una Liga que no necesita contraseña

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que está iniciada,
  - y es pública, o el usuario es participante, o el usuario es creador.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga.
  2. El sistema muestra el menú de opciones.
  3. El usuario elige “Ver Fixture”.
  4. El sistema despliega el fixture.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 24: Ver fixture de una Liga que necesita contraseña

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - es privada,
    - está iniciada,
    - el usuario no es creador,
    - el usuario no es participante.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga.
  2. El sistema muestra el menú de opciones.
  3. El usuario elige “Ver Fixture”.
  4. El sistema solicita la contraseña.
  5. El usuario la envía.
  6. El sistema valida la contraseña y despliega el fixture.
- Escenarios excepcionales:
  - 6 a) La contraseña no coincide.
    - El sistema no muestra el fixture y notifica que la contraseña no corresponde.

---

## Caso de Uso 25: Ver ranking de una Liga que no necesita contraseña

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que está iniciada,
  - y es pública, o el usuario es participante, o el usuario es creador.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga.
  2. El sistema muestra el menú.
  3. El usuario elige “Ver Ranking”.
  4. El sistema despliega el ranking de la liga ordenado por puntaje y diferencia de goles.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 26: Ver ranking de una Liga que necesita contraseña

- Actor principal: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - es privada,
    - está iniciada,
    - el usuario no es creador,
    - el usuario no es participante.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga.
  2. El sistema despliega el menú.
  3. El usuario selecciona “Ver Ranking”.
  4. El sistema solicita la contraseña.
  5. El usuario la envía.
  6. El sistema valida la contraseña y muestra el ranking.
- Escenarios excepcionales:
  - 4 b) La contraseña no coincide.
    - El sistema no muestra el ranking y notifica que la contraseña no corresponde.

---

## Caso de Uso 27: Abandonar una Liga

- Actor primario: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - no esté iniciada,
    - el usuario participe,
    - y no sea el creador.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga válida.
  2. El sistema muestra el menú de opciones.
  3. El usuario elige “Abandonar” y confirma.
  4. El sistema lo elimina del registro de la liga y avisa al usuario.
  5. Si el creador es el único participante, además se cancela la liga.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 28: Cancelar una Liga

- Actor primario: Usuario
- Precondición:
  - Hay al menos una liga en la lista que:
    - no esté iniciada,
    - y el usuario la haya creado.
- Alcance: Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona una liga.
  2. El sistema muestra el menú.
  3. El usuario elige “Cancelar Liga”.
  4. El sistema cancela la liga y notifica éxito.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 29: Buscar un Partido Amistoso

- Actor primario: Usuario
- Precondición:
  - El usuario está autenticado.
  - Tiene al menos 6 jugadores.
- Alcance: Sistema Principal
- Escenario exitoso principal:
  1. El usuario selecciona buscar un partido amistoso.
  2. El sistema busca otro usuario que también esté buscando amistoso.
  3. Los empareja y los redirige a la selección de equipo.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 30: Ver ranking general

- Actor principal: Usuario
- Precondición: El usuario está autenticado
- Alcance: Sistema Principal
- Escenario exitoso principal:
  1. El usuario selecciona ver ranking general.
  2. El sistema muestra el ranking general de los clubes ordenados por puntaje, diferencia de goles y partidos jugados.
- Escenarios excepcionales:
  - 2 a) Ningún usuario jugó un partido de liga.
    - El sistema notifica que aún no hay datos para mostrar un ranking general.

---

## Caso de Uso 31: Pedir cambio de Jugador

- Actor principal: Usuario
- Precondición:
  - El partido está iniciado.
  - El usuario está en calidad de jugador.
- Alcance: Partido en Tiempo Real
- Escenario exitoso principal:
  1. El usuario selecciona la opción “Cambio”.
  2. Elige un jugador titular y un suplente.
  3. Envía los datos al sistema.
  4. El sistema valida que haya cambios disponibles.
  5. En la próxima pausa, retira al jugador A como suplente y pone al jugador B como titular en su posición.
- Escenarios excepcionales:
  - 2 a) El jugador no tiene cambios disponibles.
    - El sistema anuncia la situación y no realiza el cambio.

---

## Caso de Uso 32: Ver comportamiento de Titular

- Actor principal: Usuario
- Precondición: El partido está iniciado
- Alcance: Partido en Tiempo Real
- Escenario exitoso principal:
  1. El usuario selecciona un jugador titular.
  2. El sistema le despliega su comportamiento actual con su código.
- Escenarios excepcionales:
  - 2 a) El usuario no es jugador del partido.
    - El sistema no le despliega el comportamiento.
  - 2 b) El usuario es jugador del partido pero el titular es del equipo rival.
    - El sistema no le despliega el comportamiento.

---

## Caso de Uso 33: Reasignar comportamiento de Titular

- Actor principal: Usuario
- Precondición:
  - El partido está iniciado.
  - El usuario es jugador del partido.
- Alcance: Partido en Tiempo Real
- Escenario exitoso principal:
  1. El usuario selecciona un jugador titular.
  2. Elige reasignar su comportamiento.
  3. Selecciona un comportamiento y confirma.
  4. El sistema usará el nuevo comportamiento a partir del siguiente tick para determinar la lógica del jugador.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 34: Seleccionar Equipo para Partido Amistoso

- Actor principal: Usuario
- Precondición: Ninguna
- Alcance: Selección de Equipo
- Escenario exitoso principal:
  1. El usuario selecciona seis integrantes con sus roles y comportamientos.
  2. El sistema espera a que ambos usuarios formen su equipo.
  3. Cuando ocurre, redirige a ambos al partido en tiempo real.
- Escenarios excepcionales: Ninguno

---

## Caso de Uso 35: Acceder al Sistema Principal

- Actor principal: Usuario
- Precondición: Ninguna
- Alcance: Sistema de Jugadores, Sistema de Comportamiento, Sistema de Ligas
- Escenario exitoso principal:
  1. El usuario selecciona la opción de acceso al sistema principal.
  2. El sistema lo redirige al sistema principal.
- Escenarios excepcionales: Ninguno