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
