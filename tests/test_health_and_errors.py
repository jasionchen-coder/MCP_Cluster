from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_ok_and_trace_id_header():
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-trace-id"].startswith("trace_")


def test_incoming_trace_id_is_reused():
    client = TestClient(app)

    response = client.get("/healthz", headers={"x-trace-id": "trace_existing"})

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == "trace_existing"
    assert response.json()["trace_id"] == "trace_existing"


def test_not_found_uses_unified_error_shape():
    client = TestClient(app)

    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
            "details": {"path": "/missing"},
        },
        "trace_id": response.headers["x-trace-id"],
    }
