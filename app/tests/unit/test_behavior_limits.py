import pytest

from app.simulation.behaviors.limits import BehaviorLimitExceeded
from app.simulation.behaviors.sandbox import compile_behavior, run_behavior

TICK = 0.015  # segundos: el presupuesto de un equipo en un tick


def run(source):
    namespace = {}
    run_behavior(compile_behavior(source), namespace, TICK)
    return namespace


@pytest.mark.parametrize(
    "source",
    [
        "x = 9**9**9",
        'x = "a" * 10**9',
        "x = (1,) * 10**9",
        'x = "%0999999999d" % 1',
        "s = 'aaaaaaaaaa'\n" + "s = s + s\n" * 30,
        "s = 'aaaaaaaaaa'\n" + "s += s\n" * 30,
        "a = 99999\n" + "a = a * a\n" * 40,
    ],
    ids=[
        "potencia",
        "string",
        "tupla",
        "formato",
        "concatenar",
        "concatenar-con-mas-igual",
        "cuadrados",
    ],
)
def test_a_huge_operation_is_cut_before_running(source):
    with pytest.raises(BehaviorLimitExceeded):
        run(source)


def test_nested_tuples_cannot_hide_a_loop():
    # Comparar a y b recorre 2**100 caminos en una sola operación de Python.
    source = "a = (1,)\nb = (1,)\n" + "a = (a, a)\nb = (b, b)\n" * 100 + "c = a == b"
    with pytest.raises(BehaviorLimitExceeded):
        run(source)


@pytest.mark.parametrize(
    "source",
    ["x = 2 ** 64", "x = -(2 ** 63) * 2", "x = 'a' * 101", "x = 101 * (1,)", "x = (((1,),),)"],
)
def test_one_step_over_the_limits_is_rejected(source):
    with pytest.raises(BehaviorLimitExceeded):
        run(source)


def test_the_limits_themselves_are_allowed():
    namespace = run(
        "big = 2 ** 63\n"
        "text = 'a' * 100\n"
        "items = (0,) * 50 + (1,) * 50\n"
        "pairs = ((1, 2), (3, 4))"
    )
    assert namespace["big"].bit_length() == 64
    assert (len(namespace["text"]), len(namespace["items"])) == (100, 100)
    assert namespace["pairs"] == ((1, 2), (3, 4))


def test_each_augmented_assignment_keeps_its_operator():
    namespace = run("total = 10\ntotal -= 4\ntotal *= 3\ntotal //= 4\ntotal **= 2")
    assert namespace["total"] == 16
