"""Compilación y ejecución aislada del código de un comportamiento.

El aislamiento tiene dos partes:

- Al compilar se rechaza el acceso a atributos (`x.__class__`), los nombres
  que empiezan con `__` y los `import`.

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
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise BehaviorCompileError("no se permiten imports")
        if isinstance(node, ast.Attribute):
            raise BehaviorCompileError("no se permite el acceso a atributos")
        if isinstance(node, ast.Name) and node.id.startswith(FORBIDDEN_NAME_PREFIX):
            raise BehaviorCompileError(f"nombre no permitido: {node.id}")

    return CompiledBehavior(compile(tree, "<behavior>", "exec"))


def run_behavior(
    behavior: CompiledBehavior,
    namespace: dict[str, Any],
    time_limit: float,
    timer: Callable[[], float] = time.perf_counter,
) -> None:
    
    namespace["__builtins__"] = {} # Sacamos los builtins de Python
    deadline = timer() + time_limit

    def check_time(frame, event, arg):
        if timer() > deadline:
            raise BehaviorTimeout(f"superó el límite de {time_limit} s")
        return check_time

    previous = sys.gettrace()  
    sys.settrace(check_time) # Antes de cada linea del comportamiento, ejecutamos el check_time
    try:
        exec(behavior.code, namespace)
    finally:
        # Lo dejamos como estaba, para no seguir ejecutando en el resto del programa
        sys.settrace(previous) 
