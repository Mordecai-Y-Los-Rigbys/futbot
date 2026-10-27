from itertools import product
from unittest.mock import Mock, patch

import pytest

from app.errors import ApiError
from app.repositories.league_access_abstract import LeagueAccessInfo
from app.services.league_access_service import (
    LeagueAccessService, has_league_access, verify_league_password,
)


@pytest.mark.parametrize("private,creator,participant,unlocked", list(product([False, True], repeat=4)))
def test_access_matrix(private, creator, participant, unlocked):
    repo = Mock()
    repo.is_participant.return_value = participant
    repo.is_unlocked.return_value = unlocked
    league = LeagueAccessInfo(5, 7 if creator else 99, private, "secret")
    assert has_league_access("sid", 7, league, repo) == (
        not private or creator or participant or unlocked
    )
    repo.unlock.assert_not_called()


def test_require_access_returns_expected_403():
    repo = Mock()
    repo.is_participant.return_value = False
    repo.is_unlocked.return_value = False
    with pytest.raises(ApiError) as exc:
        LeagueAccessService(repo).require_access("sid", 7, LeagueAccessInfo(5, 99, True, "secret"))
    assert (exc.value.status_code, exc.value.code) == (403, "leagueAccessRequired")


@pytest.mark.parametrize("password", ["secret", "ñ🔐", "a" * 72])
def test_constant_time_comparison_of_fixed_length_digests(password):
    import hmac
    with patch("app.services.league_access_service.hmac.compare_digest", wraps=hmac.compare_digest) as compare:
        assert verify_league_password(password, password)
        assert not verify_league_password(password + "x", password)
        assert all(len(arg) == 32 for call in compare.call_args_list for arg in call.args)


def test_password_is_not_in_info_repr():
    assert "secret" not in repr(LeagueAccessInfo(5, 99, True, "secret"))
