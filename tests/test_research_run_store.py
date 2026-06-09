from datetime import datetime, timezone

from app.research_workflow.schemas import ResearchRun, build_default_steps
from app.research_workflow.store import FileResearchRunStore


def _run(run_id: str, collection_name: str, created_at: datetime) -> ResearchRun:
    return ResearchRun(
        run_id=run_id,
        collection_id=f"{run_id}_collection",
        collection_name=collection_name,
        goal="Create a review",
        steps=build_default_steps(),
        output_dir=f"ResearchAgent/Runs/{run_id}",
        created_at=created_at,
        updated_at=created_at,
    )


def test_file_research_run_store_persists_runs(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    now = datetime.now(timezone.utc)

    saved = store.upsert(_run("run_a", "IRSTD", now))
    reloaded = FileResearchRunStore(path)

    assert saved.run_id == "run_a"
    assert reloaded.get("run_a").collection_name == "IRSTD"


def test_file_research_run_store_lists_newest_first(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    older = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 6, 9, 2, 0, tzinfo=timezone.utc)

    store.upsert(_run("run_old", "Old", older))
    store.upsert(_run("run_new", "New", newer))

    assert [run.run_id for run in store.list()] == ["run_new", "run_old"]


def test_file_research_run_store_uses_shared_lock_for_same_path(tmp_path):
    path = tmp_path / "research_runs.json"
    store_a = FileResearchRunStore(path)
    store_b = FileResearchRunStore(path)
    older = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 6, 9, 2, 0, tzinfo=timezone.utc)

    assert store_a._lock is store_b._lock

    store_a.upsert(_run("run_a", "A", older))
    store_b.upsert(_run("run_b", "B", newer))

    assert [run.run_id for run in store_a.list()] == ["run_b", "run_a"]


def test_file_research_run_store_clear(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    now = datetime.now(timezone.utc)
    store.upsert(_run("run_a", "IRSTD", now))

    store.clear()

    assert store.list() == []
    assert store.get("run_a") is None


def test_file_research_run_store_update_persists_changed_run(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    now = datetime.now(timezone.utc)
    store.upsert(_run("run_a", "IRSTD", now))

    updated = store.update(
        "run_a",
        lambda run: run.model_copy(
            update={
                "status": "cancelled",
                "updated_at": datetime(2026, 6, 9, 3, 0, tzinfo=timezone.utc),
            }
        ),
    )

    assert updated.status == "cancelled"
    assert store.get("run_a").status == "cancelled"


def test_file_research_run_store_update_missing_run_returns_none(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)

    updated = store.update("missing", lambda run: run)

    assert updated is None
