from unittest.mock import create_autospec

import pytest

from app.domain.behavior import BehaviorType, BehaviorUsage
from app.errors import ApiError, BehaviorConflictError, ValidationApiError
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    CreateBehaviorData,
    DuplicateBehaviorNameError,
    UpdateBehaviorData,
)
from app.services.behavior_service import PAGE_SIZE, BehaviorService
from app.simulation.behaviors.default_behaviors import DEFAULT_BEHAVIORS


@pytest.fixture
def repo():
    mock = create_autospec(AbstractBehaviorRepository, instance=True)
    mock.list_by_user.return_value = ([], 0)
    mock.get_by_id.return_value = None
    mock.name_taken.return_value = False
    mock.usage.return_value = None
    return mock


@pytest.fixture
def service(repo):
    return BehaviorService(repo)


def behavior(
    id=5, user_id=1, name="a", code="x", behavior_type=BehaviorType.player_behavior, deleted=False
):
    return BehaviorData(
        id=id, user_id=user_id, name=name, code=code, type=behavior_type, deleted=deleted
    )


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

    assert (result.id, result.name, result.deletable) == (9, "nuevo", True)
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


# --- update_behavior ----------------------------------------------------------


def edit(name="nuevo", code="go_to(1, 2)"):
    return {"name": name, "code": code}


@pytest.fixture
def owned(repo):
    """El behavior 5 existe y es del usuario 1."""
    repo.get_by_id.return_value = behavior(id=5, user_id=1, name="viejo")
    repo.update.side_effect = lambda behavior_id, data: behavior(
        id=behavior_id, user_id=1, name=data.name, code=data.code
    )
    return repo


def update_conflict_of(service, request_body):
    with pytest.raises(BehaviorConflictError) as exc:
        service.update_behavior(user_id=1, behavior_id=5, body=request_body)
    return exc.value


def test_update_saves_name_and_code(service, owned):
    result = service.update_behavior(user_id=1, behavior_id=5, body=edit())

    assert (result.name, result.code) == ("nuevo", "go_to(1, 2)")
    owned.name_taken.assert_called_once_with(1, "nuevo", except_id=5)
    owned.update.assert_called_once_with(5, UpdateBehaviorData(name="nuevo", code="go_to(1, 2)"))


def test_update_of_a_missing_behavior_is_not_found_before_the_body(service, repo):
    with pytest.raises(ApiError) as exc:
        service.update_behavior(user_id=1, behavior_id=5, body={})

    assert (exc.value.status_code, exc.value.code) == (404, "notFound")
    repo.update.assert_not_called()


def test_an_invalid_body_is_400_before_the_403(service, repo):
    repo.get_by_id.return_value = behavior(user_id=2)

    with pytest.raises(ValidationApiError):
        service.update_behavior(user_id=1, behavior_id=5, body={})


def test_update_of_another_users_behavior_is_403(service, repo):
    repo.get_by_id.return_value = behavior(user_id=2)

    with pytest.raises(ApiError) as exc:
        service.update_behavior(user_id=1, behavior_id=5, body=edit())

    assert (exc.value.status_code, exc.value.code) == (403, None)
    repo.name_taken.assert_not_called()
    repo.update.assert_not_called()


def test_update_to_a_taken_name_is_duplicate_before_the_code_rules(service, owned):
    owned.name_taken.return_value = True

    error = update_conflict_of(service, edit(code=TOO_LONG + "import os"))

    assert (error.code, error.code_error) == ("duplicateName", None)
    owned.update.assert_not_called()


def test_update_validates_the_code_against_the_stored_type(service, owned):
    owned.get_by_id.return_value = behavior(behavior_type=BehaviorType.coach_behavior)

    error = update_conflict_of(service, edit(code="kick()"))

    assert error.code == "invalidCode"
    assert error.code_error == {"rule": "primitiveNotAllowedForType", "line": 1, "column": 1}
    owned.update.assert_not_called()


def test_update_with_a_code_too_long_is_code_too_long(service, owned):
    error = update_conflict_of(service, edit(code="import os\n" + TOO_LONG))

    assert (error.code, error.code_error) == ("codeTooLong", None)
    owned.update.assert_not_called()


def test_a_behavior_deleted_while_updating_is_deleted_concurrently(service, owned):
    owned.update.side_effect = None
    owned.update.return_value = None

    with pytest.raises(ApiError) as exc:
        service.update_behavior(user_id=1, behavior_id=5, body=edit())

    assert (exc.value.status_code, exc.value.code) == (404, "deletedConcurrently")


def test_a_name_taken_while_updating_is_duplicate_name(service, owned):
    owned.update.side_effect = DuplicateBehaviorNameError()

    assert update_conflict_of(service, edit()).code == "duplicateName"


def test_update_of_a_deleted_behavior_is_deleted_concurrently_before_the_body(service, repo):
    repo.get_by_id.return_value = behavior(deleted=True)

    with pytest.raises(ApiError) as exc:
        service.update_behavior(user_id=1, behavior_id=5, body={})

    assert (exc.value.status_code, exc.value.code) == (404, "deletedConcurrently")
    repo.update.assert_not_called()


# --- delete_behavior ----------------------------------------------------------


def test_get_of_a_deleted_behavior_is_404(service, repo):
    repo.get_by_id.return_value = behavior(deleted=True)

    with pytest.raises(ApiError) as exc:
        service.get_owned_behavior(user_id=1, behavior_id=5)

    assert (exc.value.status_code, exc.value.code) == (404, None)


def test_delete_of_an_unused_behavior_deletes_it(service, repo):
    repo.get_by_id.return_value = behavior(id=5, user_id=1)
    repo.delete_if_unused.return_value = None

    service.delete_behavior(user_id=1, behavior_id=5)

    repo.delete_if_unused.assert_called_once_with(5)


@pytest.mark.parametrize("stored", [None, behavior(deleted=True)])
def test_delete_of_a_missing_or_deleted_behavior_is_404(service, repo, stored):
    repo.get_by_id.return_value = stored

    with pytest.raises(ApiError) as exc:
        service.delete_behavior(user_id=1, behavior_id=5)

    assert (exc.value.status_code, exc.value.code) == (404, None)
    repo.delete_if_unused.assert_not_called()


def test_delete_of_another_users_behavior_is_403(service, repo):
    repo.get_by_id.return_value = behavior(user_id=2)

    with pytest.raises(ApiError) as exc:
        service.delete_behavior(user_id=1, behavior_id=5)

    assert (exc.value.status_code, exc.value.code) == (403, None)
    repo.delete_if_unused.assert_not_called()


@pytest.mark.parametrize(
    "usage, code",
    [
        (BehaviorUsage.league_team, "behaviorInLeagueTeam"),
        (BehaviorUsage.match, "behaviorInMatch"),
    ],
)
def test_delete_of_a_behavior_in_use_is_409_with_the_reason(service, repo, usage, code):
    repo.get_by_id.return_value = behavior(id=5, user_id=1)
    repo.delete_if_unused.return_value = usage

    with pytest.raises(ApiError) as exc:
        service.delete_behavior(user_id=1, behavior_id=5)

    assert (exc.value.status_code, exc.value.code) == (409, code)


# --- deletable ----------------------------------------------------------------


def test_get_behavior_of_an_unused_behavior_is_deletable(service, repo):
    repo.get_by_id.return_value = behavior(id=5, user_id=1, name="mio")

    detail = service.get_behavior(user_id=1, behavior_id=5)

    assert (detail.id, detail.name, detail.deletable) == (5, "mio", True)
    repo.usage.assert_called_once_with(5)


@pytest.mark.parametrize("usage", [BehaviorUsage.league_team, BehaviorUsage.match])
def test_get_behavior_of_a_behavior_in_use_is_not_deletable(service, repo, usage):
    repo.get_by_id.return_value = behavior(id=5, user_id=1)
    repo.usage.return_value = usage

    assert service.get_behavior(user_id=1, behavior_id=5).deletable is False


def test_get_behavior_of_another_users_behavior_is_403(service, repo):
    repo.get_by_id.return_value = behavior(user_id=2)

    with pytest.raises(ApiError) as exc:
        service.get_behavior(user_id=1, behavior_id=5)

    assert exc.value.status_code == 403
    repo.usage.assert_not_called()


def test_update_returns_whether_it_is_deletable(service, owned):
    owned.usage.return_value = BehaviorUsage.league_team

    assert service.update_behavior(user_id=1, behavior_id=5, body=edit()).deletable is False
