from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services.chroma_rebuild import (
    ChromaIndexRebuilder,
    build_contract,
    preflight_rebuild,
    redact_error,
)
from app.services.embedding_client import EmbeddingClient
from app.services.vector_backends.chroma_backend import ChromaVectorBackend


def git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    head = completed.stdout.strip()
    if not head:
        raise RuntimeError("git rev-parse HEAD returned no commit")
    return head


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify the versioned bge-m3 Chroma index."
    )
    parser.add_argument("--metadata-dir", default=settings.metadata_dir)
    parser.add_argument("--persist-dir", default=settings.chroma_persist_dir)
    parser.add_argument("--collection", default=settings.chroma_collection_name)
    parser.add_argument("--expected-source-count", type=int, default=53)
    parser.add_argument("--batch-size", type=int, default=settings.embedding_batch_size)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--base-delay", type=float, default=1.0)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--canary-only", action="store_true")
    modes.add_argument("--verify-only", action="store_true")
    return parser


def _print_configuration_presence() -> None:
    print(f"embedding_base_url_configured={bool(settings.embedding_base_url)}")
    print(f"embedding_api_key_configured={bool(settings.embedding_api_key)}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if settings.embedding_provider != "api" or settings.embedding_model != "bge-m3":
        print(
            "Rebuild requires EMBEDDING_PROVIDER=api and EMBEDDING_MODEL=bge-m3",
            file=sys.stderr,
        )
        return 2

    _print_configuration_presence()
    if not (
        isinstance(settings.embedding_base_url, str)
        and settings.embedding_base_url.strip()
        and isinstance(settings.embedding_api_key, str)
        and settings.embedding_api_key.strip()
    ):
        print(
            "Rebuild requires nonempty EMBEDDING_BASE_URL and EMBEDDING_API_KEY",
            file=sys.stderr,
        )
        return 2
    try:
        persist_dir = Path(args.persist_dir)
        manifest_path = persist_dir / f"{args.collection}.rebuild-manifest.json"
        requested_git_head = git_head()
        chunk_settings = {
            "strategy": settings.chunk_strategy,
            "size": settings.child_chunk_size,
            "overlap": settings.child_chunk_overlap,
        }
        contract = build_contract(
            collection=args.collection,
            provider="api",
            model="bge-m3",
            git_head=requested_git_head,
            schema_version=1,
            chunk_settings=chunk_settings,
        )
        preflight_rebuild(
            metadata_dir=Path(args.metadata_dir),
            manifest_path=manifest_path,
            contract=contract,
            expected_source_count=args.expected_source_count,
            require_manifest=args.verify_only,
        )
        create_if_missing = not args.verify_only
        backend = ChromaVectorBackend(
            persist_dir=str(persist_dir),
            collection_name=args.collection,
            create_if_missing=create_if_missing,
            require_ready=False,
            initial_metadata=(
                {
                    "build_status": "building",
                    "embedding_model": "bge-m3",
                    "schema_version": 1,
                }
                if create_if_missing
                else None
            ),
        )
        embedding_client = EmbeddingClient(
            model_name="bge-m3", batch_size=args.batch_size
        )
        rebuilder = ChromaIndexRebuilder(
            metadata_dir=Path(args.metadata_dir),
            manifest_path=persist_dir / f"{args.collection}.rebuild-manifest.json",
            backend=backend,
            embedding_client=embedding_client,
            batch_size=args.batch_size,
            max_attempts=args.max_attempts,
            base_delay=args.base_delay,
            git_head=requested_git_head,
            chunk_settings=chunk_settings,
            expected_source_count=args.expected_source_count,
        )
        if args.verify_only:
            result = rebuilder.verify(require_complete=False)
            if result.get("status") == "building":
                success = (
                    result.get("completed_paper_count", 0) >= 1
                    and result.get("paper_count", 0) >= 1
                )
            else:
                success = (
                    result.get("status") == "ready"
                    and result.get("completed_paper_count")
                    == args.expected_source_count
                    and result.get("paper_count") == args.expected_source_count
                )
        elif args.canary_only:
            result = rebuilder.run_canary()
            success = result.get("completed_paper_count", 0) >= 1
        else:
            rebuilder.run_canary()
            result = rebuilder.run_all()
            success = result.get("status") == "ready"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if success else 1
    except Exception as exc:
        print(f"Rebuild failed: {redact_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
