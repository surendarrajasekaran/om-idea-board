import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.migrate import main as migrate


@pytest.fixture()
def client(tmp_path):
    os.environ["DATABASE_URL"] = os.environ.get(
        "TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}"
    )
    migrate()
    with TestClient(app) as http:
        yield http
        from sqlalchemy import text

        with app.state.engine.begin() as connection:
            connection.execute(text("DELETE FROM ideas"))


def test_create_list_and_persist(client):
    assert client.get("/api/ideas").json() == []
    response = client.post("/api/ideas", json={"content": "  Ship a better idea  "})
    assert response.status_code == 201
    idea = response.json()
    assert idea["id"] > 0 and idea["created_at"]
    assert idea["content"] == "Ship a better idea"
    assert client.get("/api/ideas").json() == [idea]
    assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"content": ""},
        {"content": "  "},
        {"content": "a" * 1001},
        {},
        {"content": 123},
        {"content": "ok", "id": 7},
    ],
)
def test_validation(client, payload):
    assert client.post("/api/ideas", json=payload).status_code == 422
    assert client.get("/api/ideas").json() == []


def test_ordering_and_literal_input(client):
    first = client.post(
        "/api/ideas", json={"content": "<script>alert('hello')</script>"}
    ).json()
    second = client.post("/api/ideas", json={"content": "A second thought"}).json()
    assert [idea["id"] for idea in client.get("/api/ideas").json()] == [
        second["id"],
        first["id"],
    ]


def test_health_and_metrics(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert "idea_board_http_requests_total" in client.get("/metrics").text


def test_migration_is_repeatable(client):
    client.post("/api/ideas", json={"content": "Keep this idea"})
    migrate()
    assert len(client.get("/api/ideas").json()) == 1


def test_readiness_detects_missing_schema(client):
    from sqlalchemy import text

    with app.state.engine.begin() as connection:
        connection.execute(text("DROP TABLE ideas"))
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    migrate()
