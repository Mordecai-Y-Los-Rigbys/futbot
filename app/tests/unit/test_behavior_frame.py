import pytest

from app.simulation.behaviors.frame import direction_to_absolute, to_absolute, to_relative
from app.simulation.constants import FIELD_LENGTH, FIELD_WIDTH
from app.simulation.geometry import Vec
from app.simulation.state import Team

HOME, AWAY = Team.HOME, Team.AWAY


def test_home_sees_absolute_coordinates():
    assert to_relative(HOME, Vec(10.0, 20.0)) == (10.0, 20.0)
    assert to_absolute(HOME, 10.0, 20.0) == Vec(10.0, 20.0)


def test_away_sees_the_field_rotated():
    assert to_relative(AWAY, Vec(10.0, 20.0)) == (FIELD_LENGTH - 10.0, FIELD_WIDTH - 20.0)
    assert to_absolute(AWAY, 10.0, 20.0) == Vec(FIELD_LENGTH - 10.0, FIELD_WIDTH - 20.0)


@pytest.mark.parametrize("team", [HOME, AWAY])
def test_each_team_sees_its_own_goal_at_x_zero(team):
    own_goal = Vec(0.0, FIELD_WIDTH / 2) if team is HOME else Vec(FIELD_LENGTH, FIELD_WIDTH / 2)
    assert to_relative(team, own_goal) == (0.0, FIELD_WIDTH / 2)


@pytest.mark.parametrize("team", [HOME, AWAY])
def test_going_relative_and_back_gives_the_same_point(team):
    point = Vec(37.5, 12.25)
    assert to_absolute(team, *to_relative(team, point)) == point


def test_directions_are_inverted_for_away():
    assert direction_to_absolute(HOME, 1.0, 0.5) == (1.0, 0.5)
    assert direction_to_absolute(AWAY, 1.0, 0.5) == (-1.0, -0.5)
