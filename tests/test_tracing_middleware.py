from fastapi.testclient import TestClient

from app.main import app


def test_request_id_header_is_added_to_response():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_request_id_header_preserves_incoming_value():
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "req_custom"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_custom"


def test_request_id_header_rejects_malformed_incoming_value():
    client = TestClient(app)

    response = client.get(
        "/health", headers={"X-Request-ID": "bad id with spaces and \n newline"}
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "bad id with spaces and \n newline"
    assert len(response.headers["X-Request-ID"]) > 0
