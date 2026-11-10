from typing import Any

from app.domain.behavior import BehaviorType, BehaviorUsage
from app.errors import ApiError, BehaviorConflictError
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    BehaviorNotFoundError,
    CreateBehaviorData,
    DuplicateBehaviorNameError,
)
from app.services.behavior_validation import parse_create_behavior, parse_update_behavior
from app.simulation.behaviors.default_behaviors import DEFAULT_BEHAVIORS
from app.simulation.behaviors.validation import (
    MAX_CODE_CHARS,
    MAX_CODE_LINES,
    find_code_violation,
    is_code_too_long,
)

PAGE_SIZE = 50
BEHAVIOR_NOT_FOUND_MESSAGE = "Comportamiento no encontrado."
NOT_OWNER_MESSAGE = "El comportamiento no pertenece al usuario."
IN_USE_MESSAGES = {
    BehaviorUsage.league_team: "El comportamiento está asignado a un equipo inscripto en una liga.",
    BehaviorUsage.match: "El comportamiento está en uso en un amistoso que no terminó.",
}


class BehaviorService:
    """Casos de uso de los behaviors de un usuario: listar, ver y crear."""

    def __init__(self, repository: AbstractBehaviorRepository) -> None:
        self.repository = repository

    def list_behaviors(
        self, user_id: int, name: str | None, page: int
    ) -> tuple[list[BehaviorData], int]:
        """
        Devuelve (items de la página, total que matchea el filtro).
        Siempre filtra por user_id; name es un contains case-insensitive opcional.
        """
        offset = (page - 1) * PAGE_SIZE
        return self.repository.list_by_user(
            user_id=user_id, name=name, offset=offset, limit=PAGE_SIZE
        )

    def get_owned_behavior(self, user_id: int, behavior_id: int) -> BehaviorData:
        """404 si no existe o está eliminado, 403 si es de otro usuario. Solo lectura."""
        behavior = self.repository.get_by_id(behavior_id)
        if behavior is None or behavior.deleted:
            raise ApiError(404, None, BEHAVIOR_NOT_FOUND_MESSAGE)
        if behavior.user_id != user_id:
            raise ApiError(403, None, NOT_OWNER_MESSAGE)
        return behavior

    def create_default_behaviors(self, user_id: int) -> list[BehaviorData]:
        """Crea para el usuario una copia propia de los behaviors iniciales."""
        return self.repository.create_many(
            user_id, [CreateBehaviorData(**b) for b in DEFAULT_BEHAVIORS]
        )

    def create_behavior(self, user_id: int, body: Any) -> BehaviorData:
        """Crea un behavior del usuario.

        Raises:
            ValidationApiError 400: el body no cumple el contrato.
            BehaviorConflictError 409: duplicateName, codeTooLong o invalidCode,
                el primero que falla en ese orden.
        """
        data = parse_create_behavior(body)
        if self.repository.name_taken(user_id, data.name):
            raise _duplicate_name()
        _ensure_valid_code(data.code, data.type)
        try:
            return self.repository.create(user_id, data)
        except DuplicateBehaviorNameError:
            raise _duplicate_name()

    def update_behavior(self, user_id: int, behavior_id: int, body: Any) -> BehaviorData:
        """Cambia nombre y código de un behavior del usuario. El tipo no cambia.

        Raises:
            ApiError 404: notFound si no existe; deletedConcurrently si se eliminó
                mientras se procesaba el cambio.
            ValidationApiError 400: el body no cumple el contrato.
            ApiError 403: el behavior es de otro usuario.
            BehaviorConflictError 409: duplicateName, codeTooLong o invalidCode,
                el primero que falla en ese orden.
        """
        behavior = self.repository.get_by_id(behavior_id)
        if behavior is None:
            raise ApiError(404, "notFound", BEHAVIOR_NOT_FOUND_MESSAGE)
        if behavior.deleted:
            raise _deleted_concurrently()
        data = parse_update_behavior(body)
        if behavior.user_id != user_id:
            raise ApiError(403, None, NOT_OWNER_MESSAGE)
        if self.repository.name_taken(user_id, data.name, except_id=behavior_id):
            raise _duplicate_name()
        _ensure_valid_code(data.code, behavior.type)
        try:
            updated = self.repository.update(behavior_id, data)
        except DuplicateBehaviorNameError:
            raise _duplicate_name()
        if updated is None:
            raise _deleted_concurrently()
        return updated

    def delete_behavior(self, user_id: int, behavior_id: int) -> None:
        """Elimina (borrado lógico) un behavior del usuario que no está en uso.

        Raises:
            ApiError 404: no existe o ya está eliminado.
            ApiError 403: es de otro usuario.
            ApiError 409: behaviorInLeagueTeam o behaviorInMatch, si está en uso.
        """
        self.get_owned_behavior(user_id, behavior_id)
        try:
            usage = self.repository.delete_if_unused(behavior_id)
        except BehaviorNotFoundError:
            # Otro DELETE lo eliminó después de que lo leímos.
            raise ApiError(404, None, BEHAVIOR_NOT_FOUND_MESSAGE)
        if usage is not None:
            raise ApiError(409, usage.value, IN_USE_MESSAGES[usage])


def _deleted_concurrently() -> ApiError:
    return ApiError(404, "deletedConcurrently", "El comportamiento se eliminó.")


def _duplicate_name() -> BehaviorConflictError:
    return BehaviorConflictError("duplicateName", "Ya tenés un comportamiento con ese nombre.")


def _ensure_valid_code(code: str, behavior_type: BehaviorType) -> None:
    """codeTooLong antes que invalidCode, como pide el contrato."""
    if is_code_too_long(code):
        raise BehaviorConflictError(
            "codeTooLong",
            f"El código supera las {MAX_CODE_LINES} líneas o los {MAX_CODE_CHARS} caracteres.",
        )
    violation = find_code_violation(code, behavior_type)
    if violation:
        raise BehaviorConflictError(
            "invalidCode",
            violation.message,
            {"rule": violation.rule.value, "line": violation.line, "column": violation.column},
        )
