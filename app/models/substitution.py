from sqlalchemy import CheckConstraint, DDL, ForeignKey, Integer, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

MAX_SUBSTITUTIONS_PER_TEAM = 3


class Substitution(Base):
    """Un cambio de jugador pedido durante un partido.

    `member_in_id` es el integrante (fila de `team_members`) que entra y
    `member_out_id` el que sale. Los dos tienen que ser del mismo equipo.

    Constraints:
    - Un integrante no puede reemplazarse a sí mismo (CHECK, todos los motores).
    - Las reglas que miran otras tablas no se pueden expresar con un CHECK, así
      que en Postgres las hace cumplir el trigger `substitutions_validate`
      (ver SUBSTITUTION_TRIGGER_SQL), que rechaza el INSERT si:
        * el partido no está `started`;
        * los dos integrantes no son del mismo equipo (mismo usuario y mismo
          dueño: la misma liga o el mismo partido);
        * el equipo no es de ese partido (el usuario no es uno de los dos
          clubes, o el equipo es de otra liga/otro amistoso);
        * el equipo ya hizo MAX_SUBSTITUTIONS_PER_TEAM cambios en el partido.
      El trigger toma un lock sobre el partido, así que dos cambios simultáneos
      del mismo equipo no pueden pasarse del límite.
    """

    __tablename__ = "substitutions"
    __table_args__ = (
        CheckConstraint(
            "member_in_id <> member_out_id",
            name="ck_substitutions_distinct_members",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_in_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_out_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )


SUBSTITUTION_TRIGGER_SQL = f"""
CREATE OR REPLACE FUNCTION validate_substitution() RETURNS trigger AS $$
DECLARE
    m matches%%ROWTYPE;
    t_in team_members%%ROWTYPE;
    t_out team_members%%ROWTYPE;
    used integer;
BEGIN
    -- El lock serializa los cambios de un mismo partido (límite de cambios).
    SELECT * INTO m FROM matches WHERE id = NEW.match_id FOR UPDATE;
    SELECT * INTO t_in FROM team_members WHERE id = NEW.member_in_id;
    SELECT * INTO t_out FROM team_members WHERE id = NEW.member_out_id;

    IF m.status <> 'started' THEN
        RAISE EXCEPTION 'substitution: el partido no está en juego'
            USING ERRCODE = '23514';
    END IF;

    IF t_in.user_id <> t_out.user_id
       OR t_in.league_id IS DISTINCT FROM t_out.league_id
       OR t_in.match_id IS DISTINCT FROM t_out.match_id THEN
        RAISE EXCEPTION 'substitution: los integrantes no son del mismo equipo'
            USING ERRCODE = '23514';
    END IF;

    IF t_in.user_id IS DISTINCT FROM m.user_1_id
       AND t_in.user_id IS DISTINCT FROM m.user_2_id THEN
        RAISE EXCEPTION 'substitution: el equipo no es del partido'
            USING ERRCODE = '23514';
    END IF;

    IF m.league_id IS NULL THEN
        IF t_in.match_id IS DISTINCT FROM m.id THEN
            RAISE EXCEPTION 'substitution: el equipo no es del partido'
                USING ERRCODE = '23514';
        END IF;
    ELSIF t_in.league_id IS DISTINCT FROM m.league_id THEN
        RAISE EXCEPTION 'substitution: el equipo no es del partido'
            USING ERRCODE = '23514';
    END IF;

    SELECT count(*) INTO used
    FROM substitutions s
    JOIN team_members t ON t.id = s.member_out_id
    WHERE s.match_id = NEW.match_id AND t.user_id = t_in.user_id;

    IF used >= {MAX_SUBSTITUTIONS_PER_TEAM} THEN
        RAISE EXCEPTION 'substitution: el equipo ya hizo {MAX_SUBSTITUTIONS_PER_TEAM} cambios'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

_CREATE_TRIGGER = """
CREATE TRIGGER substitutions_validate
BEFORE INSERT ON substitutions
FOR EACH ROW EXECUTE FUNCTION validate_substitution()
"""

_postgres = {"dialect": "postgresql"}
event.listen(
    Substitution.__table__,
    "after_create",
    DDL(SUBSTITUTION_TRIGGER_SQL).execute_if(**_postgres),
)
event.listen(
    Substitution.__table__,
    "after_create",
    DDL(_CREATE_TRIGGER).execute_if(**_postgres),
)
event.listen(
    Substitution.__table__,
    "after_drop",
    DDL("DROP FUNCTION IF EXISTS validate_substitution()").execute_if(**_postgres),
)