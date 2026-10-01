import pytest

pytestmark = pytest.mark.integration

URL = "/behaviors/me"


def names(r):
    return [i["name"] for i in r.json()["items"]]


def test_list_without_filters_and_response_shape(login, make_behaviors):
    make_behaviors(1, ["a", "b", "c"])

    r = login(1).get(URL)

    assert r.status_code == 200
    assert names(r) == ["a", "b", "c"]
    assert set(r.json()["items"][0].keys()) == {"id", "name"}
    assert r.json()["total"] == 3
    assert r.json()["page"] == 1
    assert r.json()["pageSize"] == 50


def test_page_out_of_range_keeps_real_total(login, make_behaviors):
    make_behaviors(1, ["a", "b"])

    r = login(1).get(URL, params={"page": 5})

    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 2


def test_ilike_case_insensitive_on_postgres(login, make_behaviors):
    make_behaviors(1, ["Patrol Zone", "attack", "PATROL-2", "pAtRoL-3"])

    r = login(1).get(URL, params={"name": "PATROL"})

    assert r.status_code == 200
    assert names(r) == ["Patrol Zone", "PATROL-2", "pAtRoL-3"]
    assert r.json()["total"] == 3


def test_wildcards_escaped_on_postgres(login, make_behaviors):
    make_behaviors(1, ["100%", "abc", "a_c", "a\\c"])
    api = login(1)

    for term, expected in [("%", ["100%"]), ("a_c", ["a_c"]), ("a\\c", ["a\\c"])]:
        r = api.get(URL, params={"name": term})
        assert names(r) == expected


def test_order_is_by_id_not_by_name(login, make_behaviors):
    # Nombres en orden alfabético inverso al id: si faltara ORDER BY id,
    # o se ordenara por nombre, el resultado cambiaría.
    rows = make_behaviors(1, ["z", "y", "x", "w"])

    r = login(1).get(URL)

    assert [i["id"] for i in r.json()["items"]] == [row.id for row in rows]


def test_order_is_stable_after_update(login, db_session, make_behaviors):
    # En Postgres un UPDATE crea una nueva versión de la fila y cambia su
    # posición física: sin ORDER BY explícito, la fila editada saldría al final.
    rows = make_behaviors(1, [f"b{i:02d}" for i in range(60)])
    ids = sorted(r.id for r in rows)
    rows[0].name = "edited"
    db_session.commit()

    api = login(1)
    p1 = api.get(URL, params={"page": 1}).json()
    p2 = api.get(URL, params={"page": 2}).json()

    assert [i["id"] for i in p1["items"]] == ids[:50]
    assert [i["id"] for i in p2["items"]] == ids[50:]
    assert p1["total"] == p2["total"] == 60


def test_filter_and_pagination_combined(login, make_behaviors):
    make_behaviors(1, [f"match-{i:02d}" for i in range(55)] + ["other"] * 10)
    api = login(1)

    p1 = api.get(URL, params={"name": "MATCH", "page": 1}).json()
    p2 = api.get(URL, params={"name": "MATCH", "page": 2}).json()

    assert len(p1["items"]) == 50
    assert len(p2["items"]) == 5
    assert p1["total"] == p2["total"] == 55


def test_user_isolation_on_postgres(login, make_behaviors):
    make_behaviors(1, ["shared", "only-1"])
    make_behaviors(2, ["shared", "only-2"])
    api = login(1)

    r = api.get(URL)
    assert names(r) == ["shared", "only-1"]
    assert r.json()["total"] == 2

    r = api.get(URL, params={"name": "only-2"})
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_max_page_offset_does_not_overflow(login, make_behaviors):
    # offset = (2147483647 - 1) * 50 ≈ 1.07e11: no entra en un int4 de Postgres,
    # este test confirma que el OFFSET se maneja como bigint.
    make_behaviors(1, ["a"])

    r = login(1).get(URL, params={"page": 2147483647})

    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 1