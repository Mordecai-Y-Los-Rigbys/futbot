"""Ligas y equipos de 6 jugadores para los tests de integración de partidos."""

from app.models.league import League, LeagueStatus
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember

ROLES = [MemberRole.forward, MemberRole.midfield, MemberRole.defense] + [MemberRole.substitute] * 3


def add_team(db, user_id, behavior, **owner):
    """Crea 6 jugadores y su equipo en `owner` (league_id=... o match_id=...)."""
    players = [
        Player(
            user_id=user_id,
            name=f"p{user_id}{i}",
            power=60,
            agility=60,
            control=60,
            strength=60,
            speed=60,
        )
        for i in range(6)
    ]
    db.add_all(players)
    db.commit()
    members = [
        TeamMember(user_id=user_id, player_id=p.id, behavior_id=behavior.id, role=role, **owner)
        for p, role in zip(players, ROLES)
    ]
    db.add_all(members)
    db.commit()
    return members


def add_league(db, name="L"):
    league = League(
        name=name,
        creator_id=1,
        status=LeagueStatus.started,
        min_participants=3,
        max_participants=8,
        match_duration=2,
        private=False,
    )
    db.add(league)
    db.flush()
    return league
