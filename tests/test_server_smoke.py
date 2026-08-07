"""OpenAI-compatible server smoke tests — real FastAPI app routes, no MLX load."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nex.server import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "models" in body
    assert isinstance(body["models"], int)
    assert body["models"] >= 1


def test_list_models_openai_shape(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body.get("object") == "list"
    assert isinstance(body.get("data"), list)
    assert len(body["data"]) >= 1
    first = body["data"][0]
    assert "id" in first
    assert first.get("object") == "model"


def test_chat_completions_requires_messages(client):
    r = client.post("/v1/chat/completions", json={"model": "x", "messages": []})
    assert r.status_code == 400
