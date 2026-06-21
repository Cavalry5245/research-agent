"""
Research Pipeline Events

定义 pipeline 执行过程中的事件类型和处理。
"""

from typing import Any

from app.research_pipeline import store


def write_stage_start_event(
    db_path: str,
    run_id: str,
    stage: str,
    message: str = "",
) -> str:
    """
    Write a stage start event.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name.
        message: Event message (default: "Stage {stage} started").

    Returns:
        event_id: The generated event ID.
    """
    if not message:
        message = f"Stage {stage} started"

    return store.append_event(
        db_path=db_path,
        run_id=run_id,
        stage=stage,
        level="info",
        message=message,
        payload={},
    )


def write_stage_complete_event(
    db_path: str,
    run_id: str,
    stage: str,
    message: str = "",
    payload: dict[str, Any] | None = None,
) -> str:
    """
    Write a stage completion event.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name.
        message: Event message (default: "Stage {stage} completed").
        payload: Optional event payload with stage results.

    Returns:
        event_id: The generated event ID.
    """
    if not message:
        message = f"Stage {stage} completed"

    return store.append_event(
        db_path=db_path,
        run_id=run_id,
        stage=stage,
        level="info",
        message=message,
        payload=payload or {},
    )


def write_stage_progress_event(
    db_path: str,
    run_id: str,
    stage: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """
    Write a stage progress event.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name.
        message: Progress message.
        payload: Optional event payload with progress details.

    Returns:
        event_id: The generated event ID.
    """
    return store.append_event(
        db_path=db_path,
        run_id=run_id,
        stage=stage,
        level="info",
        message=message,
        payload=payload or {},
    )


def write_stage_error_event(
    db_path: str,
    run_id: str,
    stage: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """
    Write a stage error event.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name.
        message: Error message.
        payload: Optional event payload with error details.

    Returns:
        event_id: The generated event ID.
    """
    return store.append_event(
        db_path=db_path,
        run_id=run_id,
        stage=stage,
        level="error",
        message=message,
        payload=payload or {},
    )


def write_debug_event(
    db_path: str,
    run_id: str,
    stage: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """
    Write a debug event.

    Args:
        db_path: Path to SQLite database file.
        run_id: Run ID.
        stage: Stage name.
        message: Debug message.
        payload: Optional event payload with debug details.

    Returns:
        event_id: The generated event ID.
    """
    return store.append_event(
        db_path=db_path,
        run_id=run_id,
        stage=stage,
        level="debug",
        message=message,
        payload=payload or {},
    )
