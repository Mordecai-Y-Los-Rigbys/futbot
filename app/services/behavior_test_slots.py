from app.errors import ApiError


class BehaviorTestSlots:
    """Pruebas abiertas en este proceso: una por usuario.

    reserve() y release() son síncronos, así que en un único event loop dos
    handshakes simultáneos no pueden pasarse el límite. Como en
    MatchConnectionManager, con varios workers de uvicorn cada uno tiene el suyo.
    """

    def __init__(self) -> None:
        self._users: set[int] = set()

    def reserve(self, user_id: int) -> None:
        """Toma el cupo del usuario. Va antes del accept.

        Raises:
            ApiError 429: tooManyConnections, si ya tiene una prueba abierta.
        """
        if user_id in self._users:
            raise ApiError(429, "tooManyConnections", "Ya tenés una prueba abierta.")
        self._users.add(user_id)

    def release(self, user_id: int) -> None:
        """Libera el cupo. Lo llama siempre el endpoint al cerrar."""
        self._users.discard(user_id)

    def is_open(self, user_id: int) -> bool:
        return user_id in self._users
