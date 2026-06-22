"""
Run seed questions through the research pipeline.

This script creates research runs for the seed questions from the evaluation dataset,
executes them, and collects the run IDs for MVP gate report generation.
"""

import json
import os
import sys
import time
from pathlib import Path

# Set SSL certificate path to certifi bundle
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.research_pipeline import store
from app.research_pipeline.runner import PipelineRunner, create_default_agent


def load_seed_questions(seed_file: Path) -> list[dict]:
    """Load seed questions from JSONL file."""
    questions = []
    with open(seed_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def main():
    # Setup paths
    storage_root = Path(settings.metadata_dir).parent
    db_path = str(storage_root / "research_pipeline.db")
    seed_file = project_root / "app" / "evaluation" / "datasets" / "research_pipeline_seed.jsonl"

    # Initialize database
    print(f"Initializing database at {db_path}")
    store.init_db(db_path)

    # Load seed questions
    print(f"Loading seed questions from {seed_file}")
    seed_questions = load_seed_questions(seed_file)
    print(f"Loaded {len(seed_questions)} seed questions")

    # Create runner
    runner = PipelineRunner(db_path=db_path, agent_factory=create_default_agent)

    # Execute each seed question
    run_ids = []
    for i, seed_data in enumerate(seed_questions, 1):
        question = seed_data["question"]
        print(f"\n{'='*80}")
        print(f"Seed Question {i}/{len(seed_questions)}")
        print(f"Question: {question}")
        print(f"{'='*80}\n")

        # Create run
        run_id = store.create_run(
            db_path=db_path,
            question=question,
            source_mode="hybrid",
            max_reader_papers=5,
            reader_concurrency=3,
        )
        run_ids.append(run_id)
        print(f"Created run: {run_id}")

        # Execute pipeline
        start_time = time.time()
        try:
            runner.run(run_id)
            elapsed = time.time() - start_time
            print(f"\n[OK] Run {run_id} completed in {elapsed:.1f} seconds")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n[FAIL] Run {run_id} failed after {elapsed:.1f} seconds")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

        # Get final status
        detail = store.get_run_detail(db_path, run_id)
        print(f"Final status: {detail['status']}")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Completed {len(run_ids)} runs:")
    for run_id in run_ids:
        detail = store.get_run_detail(db_path, run_id)
        print(f"  - {run_id}: {detail['status']}")

    print(f"\nTo generate MVP gate report, run:")
    print(f"python -m app.evaluation.scripts.generate_mvp_gate_report \\")
    print(f"  --db-path {db_path} \\")
    print(f"  --run-ids {' '.join(run_ids)}")


if __name__ == "__main__":
    main()
