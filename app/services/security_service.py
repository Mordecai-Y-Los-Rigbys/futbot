import base64
import hashlib

import bcrypt


def _prepare(plain_password: str) -> bytes:
    """
    Convierte la contraseña en una entrada segura para bcrypt.

    bcrypt acepta como máximo 72 BYTES, pero el contrato limita a 72 CARACTERES
    (un "ñ" son 2 bytes y un emoji, 4). SHA-256 + base64 da siempre 44 bytes,
    sin bytes nulos, así que cualquier contraseña válida entra.
    """
    digest: bytes = hashlib.sha256(plain_password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain_password: str) -> str:
    """Hashea una contraseña en texto plano usando bcrypt con un salt generado."""
    salt: bytes = bcrypt.gensalt()
    hashed: bytes = bcrypt.hashpw(_prepare(plain_password), salt)

    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña en texto plano contra un hash bcrypt existente."""
    return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("utf-8"))
