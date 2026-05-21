# Database and Cache Decision

## Decision

Phase 3 keeps the current file-based storage and does not introduce SQLite, SQLAlchemy, Alembic, Redis cache, or database migrations.

## Current storage model

- Uploaded PDFs: `app/storage/papers/`
- Parsed metadata JSON: `app/storage/metadata/`
- Notes and comparison reports: `app/storage/notes/`
- Vector store: Chroma persistence directory
- Task state: in-memory store or JSON-backed `FileJobStore`
- Analytics events: JSONL files under `app/storage/analytics/`
- Logs: JSONL files under `app/storage/logs/`

## Why not add a database now

- The project is still a local MVP/research demo, not a multi-user service.
- File storage makes generated artifacts easy to inspect and include in demos.
- A database migration would touch many stable paths without clear Phase 3 payoff.
- Phase 4 focuses on RAG quality, where vector-store improvements matter more than relational storage.
- Phase 5 focuses on Agent collaboration and memory; storage requirements should be revisited after memory design is concrete.

## When SQLite/PostgreSQL becomes worthwhile

Add a relational database when the project needs:

- Multi-user paper ownership
- Search/filter/sort across large paper libraries
- Durable QA history and Agent sessions
- Permission or sharing models
- Transactional task records
- Migration/version management for deployed environments

## Why not add Redis cache now

- Embedding and vector results are already persisted through Chroma.
- Note and comparison outputs are persisted as Markdown files.
- Current bottlenecks are LLM latency and retrieval quality, not repeated cache misses.
- Redis would add operational complexity in WSL/local demo usage.

## Future cache candidates

Redis or another cache becomes useful for:

- LLM response cache for repeated benchmark prompts
- Embedding cache across model experiments
- Rate-limit coordination
- Task queue backend when migrating to Celery
- Short-term Agent session state in a multi-user deployment

## Recommendation

Keep file storage for Phase 3 and revisit database/cache in Phase 5 after Agent memory requirements are finalized. If a database is added later, start with SQLite for local demo compatibility, then document a PostgreSQL migration path for production deployment.
