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