import builtins

import pytest

from app.domain.behavior import BehaviorType, CodeRule
from app.simulation.behaviors.default_behaviors import DEFAULT_BEHAVIORS
from app.simulation.behaviors.primitives import (
    GENERAL_PRIMITIVES,
    PLAYER_PRIMITIVES,
    ActionRecorder,
    MatchClock,
    build_primitives,
)
from app.simulation.behaviors.validation import (
    MAX_CODE_CHARS,
    MAX_CODE_LINES,
    find_code_violation,
    is_code_too_long,
)
from app.tests.unit.simulation_helpers import HOME, player, state

PLAYER = BehaviorType.player_behavior
COACH = BehaviorType.coach_behavior


def rule_of(code, behavior_type=PLAYER):
    violation = find_code_violation(code, behavior_type)
    return violation.rule if violation else None


def test_code_at_the_line_limit_is_not_too_long():
    assert not is_code_too_long("x = 1\n" * MAX_CODE_LINES)


def test_blank_lines_count():
    assert is_code_too_long("x = 1\n" + "\n" * (MAX_CODE_LINES - 1) + "x = 1")


def test_code_with_one_character_more_than_the_limit_is_too_long():
    assert is_code_too_long("x" * (MAX_CODE_CHARS + 1))


def test_characters_are_counted_not_bytes():
    assert not is_code_too_long("ñ" * MAX_CODE_CHARS)


def test_everything_the_api_allows_is_valid():
    code = (
        "a, b = (1, 2)\n"
        "a += 1\n"
        "if a > 1 and not b is None:\n"
        "    c = a if b else 0\n"
        "elif a == 0 or b != 2:\n"
        "    c = -a\n"
        "else:\n"
        "    pass\n"
        "d = (a, b)[0] // 2 % 3 * 1.5 - 1 / 2 + 2 ** 2\n"
        "e = 'speed'\n"
        "kick(force=50)\n"
        "go_to(field_center[0], field_center[1])\n"
    )
    assert find_code_violation(code, PLAYER) is None


@pytest.mark.parametrize("behavior", DEFAULT_BEHAVIORS, ids=lambda behavior: behavior["name"])
def test_default_behaviors_are_valid_player_behaviors(behavior):
    assert find_code_violation(behavior["code"], PLAYER) is None


def test_the_primitive_lists_match_the_primitives_the_match_provides():
    provided = build_primitives(
        state(player(HOME, 1)), (HOME, 1), MatchClock(elapsed=0.0, remaining=1.0), ActionRecorder()
    )
    assert set(provided) == GENERAL_PRIMITIVES | PLAYER_PRIMITIVES


@pytest.mark.parametrize(
    "code, rule",
    [
        ("if True", CodeRule.syntax_error),
        ("import os", CodeRule.import_not_allowed),
        ("from os import path", CodeRule.import_not_allowed),
        ("x = abs(-1)", CodeRule.call_not_allowed),
        ("print(1)", CodeRule.call_not_allowed),
        ("x = ball.real()", CodeRule.call_not_allowed),
        ("x = field_length()", CodeRule.call_not_allowed),
        ("@decorator\ndef f():\n    pass", CodeRule.call_not_allowed),
        ("def f():\n    pass", CodeRule.function_definition_not_allowed),
        ("f = lambda: 1", CodeRule.function_definition_not_allowed),
        ("class A:\n    pass", CodeRule.class_not_allowed),
        ("for i in (1, 2):\n    pass", CodeRule.loop_not_allowed),
        ("while True:\n    pass", CodeRule.loop_not_allowed),
        ("x = yield 1", CodeRule.loop_not_allowed),
        ("x = [i for i in (1, 2)]", CodeRule.comprehension_not_allowed),
        ("x = {i: i for i in (1, 2)}", CodeRule.comprehension_not_allowed),
        ("x = {i for i in (1, 2)}", CodeRule.comprehension_not_allowed),
        ("x = (i for i in (1, 2))", CodeRule.comprehension_not_allowed),
        ("global x", CodeRule.global_not_allowed),
        ("move_in_direction = 1", CodeRule.primitive_assignment_not_allowed),
        ("field_length += 1", CodeRule.primitive_assignment_not_allowed),
        ("a, kick = (1, 2)", CodeRule.primitive_assignment_not_allowed),
        ("await go_to(1, 2)", CodeRule.construct_not_allowed),
        ("try:\n    x = 1\nexcept:\n    pass", CodeRule.construct_not_allowed),
        ("with ball:\n    pass", CodeRule.construct_not_allowed),
        ("x = 1\ndel x", CodeRule.construct_not_allowed),
        ("assert True", CodeRule.construct_not_allowed),
        ("if (x := 1):\n    pass", CodeRule.construct_not_allowed),
        ("x = f'{1}'", CodeRule.construct_not_allowed),
        ("x = my_goal[0:1]", CodeRule.construct_not_allowed),
        ("x = 1 in my_goal", CodeRule.construct_not_allowed),
        ("x = 1 not in my_goal", CodeRule.construct_not_allowed),
        ("x = {'a': 1}", CodeRule.construct_not_allowed),
        ("x = {1, 2}", CodeRule.construct_not_allowed),
        ("x = __builtins__", CodeRule.construct_not_allowed),
        ("x = ().__class__", CodeRule.construct_not_allowed),
    ],
)
def test_each_rule_is_reported(code, rule):
    assert rule_of(code) == rule


@pytest.mark.parametrize("primitive", sorted(PLAYER_PRIMITIVES))
def test_player_primitives_are_not_allowed_for_a_coach(primitive):
    assert rule_of(f"{primitive}()", COACH) == CodeRule.primitive_not_allowed_for_type


@pytest.mark.parametrize("primitive", sorted(GENERAL_PRIMITIVES))
def test_general_primitives_are_allowed_for_both_types(primitive):
    assert rule_of(f"x = {primitive}()", PLAYER) is None
    assert rule_of(f"x = {primitive}()", COACH) is None


@pytest.mark.parametrize(
    "code",
    ["x = 1\x00", "x = " + "1 + " * 9999 + "1"],
    ids=["null byte", "too deep"],
)
def test_code_python_cannot_parse_is_a_syntax_error(code):
    violation = find_code_violation(code, PLAYER)
    assert (violation.rule, violation.line, violation.column) == (CodeRule.syntax_error, 1, 1)


def test_the_column_counts_characters_not_bytes():
    violation = find_code_violation("x = 'ññ'; y = abs(1)", PLAYER)
    assert violation.column == 15


def test_the_syntax_error_location_is_reported():
    violation = find_code_violation("x = 1\nif True", PLAYER)
    assert (violation.rule, violation.line, violation.column) == (CodeRule.syntax_error, 2, 8)


def test_the_first_error_by_line_is_reported():
    # El import está más arriba en el árbol, pero la llamada está antes en el código.
    violation = find_code_violation("x = abs(1)\nimport os", PLAYER)
    assert (violation.rule, violation.line) == (CodeRule.call_not_allowed, 1)


def test_on_the_same_line_the_first_error_by_column_is_reported():
    violation = find_code_violation("x = (abs(1), {1})", PLAYER)
    assert (violation.rule, violation.column) == (CodeRule.call_not_allowed, 6)


def test_an_operator_without_position_uses_the_position_of_its_comparison():
    violation = find_code_violation("x = 1\ny = 2 in my_goal", PLAYER)
    assert (violation.line, violation.column) == (2, 5)


def test_the_message_has_the_location():
    violation = find_code_violation("x = 1\ny = abs(1)", PLAYER)
    assert violation.message.startswith("Línea 2, columna 5: ")


def test_a_syntax_error_is_reported_even_with_an_earlier_error():
    violation = find_code_violation("import os\nif True", PLAYER)
    assert (violation.rule, violation.line, violation.column) == (CodeRule.syntax_error, 2, 8)


@pytest.mark.parametrize(
    "code, column",
    [("kick(force=1, force=2)", 15), ("kick(x='ñ', force=1, force=2)", 22)],
    ids=["ascii", "con ñ"],
)
def test_an_error_python_only_finds_when_compiling_is_a_syntax_error(code, column):
    violation = find_code_violation(code, PLAYER)
    assert (violation.rule, violation.line, violation.column) == (CodeRule.syntax_error, 1, column)


@pytest.mark.parametrize("line_break", ["\r\n", "\r"], ids=["crlf", "cr"])
def test_crlf_and_a_lone_cr_are_one_line_break(line_break):
    code = line_break.join(["x = 1", "", "y = 'ñ' + abs(1)"])
    violation = find_code_violation(code, PLAYER)
    assert (violation.line, violation.column) == (3, 11)


@pytest.mark.parametrize(
    "code, column",
    [("x = 1 +\x0cabs(1)", 9), ("x = '\u2028' + abs(1)", 11)],
    ids=["form feed", "separador de línea Unicode"],
)
def test_characters_python_does_not_take_as_line_breaks_do_not_split(code, column):
    violation = find_code_violation(code, PLAYER)
    assert (violation.line, violation.column) == (1, column)


@pytest.mark.parametrize("line_break", ["\r\n", "\r"], ids=["crlf", "cr"])
def test_line_breaks_are_counted_like_python_does(line_break):
    assert not is_code_too_long(("x = 1" + line_break) * MAX_CODE_LINES)
    assert is_code_too_long(("x = 1" + line_break) * (MAX_CODE_LINES + 1))


def test_the_validator_never_runs_the_code(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("el validador ejecutó el código")

    monkeypatch.setattr(builtins, "exec", fail)
    monkeypatch.setattr(builtins, "eval", fail)

    assert find_code_violation("x = ball_position()\nkick()", PLAYER) is None
    assert rule_of("import os") == CodeRule.import_not_allowed
