from fastapi.testclient import TestClient

from app.main import app


def test_http_errors_use_unified_response_shape():
    client = TestClient(app)

    response = client.get("/tasks/missing_task")

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "http_error"
    assert body["message"] == "任务 missing_task 不存在"
    assert body["status_code"] == 404
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_validation_error_does_not_expose_stack_trace():
    client = TestClient(app)

    response = client.post("/tasks/compare", json={"paper_ids": ["paper_a"]})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "http_error"
    assert "Traceback" not in body["message"]
