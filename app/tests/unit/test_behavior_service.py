from app.services.behavior_service import PAGE_SIZE, BehaviorService


def test_page_size_constant_is_50():
    assert PAGE_SIZE == 50


def test_list_all_without_filter(db_session, make_behaviors):
    make_behaviors(1, ["alpha", "beta", "gamma"])
    items, total = BehaviorService(db_session).list_behaviors(1, None, 1)
    assert [i.name for i in items] == ["alpha", "beta", "gamma"]
    assert total == 3


def test_filter_by_name_case_insensitive(db_session, make_behaviors):
    make_behaviors(1, ["Patrol Zone", "attack", "PATROL-2"])
    items, total = BehaviorService(db_session).list_behaviors(1, "patrol", 1)
    assert [i.name for i in items] == ["Patrol Zone", "PATROL-2"]
    assert total == 2


def test_empty_string_name_is_no_filter(db_session, make_behaviors):
    make_behaviors(1, ["a", "b"])
    items, total = BehaviorService(db_session).list_behaviors(1, "", 1)
    assert len(items) == 2
    assert total == 2


def test_no_matches(db_session, make_behaviors):
    make_behaviors(1, ["alpha"])
    items, total = BehaviorService(db_session).list_behaviors(1, "zzz", 1)
    assert items == []
    assert total == 0


def test_page_out_of_range_keeps_total(db_session, make_behaviors):
    make_behaviors(1, ["a", "b", "c"])
    items, total = BehaviorService(db_session).list_behaviors(1, None, 9)
    assert items == []
    assert total == 3


def test_user_isolation_with_and_without_filter(db_session, make_behaviors):
    make_behaviors(1, ["shared", "only-1"])
    make_behaviors(2, ["shared", "only-2"])
    svc = BehaviorService(db_session)

    items, total = svc.list_behaviors(1, None, 1)
    assert sorted(i.name for i in items) == ["only-1", "shared"]
    assert total == 2
    assert all(i.user_id == 1 for i in items)

    items, total = svc.list_behaviors(1, "only-2", 1)
    assert items == []
    assert total == 0


def test_pagination_order_and_total(db_session, make_behaviors):
    rows = make_behaviors(1, [f"b{i:02d}" for i in range(60)])
    ids = sorted(r.id for r in rows)
    svc = BehaviorService(db_session)

    p1, total1 = svc.list_behaviors(1, None, 1)
    p2, total2 = svc.list_behaviors(1, None, 2)

    assert [i.id for i in p1] == ids[:50]
    assert [i.id for i in p2] == ids[50:]
    assert total1 == total2 == 60


def test_wildcards_are_treated_literally(db_session, make_behaviors):
    make_behaviors(1, ["100%", "abc", "a_c"])
    svc = BehaviorService(db_session)

    items, _ = svc.list_behaviors(1, "%", 1)
    assert [i.name for i in items] == ["100%"]

    items, _ = svc.list_behaviors(1, "a_c", 1)
    assert [i.name for i in items] == ["a_c"]

def test_backslash_is_treated_literally(db_session, make_behaviors):
    make_behaviors(1, ["a\\c", "abc"])
    items, _ = BehaviorService(db_session).list_behaviors(1, "a\\c", 1)
    assert [i.name for i in items] == ["a\\c"]