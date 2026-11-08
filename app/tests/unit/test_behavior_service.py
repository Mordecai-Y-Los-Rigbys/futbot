from unittest.mock import create_autospec

import pytest

from app.domain.behavior import BehaviorType
from app.errors import ApiError, BehaviorConflictError, ValidationApiError
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    CreateBehaviorData,
    DuplicateBehaviorNameError,
)
from app.services.behavior_service import PAGE_SIZE, BehaviorService
from app.simulation.behaviors.default_behaviors import DEFAULT_BEHAVIORS


@pytest.fixture
def repo():
    mock = create_autospec(AbstractBehaviorRepository, instance=True)
    mock.list_by_user.return_value = ([], 0)
    mock.get_by_id.return_value = None
    mock.name_taken.return_value = False
    return mock


@pytest.fixture
def service(repo):
    return BehaviorService(repo)


def behavior(id=5, user_id=1, name="a", code="x"):
    return BehaviorData(id=id, user_id=user_id, name=name, code=code)


# --- list_behaviors -----------------------------------------------------------


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


# --- get_owned_behavior -------------------------------------------------------


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


# --- create_default_behaviors -------------------------------------------------


def test_create_default_behaviors_creates_a_copy_for_the_user(service, repo):
    service.create_default_behaviors(user_id=7)

    repo.create_many.assert_called_once_with(
        7, [CreateBehaviorData(name=b["name"], code=b["code"]) for b in DEFAULT_BEHAVIORS]
    )


TOO_LONG = "x = 1\n" * 251


def body(name="nuevo", code="go_to(1, 2)", behavior_type="playerBehavior"):
    return {"name": name, "code": code, "type": behavior_type}


def conflict_of(service, request_body):
    with pytest.raises(BehaviorConflictError) as exc:
        service.create_behavior(user_id=1, body=request_body)
    return exc.value


def test_create_saves_the_behavior_of_the_user(service, repo):
    created = behavior(id=9, user_id=1, name="nuevo", code="x = 1")
    repo.create.return_value = created

    request_body = body(code="x = ball_position()", behavior_type="coachBehavior")
    result = service.create_behavior(user_id=1, body=request_body)

    assert result is created
    repo.name_taken.assert_called_once_with(1, "nuevo")
    repo.create.assert_called_once_with(
        1,
        CreateBehaviorData(
            name="nuevo", code="x = ball_position()", type=BehaviorType.coach_behavior
        ),
    )


def test_create_with_an_invalid_body_does_not_touch_the_repository(service, repo):
    with pytest.raises(ValidationApiError):
        service.create_behavior(user_id=1, body={})

    repo.name_taken.assert_not_called()
    repo.create.assert_not_called()


def test_a_taken_name_is_duplicate_name_before_the_code_rules(service, repo):
    repo.name_taken.return_value = True

    error = conflict_of(service, body(code=TOO_LONG + "import os"))

    assert (error.status_code, error.code, error.code_error) == (409, "duplicateName", None)
    repo.create.assert_not_called()


def test_a_code_too_long_is_reported_before_an_invalid_code(service, repo):
    error = conflict_of(service, body(code="import os\n" + TOO_LONG))

    assert (error.status_code, error.code, error.code_error) == (409, "codeTooLong", None)
    repo.create.assert_not_called()


def test_an_invalid_code_reports_the_rule_and_its_location(service, repo):
    error = conflict_of(service, body(code="x = 1\nkick()", behavior_type="coachBehavior"))

    assert (error.status_code, error.code) == (409, "invalidCode")
    assert error.code_error == {"rule": "primitiveNotAllowedForType", "line": 2, "column": 1}
    assert error.message.startswith("Línea 2, columna 1: ")
    repo.create.assert_not_called()


def test_a_name_taken_at_the_same_time_is_duplicate_name(service, repo):
    repo.create.side_effect = DuplicateBehaviorNameError()

    error = conflict_of(service, body())

    assert (error.status_code, error.code, error.code_error) == (409, "duplicateName", None)
