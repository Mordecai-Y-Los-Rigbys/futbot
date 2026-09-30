import bcrypt


def hash_password(plain_password: str) -> str:
    """Hashea un password en texto plano usando bycrypt con un salt generado"""
    password_bytes: bytes = plain_password.encode("utf-8")
    salt: bytes = bcrypt.gensalt()
    hashed: bytes = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña en texto plano contra un hash bcrypt existente"""
    password_bytes: bytes = plain_password.encode("utf-8")
    hash_bytes: bytes = hashed_password.encode("utf-8")

    return bcrypt.checkpw(password_bytes, hash_bytes)
    