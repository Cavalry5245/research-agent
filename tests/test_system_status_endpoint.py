from fastapi.testclient import TestClient

from app.main import app


def test_system_status_endpoint_returns_dashboard_contract(monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings, "embedding_model", "bge-m3")
    monkeypatch.setattr(
        main.settings, "chroma_collection_name", "research_papers_bge_m3_v1"
    )

    class FakeVectorStore:
        def count(self):
            return 100

        def backend_name(self):
            return "chroma"

        def metadata(self):
            return {
                "backend": "chroma",
                "collection_name": "research_papers_bge_m3_v1",
                "build_status": "ready",
                "embedding_dimension": 1024,
                "embedding_model": "bge-m3",
                "schema_version": 1,
                "chunk_count": 100,
                "paper_count": 2,
                "persist_dir": "app/storage/vector_db",
            }

    class FakeJobStore:
        def list(self):
            return []

    class FakeResearchRunService:
        def list_runs(self):
            return []

    monkeypatch.setattr(main, "_get_vector_store", lambda: FakeVectorStore())
    monkeypatch.setattr(main, "_get_job_store", lambda: FakeJobStore())
    monkeypatch.setattr(
        main,
        "_get_research_run_service_for_status",
        lambda: FakeResearchRunService(),
    )
    monkeypatch.setattr(
        main,
        "list_papers",
        lambda metadata_dir: [
            {"paper_id": "paper_1", "title": "Paper 1", "abstract": "A"}
        ],
    )
    monkeypatch.setattr(
        main,
        "build_mcp_hub_health",
        lambda service, storage_root: [
            {
                "tool_name": "ResearchAgent MCP Server",
                "provider": "mcp_stdio",
                "available": True,
                "fallback_available": False,
                "fallback_active": False,
                "message": "available",
                "tool_count": 7,
                "state": "available",
            }
        ],
    )

    client = TestClient(app)
    response = client.get("/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == "ResearchAgent"
    assert payload["status"] == "ok"
    assert payload["counts"] == {
        "papers": 1,
        "chunks": 100,
        "tasks": 0,
        "research_runs": 0,
    }
    assert payload["models"]["llm"]["configured"] is bool(main.settings.llm_api_key)
    assert payload["models"]["embedding"]["model"] == main.settings.embedding_model
    assert payload["vector_store"] == {
        "available": True,
        "backend": "chroma",
        "store_path": None,
        "collection_name": "research_papers_bge_m3_v1",
        "build_status": "ready",
        "embedding_dimension": 1024,
        "embedding_model": "bge-m3",
        "schema_version": 1,
        "chunk_count": 100,
        "paper_count": 2,
        "persist_dir": "app/storage/vector_db",
        "error": None,
    }
    assert (
        payload["integrations"]["zotero"]["local_api_url"]
        == "http://127.0.0.1:23119/api/users/0"
    )
    assert payload["mcp_hub"][0]["tool_name"] == "ResearchAgent MCP Server"


def test_system_status_endpoint_degrades_when_vector_store_fails(monkeypatch):
    from app import main

    class BrokenVectorStore:
        def count(self):
            raise RuntimeError("vector store offline")

        def metadata(self):
            raise RuntimeError("vector store offline")

    class FakeJobStore:
        def list(self):
            return []

    class FakeResearchRunService:
        def list_runs(self):
            return []

    monkeypatch.setattr(main, "_get_vector_store", lambda: BrokenVectorStore())
    monkeypatch.setattr(main, "_get_job_store", lambda: FakeJobStore())
    monkeypatch.setattr(
        main,
        "_get_research_run_service_for_status",
        lambda: FakeResearchRunService(),
    )
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [])
    monkeypatch.setattr(main, "build_mcp_hub_health", lambda service, storage_root: [])

    client = TestClient(app)
    response = client.get("/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["vector_store"]["available"] is False
    assert payload["vector_store"]["error"] == "vector store offline"


def test_system_status_endpoint_does_not_start_mcp_services(monkeypatch, tmp_path):
    from app import main
    from app.research_workflow.service import ResearchRunService

    def fail_if_mcp_initializes(self):
        raise AssertionError("status endpoint must not initialize MCP services")

    class FakeVectorStore:
        def count(self):
            return 0

        def backend_name(self):
            return "json"

        def metadata(self):
            return {"backend": "json", "store_path": "store.json"}

    monkeypatch.setattr(main.settings, "metadata_dir", str(tmp_path / "metadata"))
    monkeypatch.setattr(main, "_storage_is_writable", lambda: True)
    monkeypatch.setattr(main, "_get_vector_store", lambda: FakeVectorStore())
    monkeypatch.setattr(main, "_get_job_store", lambda: type("Jobs", (), {"list": lambda self: []})())
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [])
    monkeypatch.setattr(ResearchRunService, "_init_mcp_manager", fail_if_mcp_initializes)

    client = TestClient(app)
    response = client.get("/system/status")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_system_status_endpoint_degrades_for_malformed_chroma_metadata(monkeypatch):
    from app import main

    class MalformedChromaStore:
        def backend_name(self):
            return "chroma"

        def count(self):
            return 5

        def metadata(self):
            return {
                "backend": "chroma",
                "collection_name": "research_papers_bge_m3_v1",
                "build_status": "ready",
                "embedding_dimension": {"invalid": 1024},
                "embedding_model": "bge-m3",
                "schema_version": 1,
                "api_key": "must-not-leak",
                "base_url": "https://secret.invalid/v1",
            }

    monkeypatch.setattr(main, "_storage_is_writable", lambda: True)
    monkeypatch.setattr(main, "_get_vector_store", lambda: MalformedChromaStore())
    monkeypatch.setattr(
        main, "_get_job_store", lambda: type("Jobs", (), {"list": lambda self: []})()
    )
    monkeypatch.setattr(
        main,
        "_get_research_run_service_for_status",
        lambda: type("Runs", (), {"list_runs": lambda self: []})(),
    )
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [])
    monkeypatch.setattr(main, "build_mcp_hub_health", lambda service, storage_root: [])

    response = TestClient(app).get("/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["vector_store"]["available"] is False
    assert payload["vector_store"]["embedding_dimension"] is None
    assert "api_key" not in payload["vector_store"]
    assert "base_url" not in payload["vector_store"]


def test_system_status_endpoint_degrades_when_vector_count_raises(monkeypatch):
    from app import main

    class CountFailureStore:
        def backend_name(self):
            return "json"

        def metadata(self):
            return {"backend": "json", "store_path": "store.json"}

        def count(self):
            raise RuntimeError("count unavailable")

    monkeypatch.setattr(main, "_storage_is_writable", lambda: True)
    monkeypatch.setattr(main, "_get_vector_store", lambda: CountFailureStore())
    monkeypatch.setattr(
        main, "_get_job_store", lambda: type("Jobs", (), {"list": lambda self: []})()
    )
    monkeypatch.setattr(
        main,
        "_get_research_run_service_for_status",
        lambda: type("Runs", (), {"list_runs": lambda self: []})(),
    )
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [])
    monkeypatch.setattr(main, "build_mcp_hub_health", lambda service, storage_root: [])

    response = TestClient(app).get("/system/status")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["vector_store"]["available"] is False


def test_system_status_endpoint_redacts_secrets_from_vector_errors(monkeypatch):
    from app import main

    def fail_vector_store():
        raise RuntimeError(
            "vector offline api_key=sk-secret-value at https://secret.invalid/v1"
        )

    monkeypatch.setattr(main, "_storage_is_writable", lambda: True)
    monkeypatch.setattr(main, "_get_vector_store", fail_vector_store)
    monkeypatch.setattr(
        main, "_get_job_store", lambda: type("Jobs", (), {"list": lambda self: []})()
    )
    monkeypatch.setattr(
        main,
        "_get_research_run_service_for_status",
        lambda: type("Runs", (), {"list_runs": lambda self: []})(),
    )
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [])
    monkeypatch.setattr(main, "build_mcp_hub_health", lambda service, storage_root: [])

    response = TestClient(app).get("/system/status")

    error = response.json()["vector_store"]["error"]
    assert response.json()["status"] == "degraded"
    assert "sk-secret-value" not in error
    assert "secret.invalid" not in error
