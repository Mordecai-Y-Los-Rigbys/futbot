from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """
    Base de los schemas de la API: atributos en snake_case en Python,
    claves en camelCase en el JSON (como pide el spec).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # permite construirlos con snake_case
        from_attributes=True,
    )