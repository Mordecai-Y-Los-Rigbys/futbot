import pytest

from app.errors import ApiError


# ---------- service ----------

def test_get_league_devuelve_el_detalle(service, fake_repo, make_detail):
    fake_repo.details[5] = make_detail(
        id=5, participants_count=4, min_participants=3, joined=True, private=True
    )

    result = service.get_league(league_id=5, user_id=7)

    assert result.id == 5
    assert result.participants_count == 4
    assert result.min_participants == 3
    assert result.joined is True
    assert result.private is True
    assert result.creator.avatar == 1
    assert fake_repo.detail_calls == [(5, 7)]


def test_get_league_inexistente_lanza_404(service):
    with pytest.raises(ApiError) as exc:
        service.get_league(league_id=99, user_id=7)

    assert exc.value.status_code == 404
    assert exc.value.code is None


# ---------- endpoint ----------

def test_sin_sesion_devuelve_401_con_cualquier_id(api, fake_repo, make_detail):
    fake_repo.details[1] = make_detail(id=1)

    for league_id in ("1", "abc", "0", "99"):
        response = api.get(f"/leagues/{league_id}")
        assert response.status_code == 401
        assert response.json()["code"] is None


def test_200_con_el_detalle_completo(auth_api, fake_repo, make_detail):
    fake_repo.details[1] = make_detail(
        id=1, private=True, allow_draws=False, min_participants=3, joined=False
    )

    response = auth_api.get("/leagues/1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["private"] is True
    assert body["allowDraws"] is False
    assert body["minParticipants"] == 3
    assert body["participantsCount"] == 1
    assert body["joined"] is False
    assert set(body["creator"]) == {"id", "username", "name", "avatar"}
    assert body["creator"]["name"] == "Boca Juniors FC"
    assert body["createdAt"] == "2026-01-01T00:00:00Z"


def test_liga_privada_sin_acceso_devuelve_200(auth_api, fake_repo, make_detail):
    fake_repo.details[1] = make_detail(id=1, private=True, joined=False)

    response = auth_api.get("/leagues/1")

    assert response.status_code == 200
    assert response.json()["private"] is True
    assert response.json()["joined"] is False


@pytest.mark.parametrize("status", ["preparation", "started", "cancelled", "finished"])
def test_se_pueden_leer_ligas_en_cualquier_estado(auth_api, fake_repo, make_detail, status):
    fake_repo.details[1] = make_detail(id=1, status=status)

    response = auth_api.get("/leagues/1")

    assert response.status_code == 200
    assert response.json()["status"] == status


@pytest.mark.parametrize("league_id", ["abc", "0", "-1", "2147483648", "1.5", "99"])
def test_id_invalido_o_inexistente_devuelve_404(auth_api, fake_repo, make_detail, league_id):
    fake_repo.details[1] = make_detail(id=1)

    response = auth_api.get(f"/leagues/{league_id}")

    assert response.status_code == 404
    assert response.json()["code"] is None


def test_la_respuesta_no_incluye_la_contrasena(auth_api, fake_repo, make_detail):
    fake_repo.details[1] = make_detail(id=1, private=True)

    body = auth_api.get("/leagues/1").json()

    assert "password" not in body
    assert "password" not in body["creator"]