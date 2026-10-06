from datetime import datetime, timezone

import pytest

from app.repositories.league_abstract import LeaguePageData


@pytest.mark.parametrize("page, offset", [(1, 0), (2, 50), (3, 100)])
def test_offset_and_limit(service, fake_repo, page, offset):
    service.list_leagues(name=None, page=page)
    assert fake_repo.calls == [{"name": None, "offset": offset, "limit": 50}]


def test_empty_name_is_treated_as_absent(service, fake_repo):
    service.list_leagues(name="", page=1)
    assert fake_repo.calls[0]["name"] is None


def test_name_is_forwarded(service, fake_repo):
    service.list_leagues(name="boca", page=1)
    assert fake_repo.calls[0]["name"] == "boca"


def test_page_size_is_always_50(service, make_item, fake_repo):
    fake_repo.page = LeaguePageData(items=[make_item()], total=1)
    result = service.list_leagues(name=None, page=1)
    assert result.page == 1
    assert result.page_size == 50


def test_total_comes_from_repository_not_from_items(service, make_item, fake_repo):
    fake_repo.page = LeaguePageData(items=[make_item(id=1)], total=120)
    assert service.list_leagues(name=None, page=3).total == 120


def test_out_of_range_page_returns_empty_items_with_total(service, fake_repo):
    fake_repo.page = LeaguePageData(items=[], total=120)
    result = service.list_leagues(name=None, page=4)
    assert result.items == []
    assert result.total == 120


def test_maps_the_eight_fields(service, make_item, fake_repo):
    fake_repo.page = LeaguePageData(
        items=[make_item(id=5, name="Copa", participants_count=3, max_participants=8)],
        total=1,
    )
    item = service.list_leagues(name=None, page=1).model_dump(mode="json", by_alias=True)["items"][
        0
    ]
    assert item == {
        "id": 5,
        "name": "Copa",
        "creator": {"id": 7, "username": "mgonzalez", "name": "Boca Juniors FC"},
        "status": "preparation",
        "participantsCount": 3,
        "maxParticipants": 8,
        "private": False,
        "createdAt": "2026-01-01T00:00:00Z",
    }


def test_creator_name_is_the_club_name(service, make_item, fake_repo):
    fake_repo.page = LeaguePageData(
        items=[make_item(username="mgonzalez", club_name="Boca Juniors FC")], total=1
    )
    creator = service.list_leagues(name=None, page=1).items[0].creator
    assert creator.username == "mgonzalez"
    assert creator.name == "Boca Juniors FC"


def test_preserves_repository_order(service, make_item, fake_repo):
    fake_repo.page = LeaguePageData(
        items=[make_item(id=1), make_item(id=2), make_item(id=3)], total=3
    )
    ids = [i.id for i in service.list_leagues(name=None, page=1).items]
    assert ids == [1, 2, 3]


@pytest.mark.parametrize("status", ["preparation", "started", "cancelled", "finished"])
def test_includes_every_status(service, make_item, fake_repo, status):
    fake_repo.page = LeaguePageData(items=[make_item(status=status)], total=1)
    result = service.list_leagues(name=None, page=1)
    assert result.items[0].status == status


def test_created_at_is_serialized_in_utc_with_z(service, make_item, fake_repo):
    fake_repo.page = LeaguePageData(
        items=[make_item(created_at=datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc))],
        total=1,
    )
    dumped = service.list_leagues(name=None, page=1).model_dump(mode="json", by_alias=True)
    assert dumped["items"][0]["createdAt"] == "2026-03-04T05:06:07Z"
