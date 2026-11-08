from http.cookies import SimpleCookie
from unittest.mock import create_autospec

from app.api.auth import user_logout
from app.api.deps import CurrentSession
from app.services.session_service import SessionService


def test_logout_deletes_current_session_and_expires_cookie():
    service = create_autospec(SessionService, instance=True)
    session = CurrentSession(id="sesion-actual", user_id=7)

    response = user_logout(session=session, service=service)

    service.delete.assert_called_once_with("sesion-actual")
    assert response.status_code == 204
    assert response.body == b""

    cookie = SimpleCookie(response.headers["set-cookie"])["session_id"]
    assert cookie.value == ""
    assert cookie["max-age"] == "0"
    assert cookie["httponly"]
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"