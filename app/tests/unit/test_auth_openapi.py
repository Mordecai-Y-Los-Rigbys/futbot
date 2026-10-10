"""
Test unitario de la documentación OpenAPI de auth: no usa base de datos ni
el fixture `client`.
"""
 
 
def test_openapi_documents_the_auth_error_schemas():
    from app.main import app
 
    schemas = app.openapi()["components"]["schemas"]
    assert "RegisterUserBadRequest" in schemas
    assert "RegisterUserFieldError" in schemas
    assert "LogInBadRequest" in schemas
    assert "LogInFieldError" in schemas