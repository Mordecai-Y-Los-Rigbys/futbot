"""Compilación y ejecución aislada del código de un comportamiento.

El aislamiento tiene dos partes:

- Al compilar solo se aceptan las construcciones de ALLOWED_NODES y se rechazan los
  nombres que empiezan con `__`. Sin bucles, funciones ni try/except, el código no
  puede repetirse ni atrapar el corte por tiempo.

- Al ejecutar, el código solo ve los nombres de las primitivas y constantes.
"""

import ast
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from types import CodeType
from typing import Any

FORBIDDEN_NAME_PREFIX = "__"

# Whitelist de nodos del AST permitidos en el código de un comportamiento
# (ver "Reglas de validez" en API Comportamientos). Cualquier nodo que no esté
# acá se rechaza al compilar.
ALLOWED_NODES = (
    # expresiones
    # (por ejemplo, `go_to(x, y)` sin asignar) y `pass`.
    ast.Module,
    ast.Expr,
    ast.Pass,
    # Control de flujo: if / elif / else
    ast.If,
    ast.IfExp,
    # Variables y asignaciones: leer (Load) y escribir (Store) nombres,
    # `x = ...` y `x += ...`.
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Assign,
    ast.AugAssign,
    # Literales, tuplas y acceso por índice (p[0]).
    ast.Constant,
    ast.Tuple,
    ast.Subscript,
    # Llamadas a primitivas, con argumentos por nombre: kick(force=50).
    ast.Call,
    ast.keyword,
    # Operadores aritméticos.
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    # Operadores unarios: signo y negación lógica.
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.Not,
    # Operadores lógicos: and / or.
    ast.BoolOp,
    ast.And,
    ast.Or,
    # Comparaciones.
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
)


class BehaviorCompileError(Exception):
    """El código no se puede ejecutar de forma segura."""


class BehaviorTimeout(Exception):
    """El comportamiento superó el tiempo permitido por tick."""


@dataclass(frozen=True)
class CompiledBehavior:

    code: CodeType


def compile_behavior(source: str) -> CompiledBehavior:
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as error:
        raise BehaviorCompileError(f"error de sintaxis: {error.msg}") from error

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise BehaviorCompileError(f"nodo no permitido: {type(node).__name__}")

        if isinstance(node, ast.Name) and node.id.startswith(FORBIDDEN_NAME_PREFIX):
            raise BehaviorCompileError(f"nombre no permitido: {node.id}")

    return CompiledBehavior(compile(tree, "<behavior>", "exec"))


def run_behavior(
    behavior: CompiledBehavior,
    namespace: dict[str, Any],
    time_limit: float,
    timer: Callable[[], float] = time.perf_counter,
) -> None:

    namespace["__builtins__"] = {}  # Sacamos los builtins de Python
    deadline = timer() + time_limit

    def check_time(frame, event, arg):
        if timer() > deadline:
            raise BehaviorTimeout(f"superó el límite de {time_limit} s")
        return check_time

    previous = sys.gettrace()
    sys.settrace(check_time)  # Antes de cada linea del comportamiento, ejecutamos el check_time
    try:
        exec(behavior.code, namespace)
    finally:
        # Lo dejamos como estaba, para no seguir ejecutando en el resto del programa
        sys.settrace(previous)
