"""Chequeo básico del código de los behaviors iniciales.

Hasta que exista el validador de POST /behaviors, este test verifica a mano
las reglas de docs/API Comportamientos.md recorriendo el AST.
"""

import ast

import pytest

from app.services.default_behaviors import DEFAULT_BEHAVIORS

PRIMITIVES = {
    "move_in_direction", "go_to", "kick", "kick_to",
    "my_position", "my_number", "i_have_ball",
    "teammate_position", "opponent_position", "teammate_stat", "opponent_stat",
    "ball_position", "teammate_has_ball", "opponent_has_ball", "nobody_has_ball",
    "distance", "elapsed_time", "remaining_time", "current_period",
}
CONSTANTS = {
    "field_length", "field_width", "goal_width", "player_radius", "ball_radius",
    "my_goal", "opponent_goal", "field_center",
    "bottom_left_corner", "bottom_right_corner", "top_left_corner", "top_right_corner",
}
FORBIDDEN = (
    ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Lambda, ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp,
    ast.DictComp, ast.GeneratorExp, ast.Attribute,
    ast.Try, ast.TryStar,
)
MAX_LINES = 250

BEHAVIORS = pytest.mark.parametrize("behavior", DEFAULT_BEHAVIORS, ids=lambda b: b["name"])


def test_there_are_three_with_distinct_names():
    names = [b["name"] for b in DEFAULT_BEHAVIORS]
    assert len(names) == 3
    assert len(set(names)) == 3


@BEHAVIORS
def test_name_has_1_to_20_characters(behavior):
    assert 1 <= len(behavior["name"]) <= 20


@BEHAVIORS
def test_code_is_valid_python_within_the_line_limit(behavior):
    ast.parse(behavior["code"])  # lanza SyntaxError si no es válido
    assert len(behavior["code"].splitlines()) <= MAX_LINES


@BEHAVIORS
def test_code_has_no_forbidden_constructs(behavior):
    tree = ast.parse(behavior["code"])
    found = [type(node).__name__ for node in ast.walk(tree) if isinstance(node, FORBIDDEN)]
    assert found == []


@BEHAVIORS
def test_code_only_calls_primitives(behavior):
    tree = ast.parse(behavior["code"])
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name), ast.unparse(node)
            assert node.func.id in PRIMITIVES, node.func.id


@BEHAVIORS
def test_code_only_reads_known_names(behavior):
    # Detecta typos (field_widht) y nombres que no existen en el sandbox (abs, open).
    tree = ast.parse(behavior["code"])
    names = [node for node in ast.walk(tree) if isinstance(node, ast.Name)]
    assigned = {n.id for n in names if isinstance(n.ctx, ast.Store)}
    read = {n.id for n in names if isinstance(n.ctx, ast.Load)}
    assert read <= PRIMITIVES | CONSTANTS | assigned, read - PRIMITIVES - CONSTANTS - assigned