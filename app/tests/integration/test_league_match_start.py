import asyncio
import random
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.domain.behavior import BehaviorType
from app.domain.match import MatchStatus
from app.domain.team_member import MemberRole
from app.models.behavior import Behavior
from app.models.match import Match
from app.models.player import Player
from app.models.team_member import TeamMember
from app.repositories.league_match_start_sqlalchemy import SqlAlchemyLeagueMatchStartRepository
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository
from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository
from app.services.league_fixture import build_fixture, match_slot
from app.services.league_match_start import LeagueMatchStartService
from app.services.match_runner import MatchRunner
from app.services.match_setup_service import MatchSetupService

pytestmark = pytest.mark.integration

ROLES = [MemberRole.forward, MemberRole.midfield, MemberRole.defense] + [MemberRole.substitute] * 3


@pytest.fixture()
def factory(db_session):
    """Sesiones nuevas contra la base de test: el service y el runner abren las suyas."""
    return sessionmaker(bind=db_session.get_bind())


@pytest.fixture()
def add_team(db_session):
    """Inscribe el equipo de liga de un usuario: 3 titulares y 3 suplentes."""

    def _add(league, user):
        behavior = Behavior(
            user_id=user.id, name=f"b{user.id}", code="pass", type=BehaviorType.player_behavior
        )
        players = [
            Player(
                user_id=user.id,
                name=f"J{i}",
                power=60,
                agility=60,
                control=60,
                strength=60,
                speed=60,
            )
            for i in range(6)
        ]
        db_session.add_all([behavior, *players])
        db_session.flush()
        db_session.add_all(
            TeamMember(
                league_id=league.id,
                user_id=user.id,
                player_id=p.id,
                behavior_id=behavior.id,
                role=r,
            )
            for p, r in zip(players, ROLES)
        )
        db_session.commit()
        return players

    return _add


@pytest.fixture()
def creator(create_user):
    return create_user("creator")


@pytest.fixture()
def started_league(db_session, creator, make_league, create_user, add_participant, add_team):
    """Liga de 1 minuto por partido, iniciada, con 3 participantes y sus equipos."""
    league = make_league(creator)
    league.match_duration = 1
    db_session.commit()
    add_team(league, creator)
    for name in ("p2", "p3"):
        user = create_user(name)
        add_participant(league, user)
        add_team(league, user)
    now = datetime.now(timezone.utc)
    SqlAlchemyLeagueRepository(db_session).start(
        league.id,
        lambda ids: build_fixture(ids, now, match_slot(1, True), random.Random(1)),
    )
    return league


def matches_of(db_session, league_id) -> list[Match]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Match).where(Match.league_id == league_id).order_by(Match.scheduled_at)
        )
    )


def reschedule(db_session, match_id, when):
    db_session.execute(update(Match).where(Match.id == match_id).values(scheduled_at=when))
    db_session.commit()


def test_repo_lists_the_scheduled_matches_of_each_league(
    db_session, started_league, creator, create_user, make_league
):
    repo = SqlAlchemyLeagueMatchStartRepository(db_session)
    first, *rest = matches_of(db_session, started_league.id)
    other_league = make_league(creator, "Otra")
    db_session.add(Match(user_1_id=creator.id, user_2_id=create_user("rival").id))  # amistoso
    db_session.execute(update(Match).where(Match.id == first.id).values(status=MatchStatus.started))
    db_session.commit()

    pending = repo.list_pending_start(started_league.id)
    assert [p.match_id for p in pending] == [m.id for m in rest]
    assert [p.scheduled_at for p in pending] == [m.scheduled_at for m in rest]
    assert repo.list_pending_start(other_league.id) == []
    assert [p.match_id for p in repo.list_pending_start()] == [m.id for m in rest]


def test_repo_is_ready_only_for_a_scheduled_league_match(
    db_session, started_league, creator, create_user
):
    repo = SqlAlchemyLeagueMatchStartRepository(db_session)
    first, second, _ = matches_of(db_session, started_league.id)
    friendly = Match(user_1_id=creator.id, user_2_id=create_user("rival").id)
    db_session.add(friendly)
    db_session.execute(
        update(Match).where(Match.id == second.id).values(status=MatchStatus.started)
    )
    db_session.commit()

    assert repo.is_ready_to_start(first.id) is True
    assert repo.is_ready_to_start(second.id) is False
    assert repo.is_ready_to_start(friendly.id) is False
    assert repo.is_ready_to_start(999999) is False
    assert matches_of(db_session, started_league.id)[0].status == MatchStatus.scheduled


class SilentManager:
    def subscribers(self, match_id):
        return []

    def evict(self, match_id, user_id, websocket):
        pass

    async def close_match(self, match_id, code=1000, reason=""):
        pass


def test_a_scheduled_match_starts_on_time_with_the_current_team_and_saves_the_result(
    db_session, factory, started_league
):
    match = matches_of(db_session, started_league.id)[0]

    # Cambio de alineación después de iniciar la liga: el partido usa la vigente.
    starter = db_session.scalar(
        select(TeamMember).where(
            TeamMember.league_id == started_league.id,
            TeamMember.user_id == match.user_1_id,
            TeamMember.role == MemberRole.forward,
        )
    )
    substitute = db_session.scalar(
        select(TeamMember).where(
            TeamMember.league_id == started_league.id,
            TeamMember.user_id == match.user_1_id,
            TeamMember.role == MemberRole.substitute,
        )
    )
    starter.role, substitute.role = MemberRole.substitute, MemberRole.forward
    db_session.commit()
    current_forward = substitute.player_id

    @contextmanager
    def scope(repo_class):
        with factory() as session:
            yield repo_class(session)

    setups, started_at = [], []

    def load_setup(match_id):
        started_at.append(datetime.now(timezone.utc))
        with factory() as session:
            setup = MatchSetupService(
                SqlAlchemyMatchRepository(session),
                SqlAlchemyLeagueRepository(session),
                SqlAlchemyTeamRepository(session),
            ).load_match_setup(match_id)
        setups.append(setup)
        return setup

    async def no_sleep(_):
        pass

    runner = MatchRunner(
        SilentManager(),
        load_setup,
        lambda: scope(SqlAlchemyMatchRepository),
        lambda: scope(SqlAlchemySubstitutionRepository),
        sleep=no_sleep,
    )
    played = []

    async def on_start(match_id):
        played.append(runner.start(match_id))

    service = LeagueMatchStartService(lambda: scope(SqlAlchemyLeagueMatchStartRepository), on_start)

    async def scenario():
        when = datetime.now(timezone.utc) + timedelta(milliseconds=300)
        reschedule(db_session, match.id, when)
        await service.schedule_league(started_league.id)
        await asyncio.sleep(0.1)
        before = list(played)
        await asyncio.sleep(0.4)
        await asyncio.gather(*played)
        return when, before

    when, before = asyncio.run(scenario())

    assert before == []  # todavía no era la hora
    assert len(played) == 1 and started_at[0] >= when
    forwards = [p.player_id for p in setups[0].team_1.players if p.role == MemberRole.forward]
    assert forwards == [current_forward]
    db_session.expire_all()
    finished = db_session.get(Match, match.id)
    assert finished.status == MatchStatus.finished
    assert finished.score_1 is not None and finished.score_2 is not None
