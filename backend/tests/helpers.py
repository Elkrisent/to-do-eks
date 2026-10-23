from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_session
from app.main import app


def make_client(engine):
    """Return a TestClient whose DB sessions use `engine` with fresh empty tables."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    # Not used as a context manager on purpose: that would run the app's
    # startup (create_all on the real engine), which we don't want in tests.
    return TestClient(app)


def exercise_crud(client):
    """The CRUD scenario shared by the unit and integration suites."""
    assert client.get("/api/todos").json() == []

    created = client.post("/api/todos", json={"title": "learn eks"})
    assert created.status_code == 201
    todo = created.json()
    assert todo["title"] == "learn eks" and todo["done"] is False

    assert client.get(f"/api/todos/{todo['id']}").json() == todo

    updated = client.put(f"/api/todos/{todo['id']}", json={"title": "ship it", "done": True})
    assert updated.status_code == 200
    assert updated.json() == {"id": todo["id"], "title": "ship it", "done": True}

    assert len(client.get("/api/todos").json()) == 1

    assert client.delete(f"/api/todos/{todo['id']}").status_code == 204
    assert client.get(f"/api/todos/{todo['id']}").status_code == 404
    assert client.get("/api/todos").json() == []
