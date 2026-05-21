from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.main import app


@dataclass
class StubComparison:
    markdown: str


def _reset_job_store():
    from app.main import _get_job_store

    _get_job_store().clear()


def test_submit_compare_task_runs_in_background_and_stores_result(monkeypatch, tmp_path):
    _reset_job_store()
    client = TestClient(app)

    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        "app.main.compare_papers",
        lambda paper_ids, metadata_dir, llm_client: StubComparison("# Compare\nresult"),
    )

    response = client.post("/tasks/compare", json={"paper_ids": ["paper_a", "paper_b"]})

    assert response.status_code == 202
    body = response.json()
    assert body["job_type"] == "paper_comparison"
    assert body["paper_ids"] == ["paper_a", "paper_b"]

    detail = client.get(f"/tasks/{body['job_id']}").json()
    assert detail["status"] == "completed"
    assert detail["result"]["paper_ids"] == ["paper_a", "paper_b"]
    assert detail["result"]["output_path"].endswith(".md")
    assert "compare_" in detail["result"]["output_path"]


def test_submit_compare_task_validates_paper_count():
    _reset_job_store()
    client = TestClient(app)

    response = client.post("/tasks/compare", json={"paper_ids": ["paper_a"]})

    assert response.status_code == 400
    assert response.json()["message"] == "请选择至少 2 篇论文进行对比"


def test_submit_compare_task_records_failure(monkeypatch):
    _reset_job_store()
    client = TestClient(app)

    def fail(*args, **kwargs):
        raise RuntimeError("compare failed")

    monkeypatch.setattr("app.main.compare_papers", fail)

    response = client.post("/tasks/compare", json={"paper_ids": ["paper_a", "paper_b"]})

    assert response.status_code == 202
    detail = client.get(f"/tasks/{response.json()['job_id']}").json()
    assert detail["status"] == "failed"
    assert detail["error"] == "compare failed"
