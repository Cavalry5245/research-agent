from fastapi.testclient import TestClient

from app.main import app


def test_task_routes_have_openapi_descriptions():
    client = TestClient(app)

    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert paths["/tasks"]["get"]["summary"] == "List background tasks"
    assert paths["/tasks/{job_id}"]["get"]["summary"] == "Get background task status"
    assert (
        paths["/tasks/{job_id}/result"]["get"]["summary"]
        == "Get background task result"
    )
    assert paths["/tasks/{job_id}"]["delete"]["summary"] == "Cancel background task"
    assert (
        paths["/tasks/{job_id}/retry"]["post"]["summary"]
        == "Retry failed background task"
    )
    assert (
        paths["/tasks/note/{paper_id}"]["post"]["summary"]
        == "Submit note generation task"
    )
    assert paths["/tasks/compare"]["post"]["summary"] == "Submit paper comparison task"


def test_task_routes_have_response_models():
    client = TestClient(app)

    schema = client.get("/openapi.json").json()

    assert "JobListResponse" in schema["components"]["schemas"]
    assert "JobStatusResponse" in schema["components"]["schemas"]
    assert "JobRetryResponse" in schema["components"]["schemas"]
