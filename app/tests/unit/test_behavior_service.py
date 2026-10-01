from unittest.mock import create_autospec

import pytest

from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.services.behavior_service import PAGE_SIZE, BehaviorService


@pytest.fixture
def repo():
    mock = create_autospec(AbstractBehaviorRepository, instance=True)
    mock.list_by_user.return_value = ([], 0)
    return mock


@pytest.fixture
def service(repo):
    return BehaviorService(repo)


@pytest.mark.parametrize("page, expected_offset", [(1, 0), (2, PAGE_SIZE), (5, 4 * PAGE_SIZE)])
def test_list_behaviors_translates_page_to_offset(service, repo, page, expected_offset):
    service.list_behaviors(user_id=1, name=None, page=page)

    repo.list_by_user.assert_called_once_with(
        user_id=1, name=None, offset=expected_offset, limit=PAGE_SIZE
    )


def test_list_behaviors_passes_name_filter_through(service, repo):
    service.list_behaviors(user_id=3, name="run", page=1)

    assert repo.list_by_user.call_args.kwargs["name"] == "run"


def test_list_behaviors_returns_what_the_repository_returns(service, repo):
    repo.list_by_user.return_value = (["a", "b"], 12)

    assert service.list_behaviors(user_id=1, name=None, page=1) == (["a", "b"], 12)