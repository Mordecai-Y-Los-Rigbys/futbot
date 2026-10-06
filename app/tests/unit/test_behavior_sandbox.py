import time
import itertools
import sys

import pytest

from app.simulation.behaviors.sandbox import (
    BehaviorCompileError,
    BehaviorTimeout,
    compile_behavior,
    run_behavior,
)

GENEROUS = 10.0  # segundos: el límite de tiempo no interviene


def run(source, namespace=None):
    namespace = {} if namespace is None else namespace
    run_behavior(compile_behavior(source), namespace, GENEROUS)
    return namespace


# --- compilación --------------------------------------------------------------


def test_syntax_error_is_a_compile_error():
    with pytest.raises(BehaviorCompileError):
        compile_behavior("if True")


@pytest.mark.parametrize(
    "source",
    [
        "import os",
        "from os import path",
        "x = ().__class__",
        "x = ball.real",
        "__import__('os')",
        "x = __builtins__",
    ],
)
def test_escape_routes_are_rejected_when_compiling(source):
    with pytest.raises(BehaviorCompileError):
        compile_behavior(source)


@pytest.mark.parametrize(
    "source",
    [
        "while True:\n    pass",
        "for i in (1, 2):\n    pass",
        "try:\n    x = 1\nexcept:\n    pass",
        "try:\n    while True:\n        pass\nexcept:\n    pass\nwhile True:\n    pass",
        "x = [i for i in (1, 2)]",
        "x = {i: i for i in (1, 2)}",
        "x = {i for i in (1, 2)}",
        "x = (i for i in (1, 2))",
        "f = lambda: 1",
        "def f():\n    pass",
        "class A:\n    pass",
    ],
)
def test_structures_outside_the_whitelist_are_rejected(source):
    with pytest.raises(BehaviorCompileError):
        compile_behavior(source)


def test_everything_allowed_compiles_and_runs():
    source = (
        "a, b = (1, 2)\n"
        "a += 1\n"
        "if a > 1 and not b is None:\n"
        "    c = a if b else 0\n"
        "elif a == 0 or b != 2:\n"
        "    c = -a\n"
        "else:\n"
        "    pass\n"
        "d = (a, b)[0] // 2 % 3 * 1.5 - 1 / 2 + 2 ** 2\n"
        "record(d, force=50)\n"
    )
    calls = []
    run(source, {"record": lambda *args, **kwargs: calls.append((args, kwargs))})
    assert calls == [((5.0,), {"force": 50})]


# --- ejecución sin builtins ---------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "open('/etc/passwd')",
        "globals()",
        "abs(-1)",
        "print(1)",
        "eval('1')",
        "getattr(1, 'real')",
        "type(1)",
        "exec('x = 1')",
        "compile('1', '', 'eval')",
        "vars()",
        "dir()",
    ],
)
def test_builtins_do_not_exist(source):
    with pytest.raises(NameError):
        run(source)


def test_the_code_only_sees_the_given_namespace():
    calls = []
    namespace = run("record(answer * 2)", {"record": calls.append, "answer": 21})
    assert calls == [42]
    assert namespace["__builtins__"] == {}


def test_the_code_can_use_its_own_variables():
    namespace = run("a = 2\nb = a + 3")
    assert namespace["b"] == 5


def test_errors_of_the_code_propagate():
    with pytest.raises(ZeroDivisionError):
        run("x = 1 / 0")


# --- límite de tiempo ---------------------------------------------------------


def fake_timer(step):
    """Reloj que avanza `step` segundos cada vez que se consulta."""
    counter = itertools.count()
    return lambda: next(counter) * step


def test_code_over_the_time_limit_is_interrupted():
    source = "\n".join(f"x{i} = {i}" for i in range(50))
    with pytest.raises(BehaviorTimeout):
        run_behavior(compile_behavior(source), {}, time_limit=1.0, timer=fake_timer(0.1))


def test_code_within_the_time_limit_runs_completely():
    source = "\n".join(f"x{i} = {i}" for i in range(50))
    namespace = {}
    run_behavior(compile_behavior(source), namespace, time_limit=1.0, timer=fake_timer(0.001))
    assert namespace["x49"] == 49


def test_the_previous_trace_function_is_restored():
    before = sys.gettrace()
    run("x = 1")
    assert sys.gettrace() is before

    with pytest.raises(ZeroDivisionError):
        run("x = 1 / 0")
    assert sys.gettrace() is before


@pytest.mark.slow
def test_the_time_limit_works_with_the_real_clock():
    behavior = compile_behavior("x = 1\n" * 100_000)
    started = time.perf_counter()
    with pytest.raises(BehaviorTimeout):
        run_behavior(behavior, {}, time_limit=0.005)
    # Se corta cerca del límite, no al terminar el código.
    assert time.perf_counter() - started < 0.1
