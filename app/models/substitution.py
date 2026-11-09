from sqlalchemy import CheckConstraint, DDL, ForeignKey, Integer, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Substitution(Base):
    """La sustitución PENDIENTE: la que un equipo pidió para la próxima pausa.

    Cada equipo (usuario) tiene como máximo UNA por partido: pedir otra antes
    de la pausa reemplaza a la anterior. Al empezar la pausa se aplica: se
    intercambian los roles en `team_members`, pasa a `applied_substitutions` y esta
    fila se borra (un pedido hecho durante la pausa queda pendiente para la siguiente).
    La PK (match_id, user_id) hace cumplir "una por equipo y partido".

    `member_in_id` es el integrante (fila de `team_members`) que entra y
    `member_out_id` el que sale. Los dos tienen que ser del equipo `user_id`.

    Constraints:
    - Un integrante no puede reemplazarse a sí mismo (CHECK, todos los motores).
    - Las reglas que miran otras tablas las hace cumplir en Postgres el trigger
      `substitutions_validate` (ver SUBSTITUTION_TRIGGER_SQL), que rechaza el
      INSERT/UPDATE si:
        * el partido no está `started`;
        * los dos integrantes no son del mismo equipo (mismo usuario y mismo
          dueño: la misma liga o el mismo partido);
        * `user_id` no es el dueño de los integrantes;
        * el equipo no es de ese partido (el usuario no es uno de los dos
          clubes, o el equipo es de otra liga/otro amistoso);
        * los roles no corresponden a una pendiente: el que entra tiene que
          ser `substitute` y el que sale, titular.
    """

    __tablename__ = "substitutions"
    __table_args__ = (
        CheckConstraint(
            "member_in_id <> member_out_id",
            name="ck_substitutions_distinct_members",
        ),
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    member_in_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_out_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )


class AppliedSubstitution(Base):
    """La sustitución APLICADA al empezar la última pausa de un partido.

    Es lo que GET /matches/{id}/substitutions muestra mientras dura la pausa.
    Al empezar la pausa siguiente se reemplaza por completo (un equipo sin
    cambio pendiente queda sin fila). No necesita trigger: solo la escribe el
    runner, copiando una `Substitution` ya validada.
    """

    __tablename__ = "applied_substitutions"
    __table_args__ = (
        CheckConstraint(
            "member_in_id <> member_out_id",
            name="ck_applied_substitutions_distinct_members",
        ),
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    member_in_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_out_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )


# Ya no hay que contar cambios, así que no hace falta interpolar nada.
# %% porque DDL() formatea con %.
SUBSTITUTION_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION validate_substitution() RETURNS trigger AS $$
DECLARE
    m matches%%ROWTYPE;
    t_in team_members%%ROWTYPE;
    t_out team_members%%ROWTYPE;
BEGIN
    -- El lock serializa los cambios de un mismo partido (también apply_pending).
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

    IF NEW.user_id <> t_in.user_id THEN
        RAISE EXCEPTION 'substitution: los integrantes no son del equipo indicado'
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

    IF t_in.role <> 'substitute' OR t_out.role = 'substitute' THEN
        RAISE EXCEPTION 'substitution: los roles no corresponden a una sustitución pendiente'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

_CREATE_TRIGGER = """
CREATE TRIGGER substitutions_validate
BEFORE INSERT OR UPDATE ON substitutions
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
