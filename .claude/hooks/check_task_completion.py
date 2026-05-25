#!/usr/bin/env python3
"""Stop hook: ensure the visible Claude task checklist is completed before stopping.

This hook is intentionally lightweight and project-specific. It checks:
1. `.claude/tasks/current-tasks.md` has no unchecked `- [ ]` items.
2. The Phase 2 section specifically has no unchecked items.
3. Does not inspect git state. Git cleanliness is task-specific and should be
   checked by Claude when relevant, not by a global Stop hook.

Exit codes:
- 0: allow stop
- 2: block stop with JSON reason
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / ".claude" / "tasks" / "current-tasks.md"


def _block(reason: str) -> None:
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": reason,
                "continue": False,
                "stopReason": reason,
            },
            ensure_ascii=False,
        )
    )
    sys.exit(2)


def _allow(message: str = "Task completion checks passed.") -> None:
    print(json.dumps({"systemMessage": message}, ensure_ascii=False))
    sys.exit(0)


def _phase2_section(text: str) -> str:
    start = text.find("## Week 3-4: Phase 2")
    if start == -1:
        return ""
    end = text.find("## Week 5-6: Phase 3", start)
    if end == -1:
        return text[start:]
    return text[start:end]


def main() -> None:
    # Consume stdin so Claude Code hook plumbing is happy; content is not needed.
    try:
        _ = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        pass

    if not TASKS.exists():
        _block(f"Missing task checklist: {TASKS.relative_to(ROOT)}")

    text = TASKS.read_text(encoding="utf-8")
    unchecked_all = [line.strip() for line in text.splitlines() if line.startswith("- [ ]")]
    if unchecked_all:
        sample = "\n".join(unchecked_all[:8])
        _block(f"Task checklist still has {len(unchecked_all)} unchecked item(s):\n{sample}")

    phase2 = _phase2_section(text)
    if not phase2:
        _block("Could not locate Phase 2 section in .claude/tasks/current-tasks.md")
    unchecked_phase2 = [line.strip() for line in phase2.splitlines() if line.startswith("- [ ]")]
    if unchecked_phase2:
        sample = "\n".join(unchecked_phase2[:8])
        _block(f"Phase 2 still has {len(unchecked_phase2)} unchecked item(s):\n{sample}")

    _allow()


if __name__ == "__main__":
    main()
