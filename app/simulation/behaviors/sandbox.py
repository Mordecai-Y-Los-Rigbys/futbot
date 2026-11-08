"""Compilación y ejecución aislada del código de un comportamiento.

El aislamiento tiene cuatro partes:

- Al compilar solo se aceptan las construcciones de ALLOWED_NODES y se rechazan los
  nombres que empiezan con `__`. Sin bucles, funciones ni try/except, el código no
  puede repetirse ni atrapar el corte por tiempo.

- Al compilar, cada operación aritmética y cada tupla pasan por los límites de
  `limits.py`, que rechazan los resultados demasiado grandes antes de calcularlos.

- Al ejecutar, el código solo ve los nombres de las primitivas y constantes, y se
  vuelve a rechazar cualquier nombre con `__`.

- Al ejecutar, un corte por tiempo entre línea y línea.
"""

import ast
import copy
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from types import CodeType, FrameType
from typing import Any

from app.simulation.behaviors.limits import GUARDS, OPERATION_NAME, TUPLE_NAME

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


class _GuardOperations(ast.NodeTransformer):
    """Cambia cada operación y cada tupla por una llamada a los límites.

    `a * b` pasa a ser `__operation__("Mult", a, b)`, `a += b` pasa a ser
    `a = __operation__("Add", a, b)` y `(a, b)` pasa a ser `__tuple__(a, b)`. El código
    del usuario no puede nombrar ni pisar esas funciones, porque empiezan con `__`.
    """

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        return _guarded_operation(node.op, node.left, node.right, node)

    def visit_AugAssign(self, node: ast.AugAssign) -> ast.AST:
        self.generic_visit(node)
        current = _as_load(node.target)
        value = _guarded_operation(node.op, current, node.value, node)
        return ast.copy_location(ast.Assign(targets=[node.target], value=value), node)

    def visit_Tuple(self, node: ast.Tuple) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.ctx, ast.Load):
            return node  # `a, b = ...` no arma una tupla
        call = ast.Call(func=ast.Name(TUPLE_NAME, ast.Load()), args=node.elts, keywords=[])
        return ast.copy_location(call, node)


def _guarded_operation(op: ast.operator, left: ast.expr, right: ast.expr, node: ast.AST) -> ast.AST:
    symbol = ast.Constant(type(op).__name__)
    call = ast.Call(
        func=ast.Name(OPERATION_NAME, ast.Load()), args=[symbol, left, right], keywords=[]
    )
    return ast.copy_location(call, node)


def _as_load(target: ast.expr) -> ast.expr:
    """El destino de `a += b`, para leerlo."""
    loaded = copy.deepcopy(target)
    loaded.ctx = ast.Load()
    return loaded


def _names(code: CodeType) -> list[str]:
    """Los nombres que usa el código (variables y atributos), salvo los de los límites.
    Incluye los de las funciones de adentro, aunque compile_behavior no las acepta."""
    names = [name for name in code.co_names if name not in GUARDS]
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            names.extend(_names(constant))
    return names


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

    tree = ast.fix_missing_locations(_GuardOperations().visit(tree))
    return CompiledBehavior(compile(tree, "<behavior>", "exec"))


def run_behavior(
    behavior: CompiledBehavior,
    namespace: dict[str, Any],
    time_limit: float,
    timer: Callable[[], float] = time.perf_counter,
) -> None:

    forbidden = [name for name in _names(behavior.code) if name.startswith(FORBIDDEN_NAME_PREFIX)]
    if forbidden:
        raise BehaviorCompileError(f"nombres no permitidos: {forbidden}")

    namespace["__builtins__"] = {}  # Sacamos los builtins de Python
    namespace.update(GUARDS)

    deadline = timer() + time_limit

    def check_time(frame: FrameType, event: str, arg: Any) -> Callable[..., Any]:
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
