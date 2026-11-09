# Aislamiento del código de los comportamientos

El servidor ejecuta, en cada tick de cada partido, código Python que escribieron los usuarios. Este documento explica cómo se evita que ese código lea o rompa algo del servidor, o lo frene.

## Las cuatro barreras

| # | Cuándo | Qué hace | Dónde |
|---|---|---|---|
| 1 | Al guardar y al compilar | Solo acepta las construcciones de la API de comportamientos: asignaciones, `if`, operaciones, comparaciones, tuplas, índices y llamadas a primitivas. Rechaza `import`, bucles, funciones, clases, `try`, atributos (`x.y`) y cualquier nombre que empiece con `__`. | `sandbox.py` (`ALLOWED_NODES`) y el validador de behaviors |
| 2 | Al compilar | Cambia cada operación aritmética y cada tupla por una llamada a los límites, que controlan el tamaño del resultado **antes** de calcularlo. | `limits.py` |
| 3 | Al ejecutar | El código no tiene builtins (`open`, `eval`, `__import__`, ...): solo ve las primitivas y las constantes del jugador. Además, se vuelve a rechazar cualquier nombre con `__`, por si el código no pasó por la barrera 1. | `run_behavior` en `sandbox.py` |
| 4 | Al ejecutar | Corte por tiempo: antes de cada línea del comportamiento se mira el reloj, y si el equipo se pasó de su tiempo del tick, la ejecución se corta. Adentro de las primitivas y de los límites no se mira, porque son cortos. | `run_behavior` y `executor.py` |

Como no hay bucles ni funciones, el código de un jugador ejecuta como mucho una vez cada una de sus líneas (250 como máximo). La barrera 4 corta entre línea y línea, pero no puede cortar una operación de Python que ya empezó: por eso existe la barrera 2.

## Los límites

| Límite | Valor | Ejemplo rechazado |
|---|---|---|
| Tiempo por equipo y por tick | 15 ms (30 % del tick de 50 ms, la mitad para cada equipo) | 250 líneas que tardan demasiado |
| Enteros | 64 bits | `9**9**9`, `2 ** 64` |
| Strings, bytes y tuplas que salen de una operación | 100 elementos | `"a" * 10**9`, `b"a" * 10**9`, `s = s + s` repetido |
| Tuplas dentro de tuplas | un nivel: `((1, 2), (3, 4))` sí, `(((1,),),)` no | `a = (a, a)` repetido, que hace que comparar dos tuplas recorra 2^100 caminos |
| Formatear strings o bytes con `%` | no se permite | `"%0999999999d" % 1`, que arma un string de 1 GB |
| Largo del código | 250 líneas y 20.000 caracteres | se rechaza al guardar |

Los floats no tienen límite: sus operaciones tardan siempre lo mismo, y si se pasan dan `inf` o `OverflowError` al instante.

Con estos límites, ninguna operación del código de un jugador tarda más que unos microsegundos ni pide más que unos KB de memoria, así que el corte por tiempo siempre llega a actuar.

## Qué pasa cuando algo falla

| Falla | Cuándo se detecta | Qué pasa |
|---|---|---|
| Código inválido (import, bucles, atributos, `__`) | Al guardarlo | 409 `invalidCode`, con la regla, la línea y la columna. No se guarda. |
| Una operación pasa un límite | Al ejecutar, antes de calcularla | `BehaviorLimitExceeded`. Ese jugador pierde sus acciones del tick. |
| El equipo se pasa de su tiempo | Al ejecutar, entre línea y línea | `BehaviorTimeout`. Ese jugador pierde sus acciones del tick, y los compañeros que faltaban no se ejecutan en ese tick. |
| Un error de Python o de una primitiva (`1 / 0`, un dorsal que no existe) | Al ejecutar | Ese jugador pierde sus acciones del tick. |
| Un nombre que no existe (`open`, `globals`, una variable de otro tick) | Al ejecutar | `NameError`: ese jugador pierde sus acciones del tick. |

Perder las acciones del tick quiere decir que el jugador sigue con su último movimiento y no patea. El resto de los jugadores, el partido y los otros partidos siguen igual. Cada falla queda en el log con el jugador y el tick.

## Qué no cubre

- Todos los partidos corren en el mismo proceso que la API. Las barreras evitan que un comportamiento lo frene, pero no hay un límite de memoria del sistema operativo por partido.
- El tiempo de cada tick se mide con el reloj real: en una máquina muy cargada, un comportamiento normal puede pasarse y perder un tick.