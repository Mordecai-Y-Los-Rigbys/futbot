from sqlalchemy.orm import configure_mappers

from app import models  # noqa: F401  (registra todos los modelos)


def test_mappers_configure_without_ambiguity():
    # Match tiene dos FK a users: una relación sin foreign_keys explícito rompe acá.
    configure_mappers()
