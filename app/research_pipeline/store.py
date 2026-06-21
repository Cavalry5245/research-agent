"""
Research Pipeline Store

管理 pipeline 状态的持久化存储。
"""

import json
import sqlite3
from datetime import datetime
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
    now = datetime.utcnow().isoformat()
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"

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
    Get detailed information about a run including stages and events.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        Dictionary with run details, stages, and events, or None if not found.
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
        List of run summaries with run_id, status, created_at.
    """
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, status, created_at
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
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

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
    now = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
    event_id = f"event_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
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
