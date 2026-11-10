import copy

MISSING = object()

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]
TEAM = [{"playerId": i + 1, "role": r, "behaviorId": 1} for i, r in enumerate(ROLES)]


def team(index=None, **changes):
    """TEAM con el miembro `index` modificado (MISSING borra la clave)."""
    out = copy.deepcopy(TEAM)
    if index is not None:
        for key, value in changes.items():
            if value is MISSING:
                out[index].pop(key)
            else:
                out[index][key] = value
    return out


def err(field, reason):
    return {"field": field, "reason": reason}


# (id, valor de `members` o MISSING, errors)
MEMBERS_CASES = [
    ("members_missing", MISSING, [err("members", "required")]),
    ("members_null", None, [err("members", "invalidType")]),
    ("members_string", "x", [err("members", "invalidType")]),
    ("members_object", {}, [err("members", "invalidType")]),
    ("member_not_object", TEAM[:5] + ["x"], [err("members[5]", "invalidType")]),
    ("playerId_missing", team(0, playerId=MISSING), [err("members[0].playerId", "required")]),
    ("playerId_string", team(0, playerId="abc"), [err("members[0].playerId", "invalidType")]),
    ("playerId_float", team(0, playerId=1.5), [err("members[0].playerId", "invalidType")]),
    ("playerId_bool", team(0, playerId=True), [err("members[0].playerId", "invalidType")]),
    ("playerId_null", team(0, playerId=None), [err("members[0].playerId", "invalidType")]),
    ("playerId_zero", team(0, playerId=0), [err("members[0].playerId", "outOfRange")]),
    ("playerId_too_big", team(0, playerId=2147483648), [err("members[0].playerId", "outOfRange")]),
    ("role_missing", team(2, role=MISSING), [err("members[2].role", "required")]),
    ("role_int", team(2, role=5), [err("members[2].role", "invalidType")]),
    ("role_null", team(2, role=None), [err("members[2].role", "invalidType")]),
    ("behaviorId_missing", team(1, behaviorId=MISSING), [err("members[1].behaviorId", "required")]),
    ("behaviorId_string", team(1, behaviorId="1"), [err("members[1].behaviorId", "invalidType")]),
    ("behaviorId_negative", team(1, behaviorId=-1), [err("members[1].behaviorId", "outOfRange")]),
    (
        "behaviorId_too_big",
        team(1, behaviorId=2147483648),
        [err("members[1].behaviorId", "outOfRange")],
    ),
    ("team_empty", [], [err("members", "invalidTeam")]),
    ("team_five", TEAM[:5], [err("members", "invalidTeam")]),
    (
        "team_seven",
        TEAM + [{"playerId": 7, "role": "substitute", "behaviorId": 1}],
        [err("members", "invalidTeam")],
    ),
    ("role_unknown", team(0, role="goalkeeper"), [err("members", "invalidTeam")]),
    ("role_uppercase", team(0, role="FORWARD"), [err("members", "invalidTeam")]),
    ("two_forwards", team(5, role="forward"), [err("members", "invalidTeam")]),
    ("repeated_player", team(1, playerId=1), [err("members", "invalidTeam")]),
    (
        "several_members_in_order",
        [
            {"playerId": "x", "behaviorId": 0},
            "x",
            {"playerId": 3, "role": 1, "behaviorId": "y"},
        ],
        [
            err("members[0].playerId", "invalidType"),
            err("members[0].role", "required"),
            err("members[0].behaviorId", "outOfRange"),
            err("members[1]", "invalidType"),
            err("members[2].role", "invalidType"),
            err("members[2].behaviorId", "invalidType"),
        ],
    ),
    (
        "field_errors_skip_invalid_team",
        TEAM[:4] + [{"playerId": "x", "role": "substitute", "behaviorId": 1}],
        [err("members[4].playerId", "invalidType")],
    ),
]

MEMBERS_IDS = [c[0] for c in MEMBERS_CASES]
MEMBERS_PARAMS = [c[1:] for c in MEMBERS_CASES]
