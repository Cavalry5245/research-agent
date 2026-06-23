"""
Research Pipeline Store

管理 pipeline 状态的持久化存储。
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_connection(db_path: str) -> sqlite3.Connection:
    """
    Get a SQLite connection with foreign keys enabled.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        sqlite3.Connection with foreign keys enabled.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """
    Initialize the research pipeline SQLite database with all required tables.

    Creates 9 tables for storing research run state, stages, events, candidates,
    paper cards, evidence, reports, and claims. This function is idempotent and
    can be safely called multiple times.

    Args:
        db_path: Path to SQLite database file. If None, uses default from settings.

    Tables created:
        - research_runs: Main run metadata and configuration
        - research_run_stages: Stage progress (planner, retriever, reader, synthesis, harness)
        - research_run_events: Event log for frontend display
        - research_plans: Planner output (initial and candidate_selection phases)
        - paper_candidates: Candidate papers from retriever
        - paper_cards: Extracted paper content from reader
        - paper_evidence: Evidence snippets with citations
        - research_reports: Final markdown reports
        - report_claims: Claims with verification status from harness
    """
    if db_path is None:
        from app.config import settings
        db_path = f"{settings.metadata_dir}/research_pipeline.sqlite3"

    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    # 1. research_runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_runs (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            normalized_question TEXT,
            source_mode TEXT NOT NULL,
            zotero_collection_key TEXT,
            status TEXT NOT NULL,
            max_reader_papers INTEGER NOT NULL,
            reader_concurrency INTEGER NOT NULL,
            year_start INTEGER,
            year_end INTEGER,
            venue_filter_json TEXT NOT NULL DEFAULT '[]',
            keywords_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            failed_at TEXT,
            cancelled_at TEXT,
            error TEXT
        )
    """)

    # 2. research_run_stages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_run_stages (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            started_at TEXT,
            completed_at TEXT,
            error TEXT,
            FOREIGN KEY(run_id) REFERENCES research_runs(id)
        )
    """)

    # 3. research_run_events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_run_events (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES research_runs(id)
        )
    """)

    # 4. research_plans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_plans (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            phase TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES research_runs(id)
        )
    """)

    # 5. paper_candidates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_candidates (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            paper_id TEXT NOT NULL,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            authors_json TEXT NOT NULL DEFAULT '[]',
            year INTEGER,
            venue TEXT,
            abstract TEXT,
            doi TEXT,
            arxiv_id TEXT,
            semantic_scholar_id TEXT,
            zotero_item_id TEXT,
            url TEXT,
            pdf_url TEXT,
            local_pdf_path TEXT,
            citation_count INTEGER,
            relevance_score REAL,
            selected_for_reader INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE(run_id, paper_id),
            FOREIGN KEY(run_id) REFERENCES research_runs(id)
        )
    """)

    # 6. paper_cards
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_cards (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            paper_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            status TEXT NOT NULL,
            extraction_mode TEXT NOT NULL,
            title TEXT NOT NULL,
            bibliographic_json TEXT NOT NULL DEFAULT '{}',
            research_problem TEXT,
            method TEXT,
            datasets_json TEXT NOT NULL DEFAULT '[]',
            metrics_json TEXT NOT NULL DEFAULT '[]',
            key_results_json TEXT NOT NULL DEFAULT '[]',
            limitations_json TEXT NOT NULL DEFAULT '[]',
            assumptions_json TEXT NOT NULL DEFAULT '[]',
            future_work_json TEXT NOT NULL DEFAULT '[]',
            claims_json TEXT NOT NULL DEFAULT '[]',
            evidence_json TEXT NOT NULL DEFAULT '[]',
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES research_runs(id),
            FOREIGN KEY(candidate_id) REFERENCES paper_candidates(id)
        )
    """)

    # 7. paper_evidence
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_evidence (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            paper_id TEXT NOT NULL,
            paper_card_id TEXT NOT NULL,
            claim_id TEXT,
            snippet TEXT NOT NULL,
            section TEXT,
            page INTEGER,
            source_url TEXT,
            evidence_type TEXT NOT NULL,
            confidence REAL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(run_id) REFERENCES research_runs(id),
            FOREIGN KEY(paper_card_id) REFERENCES paper_cards(id)
        )
    """)

    # 8. research_reports
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_reports (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            markdown TEXT NOT NULL,
            template_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES research_runs(id)
        )
    """)

    # 9. report_claims
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_claims (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            report_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            citation_ids_json TEXT NOT NULL DEFAULT '[]',
            evidence_ids_json TEXT NOT NULL DEFAULT '[]',
            verification_status TEXT NOT NULL,
            verification_reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES research_runs(id),
            FOREIGN KEY(report_id) REFERENCES research_reports(id)
        )
    """)

    conn.commit()
    conn.close()


# ==================== CRUD Operations ====================


def create_run(
    db_path: str,
    question: str,
    source_mode: str,
    max_reader_papers: int,
    reader_concurrency: int,
    zotero_collection_key: str | None = None,
    year_start: int | None = None,
    year_end: int | None = None,
    venue_filter: list[str] | None = None,
    keywords: list[str] | None = None,
) -> str:
    """
    Create a new research run and initialize its 5 stages.

    Args:
        db_path: Path to SQLite database file.
        question: Research question.
        source_mode: One of "web_search", "zotero_only", "hybrid".
        max_reader_papers: Maximum papers to read (3-15).
        reader_concurrency: Number of concurrent readers.
        zotero_collection_key: Optional Zotero collection key.
        year_start: Optional start year filter.
        year_end: Optional end year filter.
        venue_filter: Optional list of venue names.
        keywords: Optional list of keywords.

    Returns:
        run_id: The generated run ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

    venue_filter = venue_filter or []
    keywords = keywords or []

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Insert run
        cursor.execute(
            """
            INSERT INTO research_runs (
                id, question, source_mode, zotero_collection_key, status,
                max_reader_papers, reader_concurrency, year_start, year_end,
                venue_filter_json, keywords_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                question,
                source_mode,
                zotero_collection_key,
                "queued",
                max_reader_papers,
                reader_concurrency,
                year_start,
                year_end,
                json.dumps(venue_filter),
                json.dumps(keywords),
                now,
            ),
        )

        # Initialize 5 stages
        stages = ["planner", "retriever", "reader", "synthesis", "harness"]
        for stage in stages:
            stage_id = f"stage_{run_id}_{stage}"
            cursor.execute(
                """
                INSERT INTO research_run_stages (
                    id, run_id, stage, status, progress, message
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (stage_id, run_id, stage, "queued", 0.0, ""),
            )

        conn.commit()
        return run_id

    finally:
        conn.close()


def get_run_detail(db_path: str, run_id: str) -> dict[str, Any] | None:
    """
    Get detailed information about a run including stages, events, candidates, and cards.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        Dictionary with run details, stages, events, candidates, and cards, or None if not found.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get run
        cursor.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,))
        run_row = cursor.fetchone()

        if run_row is None:
            return None

        # Get stages
        cursor.execute(
            "SELECT * FROM research_run_stages WHERE run_id = ? ORDER BY stage",
            (run_id,),
        )
        stage_rows = cursor.fetchall()

        # Get events
        cursor.execute(
            "SELECT * FROM research_run_events WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        )
        event_rows = cursor.fetchall()

        # Get candidates
        candidates = get_candidates(db_path, run_id)

        # Get paper cards
        cards = get_paper_cards(db_path, run_id)

        # Build response
        return {
            "run_id": run_row["id"],
            "question": run_row["question"],
            "normalized_question": run_row["normalized_question"],
            "source_mode": run_row["source_mode"],
            "zotero_collection_key": run_row["zotero_collection_key"],
            "status": run_row["status"],
            "max_reader_papers": run_row["max_reader_papers"],
            "reader_concurrency": run_row["reader_concurrency"],
            "year_start": run_row["year_start"],
            "year_end": run_row["year_end"],
            "venue_filter": json.loads(run_row["venue_filter_json"]),
            "keywords": json.loads(run_row["keywords_json"]),
            "created_at": run_row["created_at"],
            "started_at": run_row["started_at"],
            "completed_at": run_row["completed_at"],
            "failed_at": run_row["failed_at"],
            "cancelled_at": run_row["cancelled_at"],
            "error": run_row["error"],
            "stages": [
                {
                    "id": stage["id"],
                    "run_id": stage["run_id"],
                    "stage": stage["stage"],
                    "status": stage["status"],
                    "progress": stage["progress"],
                    "message": stage["message"],
                    "started_at": stage["started_at"],
                    "completed_at": stage["completed_at"],
                    "error": stage["error"],
                }
                for stage in stage_rows
            ],
            "events": [
                {
                    "id": event["id"],
                    "run_id": event["run_id"],
                    "stage": event["stage"],
                    "level": event["level"],
                    "message": event["message"],
                    "payload": json.loads(event["payload_json"]),
                    "created_at": event["created_at"],
                }
                for event in event_rows
            ],
            "candidates": candidates,
            "cards": cards,
        }

    finally:
        conn.close()


def list_runs(db_path: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    List runs in reverse chronological order (newest first).

    Args:
        db_path: Path to SQLite database file.
        limit: Maximum number of runs to return.

    Returns:
        List of run summaries with run_id, question, source_mode, status, error, created_at.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, question, source_mode, status, error, created_at
            FROM research_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

        return [
            {
                "run_id": row["id"],
                "question": row["question"],
                "source_mode": row["source_mode"],
                "status": row["status"],
                "error": row["error"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    finally:
        conn.close()


def delete_run(db_path: str, run_id: str) -> bool:
    """
    Delete a research run and all database records owned by it.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        True if the run existed and was deleted, False otherwise.
    """
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT 1 FROM research_runs WHERE id = ?", (run_id,))
        if cursor.fetchone() is None:
            return False

        cursor.execute("DELETE FROM report_claims WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM paper_evidence WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM paper_cards WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM paper_candidates WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM research_reports WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM research_plans WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM research_run_events WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM research_run_stages WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM research_runs WHERE id = ?", (run_id,))

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_run_create_params(db_path: str, run_id: str) -> dict:
    """
    Extract creation parameters from an existing run for rerun purposes.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        Dictionary with run creation parameters.

    Raises:
        ValueError: If run not found.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT question, source_mode, zotero_collection_key,
                   max_reader_papers, reader_concurrency,
                   year_start, year_end, venue_filter_json, keywords_json
            FROM research_runs
            WHERE id = ?
        """, (run_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Run {run_id} not found")

        return {
            "question": row["question"],
            "source_mode": row["source_mode"],
            "zotero_collection_key": row["zotero_collection_key"],
            "max_reader_papers": row["max_reader_papers"],
            "reader_concurrency": row["reader_concurrency"],
            "year_start": row["year_start"],
            "year_end": row["year_end"],
            "venue_filter": json.loads(row["venue_filter_json"]),
            "keywords": json.loads(row["keywords_json"]),
        }
    finally:
        conn.close()


def update_run_status(
    db_path: str,
    run_id: str,
    status: str,
    error: str | None = None,
) -> bool:
    """
    Update run status and set appropriate timestamp fields.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        status: New status ("queued", "running", "completed", "failed", "cancelled", "degraded").
        error: Optional error message (used with "failed" status).

    Returns:
        True if update succeeded, False if run not found.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Determine which timestamp field to set
        timestamp_updates = []
        timestamp_values = []

        if status == "running":
            timestamp_updates.append("started_at = ?")
            timestamp_values.append(now)
        elif status == "completed":
            timestamp_updates.append("completed_at = ?")
            timestamp_values.append(now)
        elif status == "failed":
            timestamp_updates.append("failed_at = ?")
            timestamp_values.append(now)
        elif status == "cancelled":
            timestamp_updates.append("cancelled_at = ?")
            timestamp_values.append(now)

        # Build update query
        update_parts = ["status = ?"]
        values = [status]

        if error is not None:
            update_parts.append("error = ?")
            values.append(error)

        if timestamp_updates:
            update_parts.extend(timestamp_updates)
            values.extend(timestamp_values)

        values.append(run_id)

        query = f"""
            UPDATE research_runs
            SET {', '.join(update_parts)}
            WHERE id = ?
        """

        cursor.execute(query, values)
        conn.commit()

        # Check if any row was updated
        return cursor.rowcount > 0

    finally:
        conn.close()


def update_stage(
    db_path: str,
    run_id: str,
    stage: str,
    status: str,
    progress: float = 0.0,
    message: str = "",
    error: str | None = None,
) -> bool:
    """
    Update stage status, progress, and message.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name ("planner", "retriever", "reader", "synthesis", "harness").
        status: New status ("queued", "running", "completed", "failed", "degraded").
        progress: Progress (0.0 to 1.0).
        message: Status message.
        error: Optional error message.

    Returns:
        True if update succeeded, False if stage not found.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Determine timestamp updates
        timestamp_updates = []
        timestamp_values = []

        if status == "running":
            timestamp_updates.append("started_at = ?")
            timestamp_values.append(now)
        elif status == "completed":
            timestamp_updates.append("completed_at = ?")
            timestamp_values.append(now)

        # Build update query
        update_parts = ["status = ?", "progress = ?", "message = ?"]
        values = [status, progress, message]

        if error is not None:
            update_parts.append("error = ?")
            values.append(error)

        if timestamp_updates:
            update_parts.extend(timestamp_updates)
            values.extend(timestamp_values)

        values.extend([run_id, stage])

        query = f"""
            UPDATE research_run_stages
            SET {', '.join(update_parts)}
            WHERE run_id = ? AND stage = ?
        """

        cursor.execute(query, values)
        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def append_event(
    db_path: str,
    run_id: str,
    stage: str,
    level: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """
    Append an event to the run's event log.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name.
        level: Event level ("debug", "info", "warning", "error").
        message: Event message.
        payload: Optional event payload.

    Returns:
        event_id: The generated event ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    event_id = f"event_{uuid.uuid4().hex[:16]}"
    payload = payload or {}

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO research_run_events (
                id, run_id, stage, level, message, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, run_id, stage, level, message, json.dumps(payload), now),
        )

        conn.commit()
        return event_id

    finally:
        conn.close()


# ==================== Candidate CRUD Operations ====================


def create_candidate(
    db_path: str,
    run_id: str,
    candidate: Any,  # PaperCandidate
) -> str:
    """
    Create a paper candidate record.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        candidate: PaperCandidate instance.

    Returns:
        candidate_id: The generated candidate ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    candidate_id = f"cand_{uuid.uuid4().hex[:16]}"

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO paper_candidates (
                id, run_id, paper_id, source, title, authors_json, year, venue,
                abstract, doi, arxiv_id, semantic_scholar_id, zotero_item_id,
                url, pdf_url, local_pdf_path, citation_count, relevance_score,
                selected_for_reader, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                run_id,
                candidate.paper_id,
                candidate.source,
                candidate.title,
                json.dumps(candidate.authors),
                candidate.year,
                candidate.venue,
                candidate.abstract,
                candidate.doi,
                candidate.arxiv_id,
                candidate.semantic_scholar_id,
                candidate.zotero_item_id,
                candidate.url,
                candidate.pdf_url,
                candidate.local_pdf_path,
                candidate.citation_count,
                candidate.relevance_score,
                0,  # selected_for_reader
                json.dumps(candidate.metadata),
                now,
            ),
        )

        conn.commit()
        return candidate_id

    finally:
        conn.close()


def get_candidates(db_path: str, run_id: str) -> list[dict[str, Any]]:
    """
    Get all paper candidates for a run.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        List of candidate dictionaries.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM paper_candidates
            WHERE run_id = ?
            ORDER BY created_at
            """,
            (run_id,),
        )
        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "paper_id": row["paper_id"],
                "source": row["source"],
                "title": row["title"],
                "authors": json.loads(row["authors_json"]),
                "year": row["year"],
                "venue": row["venue"],
                "abstract": row["abstract"],
                "doi": row["doi"],
                "arxiv_id": row["arxiv_id"],
                "semantic_scholar_id": row["semantic_scholar_id"],
                "zotero_item_id": row["zotero_item_id"],
                "url": row["url"],
                "pdf_url": row["pdf_url"],
                "local_pdf_path": row["local_pdf_path"],
                "citation_count": row["citation_count"],
                "relevance_score": row["relevance_score"],
                "selected_for_reader": row["selected_for_reader"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    finally:
        conn.close()


# ==================== Plan CRUD Operations ====================


def create_plan(
    db_path: str,
    run_id: str,
    phase: str,
    plan_data: dict[str, Any],
) -> str:
    """
    Create a research plan record.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        phase: Plan phase ("initial" or "candidate_selection").
        plan_data: Plan data dictionary.

    Returns:
        plan_id: The generated plan ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    plan_id = f"plan_{uuid.uuid4().hex[:16]}"

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Get next version number for this run
        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM research_plans WHERE run_id = ?",
            (run_id,),
        )
        version = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO research_plans (
                id, run_id, version, phase, plan_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                run_id,
                version,
                phase,
                json.dumps(plan_data),
                now,
            ),
        )

        conn.commit()
        return plan_id

    finally:
        conn.close()


def get_plans_by_run(db_path: str, run_id: str) -> list[dict[str, Any]]:
    """
    Get all plans for a run, ordered by version.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        List of plan dictionaries.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM research_plans
            WHERE run_id = ?
            ORDER BY version
            """,
            (run_id,),
        )
        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "version": row["version"],
                "phase": row["phase"],
                "plan_data": json.loads(row["plan_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    finally:
        conn.close()


# ==================== PaperCard and Evidence CRUD Operations ====================


def create_paper_card(
    db_path: str,
    run_id: str,
    paper_card: Any,  # PaperCard
) -> str:
    """
    Create a paper card record.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        paper_card: PaperCard instance.

    Returns:
        card_id: The generated card ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    card_id = f"card_{uuid.uuid4().hex[:16]}"

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Find the candidate_id for this paper_id
        cursor.execute(
            "SELECT id FROM paper_candidates WHERE run_id = ? AND paper_id = ?",
            (run_id, paper_card.paper_id),
        )
        candidate_row = cursor.fetchone()

        if candidate_row is None:
            raise ValueError(f"No candidate found for paper_id={paper_card.paper_id} in run_id={run_id}")

        candidate_id = candidate_row[0]

        cursor.execute(
            """
            INSERT INTO paper_cards (
                id, run_id, paper_id, candidate_id, status, extraction_mode,
                title, bibliographic_json, research_problem, method,
                datasets_json, metrics_json, key_results_json, limitations_json,
                assumptions_json, future_work_json, claims_json, evidence_json,
                error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                run_id,
                paper_card.paper_id,
                candidate_id,
                paper_card.status,
                paper_card.extraction_mode,
                paper_card.title,
                json.dumps(paper_card.bibliographic_metadata, ensure_ascii=False),
                paper_card.research_problem,
                paper_card.method,
                json.dumps(paper_card.datasets, ensure_ascii=False),
                json.dumps(paper_card.metrics, ensure_ascii=False),
                json.dumps(paper_card.key_results, ensure_ascii=False),
                json.dumps(paper_card.limitations, ensure_ascii=False),
                json.dumps(paper_card.assumptions, ensure_ascii=False),
                json.dumps(paper_card.future_work, ensure_ascii=False),
                json.dumps(paper_card.claims, ensure_ascii=False),
                json.dumps(paper_card.evidence, ensure_ascii=False),
                paper_card.error,
                now,
                now,
            ),
        )

        conn.commit()
        return card_id

    finally:
        conn.close()


def create_evidence(
    db_path: str,
    run_id: str,
    paper_id: str,
    evidence: dict[str, Any],
) -> str:
    """
    Create an evidence record.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        paper_id: Paper ID.
        evidence: Evidence dictionary with fields:
            - snippet (required): Evidence text snippet.
            - section (optional): Section name.
            - page (optional): Page number.
            - source_url (optional): Source URL.
            - evidence_type (required): Type of evidence.
            - confidence (optional): Confidence score.
            - metadata (optional): Additional metadata.

    Returns:
        evidence_id: The generated evidence ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    evidence_id = f"evid_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Find the paper_card_id for this paper_id
        cursor.execute(
            "SELECT id FROM paper_cards WHERE run_id = ? AND paper_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id, paper_id),
        )
        card_row = cursor.fetchone()

        if card_row is None:
            raise ValueError(f"No paper card found for paper_id={paper_id} in run_id={run_id}")

        paper_card_id = card_row[0]

        cursor.execute(
            """
            INSERT INTO paper_evidence (
                id, run_id, paper_id, paper_card_id, claim_id,
                snippet, section, page, source_url, evidence_type,
                confidence, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                run_id,
                paper_id,
                paper_card_id,
                evidence.get("claim_id"),
                evidence["snippet"],
                evidence.get("section"),
                evidence.get("page"),
                evidence.get("source_url"),
                evidence["evidence_type"],
                evidence.get("confidence"),
                json.dumps(evidence.get("metadata", {}), ensure_ascii=False),
            ),
        )

        conn.commit()
        return evidence_id

    finally:
        conn.close()


def get_paper_cards(db_path: str, run_id: str) -> list[dict[str, Any]]:
    """
    Get all paper cards for a run.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        List of paper card dictionaries.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM paper_cards
            WHERE run_id = ?
            ORDER BY created_at
            """,
            (run_id,),
        )
        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "paper_id": row["paper_id"],
                "candidate_id": row["candidate_id"],
                "status": row["status"],
                "extraction_mode": row["extraction_mode"],
                "title": row["title"],
                "bibliographic_metadata": json.loads(row["bibliographic_json"]),
                "research_problem": row["research_problem"],
                "method": row["method"],
                "datasets": json.loads(row["datasets_json"]),
                "metrics": json.loads(row["metrics_json"]),
                "key_results": json.loads(row["key_results_json"]),
                "limitations": json.loads(row["limitations_json"]),
                "assumptions": json.loads(row["assumptions_json"]),
                "future_work": json.loads(row["future_work_json"]),
                "claims": json.loads(row["claims_json"]),
                "evidence": json.loads(row["evidence_json"]),
                "error": row["error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    finally:
        conn.close()


def get_evidence(
    db_path: str,
    run_id: str,
    paper_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get evidence records for a run, optionally filtered by paper_id.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        paper_id: Optional paper ID to filter by.

    Returns:
        List of evidence dictionaries.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        if paper_id is not None:
            cursor.execute(
                """
                SELECT * FROM paper_evidence
                WHERE run_id = ? AND paper_id = ?
                ORDER BY id
                """,
                (run_id, paper_id),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM paper_evidence
                WHERE run_id = ?
                ORDER BY id
                """,
                (run_id,),
            )

        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "paper_id": row["paper_id"],
                "paper_card_id": row["paper_card_id"],
                "claim_id": row["claim_id"],
                "snippet": row["snippet"],
                "section": row["section"],
                "page": row["page"],
                "source_url": row["source_url"],
                "evidence_type": row["evidence_type"],
                "confidence": row["confidence"],
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]

    finally:
        conn.close()


# ==================== Report CRUD Operations ====================


def save_report(
    db_path: str,
    run_id: str,
    markdown: str,
    template_version: str,
) -> str:
    """
    Save or update a research report for a run.

    Each run can have one current report. If a report already exists for the run_id,
    it will be updated. Otherwise, a new report is created.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        markdown: Report markdown content (UTF-8, Chinese preserved).
        template_version: Template version identifier.

    Returns:
        report_id: The report ID (existing or newly created).
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Check if report exists for this run_id
        cursor.execute(
            "SELECT id FROM research_reports WHERE run_id = ?",
            (run_id,),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing report
            report_id = existing[0]
            cursor.execute(
                """
                UPDATE research_reports
                SET markdown = ?, template_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (markdown, template_version, now, report_id),
            )
        else:
            # Create new report
            report_id = f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
            cursor.execute(
                """
                INSERT INTO research_reports (
                    id, run_id, status, markdown, template_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (report_id, run_id, "draft", markdown, template_version, now, now),
            )

        conn.commit()
        return report_id

    finally:
        conn.close()


def get_report(db_path: str, run_id: str) -> dict[str, Any] | None:
    """
    Get the research report for a run.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        Report dictionary with id, run_id, status, markdown, template_version,
        created_at, updated_at, or None if no report exists.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM research_reports
            WHERE run_id = ?
            """,
            (run_id,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "status": row["status"],
            "markdown": row["markdown"],
            "template_version": row["template_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    finally:
        conn.close()


def save_claims(
    db_path: str,
    run_id: str,
    report_id: str,
    claims: list[dict[str, Any]],
) -> None:
    """
    Save report claims in batch.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        report_id: Report ID.
        claims: List of claim dictionaries with fields:
            - claim_text: str
            - claim_type: str
            - citation_ids: list[str]
            - evidence_ids: list[str]
            - verification_status: str
            - verification_reason: str
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        for idx, claim in enumerate(claims):
            # Add index to ensure unique IDs when batch inserting
            claim_id = f"claim_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}_{idx}"
            cursor.execute(
                """
                INSERT INTO report_claims (
                    id, run_id, report_id, claim_text, claim_type,
                    citation_ids_json, evidence_ids_json, verification_status,
                    verification_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    run_id,
                    report_id,
                    claim["claim_text"],
                    claim["claim_type"],
                    json.dumps(claim["citation_ids"], ensure_ascii=False),
                    json.dumps(claim["evidence_ids"], ensure_ascii=False),
                    claim["verification_status"],
                    claim["verification_reason"],
                    now,
                ),
            )

        conn.commit()

    finally:
        conn.close()


def get_claims(db_path: str, run_id: str) -> list[dict[str, Any]]:
    """
    Get all report claims for a run.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        List of claim dictionaries with all fields.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM report_claims
            WHERE run_id = ?
            ORDER BY created_at
            """,
            (run_id,),
        )
        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "report_id": row["report_id"],
                "claim_text": row["claim_text"],
                "claim_type": row["claim_type"],
                "citation_ids": json.loads(row["citation_ids_json"]),
                "evidence_ids": json.loads(row["evidence_ids_json"]),
                "verification_status": row["verification_status"],
                "verification_reason": row["verification_reason"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    finally:
        conn.close()


def get_claim_summary(db_path: str, run_id: str) -> dict[str, int]:
    """
    Get claim verification status summary for a run.

    Aggregates claim counts by verification_status.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        Dictionary with counts for each verification status:
        {
            "supported": int,
            "weak": int,
            "unverified": int,
            "numeric_trace_missing": int,
            "conflict_detected": int,
            "total": int,
        }
    """
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT verification_status, COUNT(*) as count
            FROM report_claims
            WHERE run_id = ?
            GROUP BY verification_status
            """,
            (run_id,),
        )
        rows = cursor.fetchall()

        # Initialize all statuses to 0
        summary = {
            "supported": 0,
            "weak": 0,
            "unverified": 0,
            "numeric_trace_missing": 0,
            "conflict_detected": 0,
            "total": 0,
        }

        # Populate with actual counts
        for row in rows:
            status = row[0]
            count = row[1]
            if status in summary:
                summary[status] = count
                summary["total"] += count

        return summary

    finally:
        conn.close()
