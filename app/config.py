from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.example.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # Embedding
    embedding_provider: str = "local"
    embedding_model: str = "m3e-base"
    embedding_device: str = "auto"
    embedding_batch_size: int = 32

    # Vector store
    vector_store: str = "chroma"
    chroma_persist_dir: str = "app/storage/vector_db"

    # Storage paths
    upload_dir: str = "app/storage/papers"
    note_dir: str = "app/storage/notes"
    metadata_dir: str = "app/storage/metadata"

    # Integrations
    enable_zotero: bool = False
    zotero_local: bool = True
    zotero_mcp_command: str = ""
    zotero_data_dir: str = ""
    zotero_library_id: str = "0"
    zotero_library_type: str = "user"

    # Obsidian
    obsidian_vault_root: str = "app/storage/knowledge_packs"

    # MCP Configuration
    mcp_enabled: bool = True
    mcp_startup_timeout: float = 10.0
    mcp_health_check_interval: float = 30.0
    mcp_tool_timeout: float = 30.0

    # Zotero MCP
    zotero_mcp_enabled: bool = True
    zotero_mcp_auto_install: bool = False
    semantic_scholar_mcp_enabled: bool = False
    semantic_scholar_api_key: str = ""
    arxiv_mcp_enabled: bool = False
    research_agent_mcp_enabled: bool = True

    # External multi-source paper search MCP server (paper-search-mcp).
    # Disabled by default; when enabled, prefer disabling the two minimal
    # arXiv / Semantic Scholar servers above to avoid duplicate requests.
    paper_search_mcp_enabled: bool = False
    paper_search_mcp_command: str = "python -m app.mcp.paper_search_server"
    paper_search_mcp_save_dir: str = "app/storage/papers"

    # Phase 4: Rerank
    enable_rerank: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_k: int = 5
    rerank_recall_top_k: int = 20

    # Phase 4: Retriever (vector / bm25 / hybrid)
    retriever: str = "vector"
    hybrid_alpha: float = 0.5
    hybrid_recall_top_k: int = 20

    # Phase 4: Query optimization
    query_rewrite: str = "off"
    hyde: str = "off"

    # PDF RAG 父子文档配置
    pdf_parse_mode: str = "structured"
    chunk_strategy: str = "parent_child_sliding_window"
    parent_doc_store: str = "json"
    parent_doc_dir: str = "app/storage/parent_docs"
    child_chunk_size: int = 500
    child_chunk_overlap: int = 100
    preserve_page_citations: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
