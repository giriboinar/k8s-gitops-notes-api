"""Tests for the Notes API: root, health, CRUD, 404, validation, metrics."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "Notes API"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_get_list_and_delete():
    created = client.post(
        "/api/notes",
        json={"title": "Deploy checklist", "body": "Check /health first", "tags": ["devops"]},
    )
    assert created.status_code == 201
    note_id = created.json()["id"]

    got = client.get(f"/api/notes/{note_id}")
    assert got.status_code == 200
    assert got.json()["title"] == "Deploy checklist"

    listed = client.get("/api/notes", params={"tag": "devops"})
    assert any(n["id"] == note_id for n in listed.json())

    deleted = client.delete(f"/api/notes/{note_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/notes/{note_id}").status_code == 404


def test_get_missing_returns_404():
    assert client.get("/api/notes/does-not-exist").status_code == 404


def test_empty_title_is_rejected():
    r = client.post("/api/notes", json={"title": "", "body": "no title"})
    assert r.status_code == 422


def test_metrics_mentions_notes_counters():
    client.post("/api/notes", json={"title": "Metrics probe"})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "notes_created_total" in r.text
    assert "notes_total" in r.text
