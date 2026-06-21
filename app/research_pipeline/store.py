"""
Research Pipeline Store

管理 pipeline 状态的持久化存储。
"""

import sqlite3
from pathlib import Path


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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")

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
