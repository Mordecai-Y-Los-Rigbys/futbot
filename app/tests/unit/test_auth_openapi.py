"""
Test unitario de la documentación OpenAPI de auth: no usa base de datos ni
el fixture `client`.
"""


def test_auth_400s_are_documented_with_validation_bad_request():
    from app.main import app

    spec = app.openapi()
    for path in ("/auth/register", "/auth/log-in"):
        response = spec["paths"][path]["post"]["responses"]["400"]
        schema = response["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/ValidationBadRequest")

    schemas = spec["components"]["schemas"]
    for old in ("RegisterUserBadRequest", "RegisterUserFieldError", "LogInBadRequest", "LogInFieldError"):
        assert old not in schemas
