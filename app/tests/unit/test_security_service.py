import pytest

from app.services.security_service import hash_password, verify_password


@pytest.mark.parametrize("password", ["a" * 72, "ñ" * 72, "😀" * 72, "áéíóú" * 14])
def test_passwords_up_to_72_chars_roundtrip_regardless_of_bytes(password):
    assert len(password) <= 72
    assert verify_password(password, hash_password(password))


def test_wrong_password_does_not_verify():
    assert not verify_password("ñ" * 71, hash_password("ñ" * 72))


def test_passwords_sharing_the_first_72_bytes_are_not_equivalent():
    # Con "ñ" * 36 y "ñ" * 72 los primeros 72 bytes son iguales: no deben confundirse
    assert not verify_password("ñ" * 72, hash_password("ñ" * 36))


def test_hash_is_not_the_plain_password():
    assert hash_password("Password123!") != "Password123!"
