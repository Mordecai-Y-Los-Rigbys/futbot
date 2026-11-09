"""Límites de las operaciones del código de un comportamiento.

El corte por tiempo de `run_behavior` actúa entre línea y línea. Una sola operación
de Python puede tardar segundos o pedir gigas de memoria (`9**9**9`, `"a" * 10**9`),
y mientras corre no deja actuar al corte. Por eso, al compilar, cada operación
aritmética y cada tupla se reemplazan por una llamada a estas funciones, que
controlan el tamaño del resultado antes de calcularlo.
"""

import operator
from collections.abc import Callable
from typing import Any

MAX_INT_BITS = 64
MAX_SEQUENCE_LENGTH = 100

OPERATION_NAME = "__operation__"
TUPLE_NAME = "__tuple__"

# Las claves son los nombres de los operadores en el AST.
OPERATIONS: dict[str, Callable[[Any, Any], Any]] = {
    "Add": operator.add,
    "Sub": operator.sub,
    "Mult": operator.mul,
    "Div": operator.truediv,
    "FloorDiv": operator.floordiv,
    "Mod": operator.mod,
    "Pow": operator.pow,
}


class BehaviorLimitExceeded(Exception):
    """Una operación del comportamiento supera los límites de tamaño."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, (str, bytes, tuple))


def _check_int(bits: int) -> None:
    if bits > MAX_INT_BITS:
        raise BehaviorLimitExceeded(f"un entero supera los {MAX_INT_BITS} bits")


def _check_length(length: int) -> None:
    if length > MAX_SEQUENCE_LENGTH:
        raise BehaviorLimitExceeded(f"un string o una tupla supera {MAX_SEQUENCE_LENGTH} elementos")


def _check_before(symbol: str, left: Any, right: Any) -> None:
    """Rechaza, sin calcularlas, las operaciones que podrían tardar o pedir mucha memoria.

    Las demás se calculan rápido, porque sus operandos ya están acotados (o son literales
    del código, que no pasan de 20.000 caracteres), y el entero que dan se controla después.
    """
    if symbol == "Pow" and _is_int(left) and _is_int(right):
        # El resultado tiene al menos estos bits. Si entran, la cuenta es barata.
        _check_int((left.bit_length() - 1) * right + 1)
    if symbol == "Mult":
        for sequence, times in ((left, right), (right, left)):
            if _is_sequence(sequence) and _is_int(times):
                _check_length(len(sequence) * max(times, 0))
    if symbol == "Add" and _is_sequence(left) and _is_sequence(right):
        _check_length(len(left) + len(right))
    if symbol == "Mod" and isinstance(left, (str, bytes)):
        # "%0999999999d" % 1 arma un string de 1 GB (y b"%0999999999d" % 1, 1 GB de bytes).
        raise BehaviorLimitExceeded("no se permite formatear strings con %")


def run_operation(symbol: str, left: Any, right: Any) -> Any:
    """`left <symbol> right`, si el resultado entra en los límites."""
    _check_before(symbol, left, right)
    result = OPERATIONS[symbol](left, right)
    if _is_int(result):
        _check_int(abs(result).bit_length())
    return result


def build_tuple(*items: Any) -> tuple:
    """Una tupla del código. Puede tener tuplas adentro, pero esas no pueden tener otras:
    comparar tuplas muy anidadas tarda exponencialmente, y no se puede cortar."""
    for item in items:
        if isinstance(item, tuple) and any(isinstance(inner, tuple) for inner in item):
            raise BehaviorLimitExceeded("una tupla tiene más de dos niveles")
    return items


GUARDS = {OPERATION_NAME: run_operation, TUPLE_NAME: build_tuple}
