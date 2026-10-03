from unittest.mock import create_autospec

import pytest

from app.errors import ApiError
from app.repositories.behavior_abstract import AbstractBehaviorRepository, BehaviorData, CreateBehaviorData
from app.services.behavior_service import PAGE_SIZE, BehaviorService
from app.services.default_behaviors import DEFAULT_BEHAVIORS

@pytest.fixture
def repo():
    mock = create_autospec(AbstractBehaviorRepository, instance=True)
    mock.list_by_user.return_value = ([], 0)
    mock.get_by_id.return_value = None
    return mock


@pytest.fixture
def service(repo):
    return BehaviorService(repo)


def behavior(id=5, user_id=1, name="a", code="x"):
    return BehaviorData(id=id, user_id=user_id, name=name, code=code)


# ---------- list_behaviors ----------

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


# ---------- get_owned_behavior ----------

def test_returns_own_behavior(service, repo):
    own = behavior(id=5, user_id=1)
    repo.get_by_id.return_value = own

    assert service.get_owned_behavior(user_id=1, behavior_id=5) is own
    repo.get_by_id.assert_called_once_with(5)


def test_nonexistent_raises_404(service):
    with pytest.raises(ApiError) as exc:
        service.get_owned_behavior(user_id=1, behavior_id=5)

    assert exc.value.status_code == 404
    assert exc.value.code is None


def test_other_users_behavior_raises_403_without_leaking(service, repo):
    repo.get_by_id.return_value = behavior(user_id=2, name="ajeno", code="secreto")

    with pytest.raises(ApiError) as exc:
        service.get_owned_behavior(user_id=1, behavior_id=5)

    assert exc.value.status_code == 403
    assert exc.value.code is None
    assert "ajeno" not in exc.value.message
    assert "secreto" not in exc.value.message


def test_get_owned_behavior_is_read_only(service, repo):
    repo.get_by_id.return_value = behavior()

    service.get_owned_behavior(user_id=1, behavior_id=5)

    # el único acceso al repositorio es la lectura por id
    assert [c[0] for c in repo.method_calls] == ["get_by_id"]
    
    
# ---------- create_default_behaviors ----------

def test_create_default_behaviors_creates_a_copy_for_the_user(service, repo):
    service.create_default_behaviors(user_id=7)

    repo.create_many.assert_called_once_with(
        7, [CreateBehaviorData(name=b["name"], code=b["code"]) for b in DEFAULT_BEHAVIORS]
    )