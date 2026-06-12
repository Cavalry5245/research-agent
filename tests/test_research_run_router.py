from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.research_runs import router as research_runs_router
from app.research_workflow.paper_processing import PaperProcessingResult
from app.research_workflow.schemas import ResearchRunPaperItem
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore

app = FastAPI()
app.include_router(research_runs_router)


class RejectDefaultService:
    def create_run(self, request):
        raise AssertionError("FastAPI dependency override was not used")

    def list_runs(self):
        raise AssertionError("FastAPI dependency override was not used")

    def get_run(self, run_id):
        raise AssertionError("FastAPI dependency override was not used")

    def cancel_run(self, run_id):
        raise AssertionError("FastAPI dependency override was not used")


def _override_research_run_service(tmp_path, monkeypatch) -> ResearchRunService:
    from app.routers import research_runs as router

    service = ResearchRunService(
        store=FileResearchRunStore(tmp_path / "runs.json"),
        vault_root=tmp_path / "vault",
    )
    monkeypatch.setattr(router, "_service_instance", RejectDefaultService())
    app.dependency_overrides[router.get_research_run_service] = lambda: service
    return service


def test_research_run_routes_create_list_get_and_cancel(tmp_path, monkeypatch):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        client = TestClient(app)

        create_response = client.post(
            "/research-runs",
            json={
                "collection_id": "COLL123",
                "collection_name": "IRSTD",
                "goal": "Create an IRSTD review",
                "options": {"max_papers": 3, "semantic_scholar": True},
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["collection_id"] == "COLL123"
        assert created["steps"][0]["agent"] == "CollectionIntakeAgent"

        list_response = client.get("/research-runs")
        assert list_response.status_code == 200
        assert list_response.json()["count"] == 1

        detail_response = client.get(f"/research-runs/{created['run_id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["run_id"] == created["run_id"]

        cancel_response = client.delete(f"/research-runs/{created['run_id']}")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"

        conflict_response = client.delete(f"/research-runs/{created['run_id']}")
        assert conflict_response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_research_run_detail_missing_returns_404(tmp_path, monkeypatch):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        client = TestClient(app)
        response = client.get("/research-runs/missing")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_research_run_execute_local_route(tmp_path, monkeypatch):
    service = _override_research_run_service(tmp_path, monkeypatch)

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="item-1",
                    title="Injected Paper",
                    zotero_item_id="ZOTERO1",
                    pdf_path=str(tmp_path / "paper.pdf"),
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            completed_at = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "fake-processor-paper",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": completed_at,
                        "completed_at": completed_at,
                    }
                ),
                chunk_count=3,
                note_path=str(tmp_path / "note.md"),
                vector_backend="fake",
            )

    try:
        client = TestClient(app)
        created = client.post(
            "/research-runs",
            json={"collection_id": "COLL123", "collection_name": "IRSTD"},
        ).json()

        from app.routers import research_runs as router

        app.dependency_overrides[router.get_optional_collection_intake_service] = lambda: FakeIntake()
        app.dependency_overrides[router.get_paper_processing_service] = lambda: FakeProcessor()

        response = client.post(f"/research-runs/{created['run_id']}/execute-local")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["paper_items"][0]["paper_id"] == "fake-processor-paper"
        assert response.json()["paper_items"][0]["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


def test_research_run_tools_health_route(tmp_path, monkeypatch):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        client = TestClient(app)
        response = client.get("/research-runs/tools/health")

        assert response.status_code == 200
        tool_names = {item["tool_name"] for item in response.json()["tools"]}
        assert "research_agent.echo" in tool_names
        assert "zotero.list_collection_items" in tool_names
        assert "semantic_scholar.enrich" in tool_names
        assert "arxiv.find_preprint" in tool_names
        assert "ResearchAgent MCP Server" in tool_names
    finally:
        app.dependency_overrides.clear()


def test_tool_health_reports_mcp_state(tmp_path, monkeypatch):
    service = _override_research_run_service(tmp_path, monkeypatch)

    class FakeManager:
        def list_servers(self):
            return ["zotero"]

        def list_tools(self, server_name):
            assert server_name == "zotero"
            return ["zotero_get_collection_items", "zotero_get_item"]

    service._mcp_manager = FakeManager()

    try:
        client = TestClient(app)
        response = client.get("/research-runs/tools/health")

        assert response.status_code == 200
        tools = response.json()["tools"]
        assert all("provider" in tool for tool in tools)
        assert all("fallback_active" in tool for tool in tools)
        assert all("state" in tool for tool in tools)

        zotero = next(
            tool for tool in tools if tool["tool_name"] == "Zotero MCP Server"
        )
        assert zotero["provider"] == "mcp"
        assert zotero["available"] is True
        assert zotero["fallback_active"] is False
        assert zotero["tool_count"] == 2
        assert "MCP tool(s) discovered" in zotero["message"]
        assert any(tool["tool_name"] == "ResearchAgent MCP Server" for tool in tools)
    finally:
        app.dependency_overrides.clear()


def test_research_run_tool_call_route(tmp_path, monkeypatch):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        from app.routers import research_runs as router

        class FakeEmbeddingClient:
            def embed_query(self, query):
                return [0.1, 0.2, 0.3]

        class FakeVectorStore:
            def query(self, query_embedding, top_k=5, paper_id=None, hybrid_query_text=None):
                return [
                    {
                        "chunk_id": "chunk-1",
                        "paper_id": paper_id or "paper_001",
                        "content": hybrid_query_text,
                        "score": 0.9,
                        "embedding": query_embedding,
                    }
                ]

        app.dependency_overrides[router.get_embedding_client] = (
            lambda: FakeEmbeddingClient()
        )
        app.dependency_overrides[router.get_vector_store] = lambda: FakeVectorStore()
        app.dependency_overrides[router.get_llm_client] = lambda: object()
        app.dependency_overrides[router.get_reranker] = lambda: None
        app.dependency_overrides[router.get_retriever] = lambda: None

        client = TestClient(app)
        response = client.post(
            "/research-runs/tools/call",
            json={
                "tool_name": "research_agent.search_chunks",
                "arguments": {"query": "infrared", "top_k": 2, "paper_id": "paper_qa"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["tool_name"] == "research_agent.search_chunks"
        assert payload["status"] == "completed"
        assert payload["result"]["query"] == "infrared"
        assert payload["result"]["matches"][0]["paper_id"] == "paper_qa"
        assert payload["result"]["matches"][0]["content"] == "infrared"
    finally:
        app.dependency_overrides.clear()


def test_research_run_tool_call_route_uses_qa_and_compare_backends(
    tmp_path,
    monkeypatch,
):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        from app.routers import research_runs as router

        calls = {}

        class FakeEmbeddingClient:
            pass

        class FakeVectorStore:
            pass

        class FakeLLMClient:
            pass

        def fake_answer_question(**kwargs):
            calls["qa"] = kwargs
            return {
                "question": kwargs["question"],
                "answer": "backend QA answer",
                "sources": [],
            }

        def fake_compare_papers(paper_ids, metadata_dir, llm_client=None):
            calls["compare"] = {
                "paper_ids": paper_ids,
                "metadata_dir": metadata_dir,
                "llm_client": llm_client,
            }
            return {"overview": "backend compare result", "paper_ids": paper_ids}

        monkeypatch.setattr(router, "answer_question", fake_answer_question)
        monkeypatch.setattr(router, "compare_papers", fake_compare_papers)
        app.dependency_overrides[router.get_embedding_client] = (
            lambda: FakeEmbeddingClient()
        )
        app.dependency_overrides[router.get_vector_store] = lambda: FakeVectorStore()
        app.dependency_overrides[router.get_llm_client] = lambda: FakeLLMClient()
        app.dependency_overrides[router.get_reranker] = lambda: None
        app.dependency_overrides[router.get_retriever] = lambda: None

        client = TestClient(app)
        qa_response = client.post(
            "/research-runs/tools/call",
            json={
                "tool_name": "research_agent.answer_question",
                "arguments": {
                    "question": "What changed?",
                    "run_id": "run_1",
                    "paper_id": "paper_1",
                    "top_k": 3,
                },
            },
        )
        compare_response = client.post(
            "/research-runs/tools/call",
            json={
                "tool_name": "research_agent.compare_papers",
                "arguments": {"paper_ids": ["paper_1", "paper_2"]},
            },
        )

        assert qa_response.status_code == 200
        qa_payload = qa_response.json()
        assert qa_payload["status"] == "completed"
        assert qa_payload["result"]["answer"]["answer"] == "backend QA answer"
        assert calls["qa"]["paper_id"] == "paper_1"
        assert calls["qa"]["top_k"] == 3

        assert compare_response.status_code == 200
        compare_payload = compare_response.json()
        assert compare_payload["status"] == "completed"
        assert compare_payload["result"]["comparison"]["overview"] == (
            "backend compare result"
        )
        assert calls["compare"]["paper_ids"] == ["paper_1", "paper_2"]
    finally:
        app.dependency_overrides.clear()


def test_production_app_import_registers_research_run_routes():
    from app.main import app as production_app

    route_paths = {route.path for route in production_app.routes}

    assert "/research-runs" in route_paths
    assert "/research-runs/tools/health" in route_paths
    assert "/research-runs/tools/call" in route_paths
    assert "/research-runs/{run_id}/execute-local" in route_paths
