import pytest
from django.db import connection
from django.test import Client


def test_health_ok():
    response = Client().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_non_get():
    assert Client().post("/api/health/").status_code == 405


@pytest.mark.django_db
def test_ready_ok_with_postgres_and_cache():
    response = Client().get("/api/health/ready/")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "cache": "ok"}


def test_ready_returns_503_when_database_down(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(connection, "cursor", boom)
    response = Client().get("/api/health/ready/")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"