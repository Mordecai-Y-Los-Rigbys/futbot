"""Validación del código de un behavior antes de guardarlo.

Aplica las reglas de validez de la API de comportamientos sin ejecutar el código:
solo lo parsea y recorre su árbol sintáctico. Informa el primer error, con la regla
que incumple y su ubicación, para que el cliente lo pueda señalar en el editor.
"""

import ast
from dataclasses import dataclass

from app.domain.behavior import BehaviorType, CodeRule
from app.simulation.behaviors.primitives import (
    GENERAL_PRIMITIVES,
    PLAYER_PRIMITIVES,
    behavior_constants,
)
from app.simulation.behaviors.sandbox import ALLOWED_NODES, FORBIDDEN_NAME_PREFIX

MAX_CODE_LINES = 250
MAX_CODE_CHARS = 20000

# Primitivas que puede llamar cada tipo. El DT todavía no tiene primitivas propias.
CALLABLE_PRIMITIVES = {
    BehaviorType.player_behavior: GENERAL_PRIMITIVES | PLAYER_PRIMITIVES,
    BehaviorType.coach_behavior: GENERAL_PRIMITIVES,
}
ALL_PRIMITIVES = GENERAL_PRIMITIVES | PLAYER_PRIMITIVES | frozenset(behavior_constants())

# Nodos con una regla propia. Los que no están acá ni en ALLOWED_NODES
# son constructNotAllowed.
RULE_BY_NODE = {
    ast.Import: CodeRule.import_not_allowed,
    ast.ImportFrom: CodeRule.import_not_allowed,
    ast.FunctionDef: CodeRule.function_definition_not_allowed,
    ast.AsyncFunctionDef: CodeRule.function_definition_not_allowed,
    ast.Lambda: CodeRule.function_definition_not_allowed,
    ast.ClassDef: CodeRule.class_not_allowed,
    ast.For: CodeRule.loop_not_allowed,
    ast.AsyncFor: CodeRule.loop_not_allowed,
    ast.While: CodeRule.loop_not_allowed,
    ast.Yield: CodeRule.loop_not_allowed,
    ast.YieldFrom: CodeRule.loop_not_allowed,
    ast.ListComp: CodeRule.comprehension_not_allowed,
    ast.SetComp: CodeRule.comprehension_not_allowed,
    ast.DictComp: CodeRule.comprehension_not_allowed,
    ast.GeneratorExp: CodeRule.comprehension_not_allowed,
    ast.Global: CodeRule.global_not_allowed,
    ast.Nonlocal: CodeRule.global_not_allowed,
}

# Cómo se nombra en el mensaje cada construcción no permitida que lista el contrato.
CONSTRUCT_NAMES = {
    ast.Await: "await",
    ast.Try: "try",
    ast.With: "with",
    ast.Delete: "del",
    ast.Assert: "assert",
    ast.NamedExpr: "el operador :=",
    ast.JoinedStr: "f-strings",
    ast.Slice: "slices",
    ast.In: "el operador in",
    ast.NotIn: "el operador not in",
    ast.Dict: "diccionarios",
    ast.Set: "conjuntos",
    ast.List: "listas",
    ast.Attribute: "atributos",
}

# Mensaje de cada regla que se informa siempre igual.
MESSAGES = {
    CodeRule.import_not_allowed: "no se permite importar módulos",
    CodeRule.call_not_allowed: "solo se pueden llamar primitivas del sistema",
    CodeRule.function_definition_not_allowed: "no se permite definir funciones",
    CodeRule.class_not_allowed: "no se permite definir clases",
    CodeRule.loop_not_allowed: "no se permiten bucles ni generadores",
    CodeRule.comprehension_not_allowed: "no se permiten comprensiones",
    CodeRule.global_not_allowed: "no se permite global ni nonlocal",
}


@dataclass(frozen=True)
class CodeViolation:
    """Primer error de un código inválido. `line` y `column` empiezan en 1."""

    rule: CodeRule
    line: int
    column: int
    message: str


def is_code_too_long(code: str) -> bool:
    """Más de MAX_CODE_LINES líneas o más de MAX_CODE_CHARS caracteres.

    Un salto de línea al final no agrega una línea. Un `\r\n` cuenta como un solo
    salto porque se separa por `\n`.
    """
    lines = code.split("\n")
    if lines[-1] == "":
        lines.pop()
    return len(lines) > MAX_CODE_LINES or len(code) > MAX_CODE_CHARS


def find_code_violation(code: str, behavior_type: BehaviorType) -> CodeViolation | None:
    """Primer error del código para su tipo, o None si es válido. Nunca lo ejecuta."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as error:
        return _violation(
            CodeRule.syntax_error, error.lineno, error.offset, f"error de sintaxis: {error.msg}"
        )
    except (ValueError, RecursionError, MemoryError):
        # Bytes nulos o un código tan anidado que Python no lo puede parsear.
        return _violation(
            CodeRule.syntax_error, 1, 1, "error de sintaxis: Python no puede leer el código"
        )

    lines = code.split("\n")
    first: tuple[tuple[int, int], CodeRule, str] | None = None
    for node, position, is_decorator in _walk(tree):
        if is_decorator:
            found = (CodeRule.call_not_allowed, "no se permiten decoradores")
        else:
            found = _rule_for(node, behavior_type)
        # `<` estricto: ante un empate gana el nodo padre, que se visita antes
        if found is not None and (first is None or position < first[0]):
            first = (position, *found)

    if first is None:
        return None
    (line, byte_offset), rule, detail = first
    return _violation(rule, line, _char_column(lines, line, byte_offset), detail)


def _rule_for(node: ast.AST, behavior_type: BehaviorType) -> tuple[CodeRule, str] | None:
    """Regla que incumple este nodo y el detalle del mensaje, o None si está permitido."""
    if type(node) in RULE_BY_NODE:
        return RULE_BY_NODE[type(node)], MESSAGES[RULE_BY_NODE[type(node)]]
    if isinstance(node, ast.Call):
        return _call_rule(node, behavior_type)
    if isinstance(node, ast.Name):
        return _name_rule(node)
    if not isinstance(node, ALLOWED_NODES):
        construct = CONSTRUCT_NAMES.get(type(node), type(node).__name__)
        return CodeRule.construct_not_allowed, f"no se permite usar {construct}"
    return None


def _call_rule(node: ast.Call, behavior_type: BehaviorType) -> tuple[CodeRule, str] | None:
    if not isinstance(node.func, ast.Name):
        return CodeRule.call_not_allowed, MESSAGES[CodeRule.call_not_allowed]
    name = node.func.id
    if name in CALLABLE_PRIMITIVES[behavior_type]:
        return None
    if name in GENERAL_PRIMITIVES | PLAYER_PRIMITIVES:
        return CodeRule.primitive_not_allowed_for_type, f"`{name}` no es de {behavior_type.value}"
    return CodeRule.call_not_allowed, f"`{name}` no es una primitiva del sistema"


def _name_rule(node: ast.Name) -> tuple[CodeRule, str] | None:
    if node.id.startswith(FORBIDDEN_NAME_PREFIX):
        return CodeRule.construct_not_allowed, f"no se permite el nombre `{node.id}`"
    if isinstance(node.ctx, ast.Store) and node.id in ALL_PRIMITIVES:
        return CodeRule.primitive_assignment_not_allowed, f"`{node.id}` es una primitiva"
    return None


def _walk(tree: ast.AST):
    """Recorre todos los nodos con su posición (línea, offset en bytes) y si son
    un decorador.

    Algunos nodos no tienen posición (por ejemplo, el operador `in`): usan la del
    nodo que los contiene. Es iterativo para no chocar con el límite de recursión.
    """
    pending = [(tree, (1, 0), False)]
    while pending:
        node, parent_position, is_decorator = pending.pop()
        position = parent_position
        if hasattr(node, "lineno"):
            position = (node.lineno, node.col_offset)
        yield node, position, is_decorator
        decorators = getattr(node, "decorator_list", [])
        pending.extend(
            (child, position, child in decorators) for child in ast.iter_child_nodes(node)
        )


def _char_column(lines: list[str], line: int, byte_offset: int) -> int:
    """Pasa el offset en bytes UTF-8 del AST a una columna en caracteres."""
    text = lines[line - 1].encode("utf-8")[:byte_offset]
    return len(text.decode("utf-8", errors="ignore")) + 1


def _violation(rule: CodeRule, line: int | None, column: int | None, detail: str) -> CodeViolation:
    line = max(line or 1, 1)
    column = max(column or 1, 1)
    return CodeViolation(rule, line, column, f"Línea {line}, columna {column}: {detail}.")
