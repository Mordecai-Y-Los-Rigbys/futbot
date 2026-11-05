import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.errors import validation_exception_handler


class Member(BaseModel):
    playerId: int


class Body(BaseModel):
    name: str = Field(max_length=5)
    members: list[Member]


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.post("/otro")
    def otro(body: Body, page: int = 1):
        return {"ok": True}

    return TestClient(app)


def errors_of(resp):
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalidFields"
    assert resp.json()["message"]
    return resp.json()["errors"]


def test_each_failing_field_is_reported_with_its_path(client):
    resp = client.post("/otro", json={"name": "x" * 6, "members": [{"playerId": "x"}]})
    assert errors_of(resp) == [
        {"field": "name", "reason": "tooLong"},
        {"field": "members[0].playerId", "reason": "invalidType"},
    ]


def test_missing_field_is_required(client):
    resp = client.post("/otro", json={"members": []})
    assert errors_of(resp) == [{"field": "name", "reason": "required"}]


def test_query_param_uses_its_name(client):
    resp = client.post("/otro?page=abc", json={"name": "a", "members": []})
    assert errors_of(resp) == [{"field": "page", "reason": "invalidType"}]


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"content": "{", "headers": {"Content-Type": "application/json"}}, {"json": [1]}],
)
def test_unreadable_body_falls_back_to_body_required(client, kwargs):
    assert errors_of(client.post("/otro", **kwargs)) == [{"field": "body", "reason": "required"}]
