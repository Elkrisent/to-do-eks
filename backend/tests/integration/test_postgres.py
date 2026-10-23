import os

import pytest

from app.db import make_engine
from tests.helpers import exercise_crud, make_client

URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture
def client():
    engine = make_engine(URL)
    yield make_client(engine)
    engine.dispose()


def test_healthz_reaches_postgres(client):
    assert client.get("/api/healthz").json() == {"status": "ok"}


def test_crud_flow_against_postgres(client):
    exercise_crud(client)


def test_data_persists_across_requests(client):
    client.post("/api/todos", json={"title": "persisted"})
    assert [t["title"] for t in client.get("/api/todos").json()] == ["persisted"]
