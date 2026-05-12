# AGENTS.md — ResearchAgent

## Project overview

AI research assistant for paper reading, note generation, RAG QA, multi-paper comparison, and Markdown export. Python + FastAPI backend, Streamlit frontend, Chroma vector store, PyMuPDF for PDF parsing, OpenAI-compatible LLM API.

## Tech stack (MVP)

| Layer | Choice |
|-------|--------|
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Frontend | Streamlit |
| PDF parsing | PyMuPDF (pymupdf) |
| LLM | OpenAI-compatible API (DeepSeek, Qwen, Ollama, etc.) |
| Vector DB | Chroma (local persistence) |
| Embedding | bge-small-zh-v1.5 / bge-m3 / OpenAI-compatible |
| Config | `.env` (python-dotenv) |
| Storage | `app/storage/` — papers, notes, vector_db, metadata |

## Dev commands

```bash
# Conda environment (recommended — ensures torch/chroma binary compatibility)
conda activate research_agent
pip install -r requirements.txt

# Optional venv fallback (use only if you are not using the conda workflow)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start FastAPI backend
uvicorn app.main:app --reload

# Start Streamlit UI
streamlit run ui/streamlit_app.py

# Run all tests
python -m pytest tests -v
```

## Environment config

Copy `.env.example` to `.env` and fill in. Required keys:

- `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`
- `VECTOR_STORE=chroma`, `CHROMA_PERSIST_DIR`
- `UPLOAD_DIR`, `NOTE_DIR`, `METADATA_DIR`

LLM calls use OpenAI-compatible `/v1/chat/completions` — set `LLM_BASE_URL` to your provider.

## Directory structure (planned)

```
app/
  main.py, config.py, schemas.py
  services/    — pdf_parser, chunker, llm_client, embedding_client,
                  vector_store, note_generator, paper_qa, paper_compare,
                  markdown_exporter
  agents/      — tools.py, research_agent.py
  prompts/     — paper_note_prompt, qa_prompt, compare_prompt
  storage/     — papers/, notes/, vector_db/, metadata/
ui/
  streamlit_app.py
docs/
tests/
```

## Development phases (first build order)

1. **Phase 1**: Project scaffold — directory structure, `.env.example`, `app/main.py`, `app/config.py`
2. **Phase 2**: PDF parsing — `app/services/pdf_parser.py` (PyMuPDF → title, abstract, sections, full_text)
3. **Phase 3**: LLM + note generation — `app/services/llm_client.py`, `note_generator.py`, `markdown_exporter.py`
4. **Phase 4**: RAG — `chunker.py`, `embedding_client.py`, `vector_store.py`, `paper_qa.py`
5. **Phase 5**: Multi-paper comparison + Streamlit UI wiring

**Important**: Do not build the agent framework, complex frontends, or multi-user features before the core `PDF → Markdown → QA` pipeline works end-to-end.

## Key conventions

- All output goes through LLM with strict prompts: Chinese output, academic tone, no fabrication, mark "原文未明确说明" when info missing
- Paper notes follow the 13-section Markdown template in `docs/MVP_REQUIREMENTS.md`
- Chunk config: `chunk_size=800`, `chunk_overlap=100`
- Paper IDs are generated as `paper_YYYYMMDD_NNN`
- Retriever must include paper_id, section name, and chunk_id in its results
- Errors must surface clear messages to the UI — never raw stack traces

## Config-driven design

All models/providers are swappable via `.env`:
- LLM provider/model can be changed without code changes
- Embedding provider/model likewise
- Vector store path configurable via `CHROMA_PERSIST_DIR`
- The project is designed to be provider-agnostic from the start

## Development constraints

- Strictly follow `docs/MVP_REQUIREMENTS.md` for phased development
- Do not skip acceptance criteria
- Complete only one well-defined task at a time
- After each change, document which files were modified and how to test
- Do not introduce complex frameworks; keep MVP simple
- First priority: `PDF → text → Markdown notes` pipeline before any agent/UI complexity
- Keep the codebase clean and organized at all times: no temporary files, no dead code, no dead files, no unnecessary folders/subfolders/files, and remove obsolete artifacts promptly when they are no longer needed
