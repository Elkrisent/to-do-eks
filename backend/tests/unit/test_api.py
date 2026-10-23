import pytest

from app.db import make_engine
from tests.helpers import exercise_crud, make_client


@pytest.fixture
def client():
    return make_client(make_engine("sqlite://"))


def test_healthz(client):
    assert client.get("/api/healthz").json() == {"status": "ok"}


def test_crud_flow(client):
    exercise_crud(client)


def test_create_rejects_empty_title(client):
    assert client.post("/api/todos", json={"title": ""}).status_code == 422


def test_create_rejects_missing_title(client):
    assert client.post("/api/todos", json={}).status_code == 422


def test_create_rejects_overlong_title(client):
    assert client.post("/api/todos", json={"title": "x" * 201}).status_code == 422


def test_missing_todo_returns_404(client):
    assert client.get("/api/todos/999").status_code == 404
    assert client.put("/api/todos/999", json={"title": "a", "done": True}).status_code == 404
    assert client.delete("/api/todos/999").status_code == 404
