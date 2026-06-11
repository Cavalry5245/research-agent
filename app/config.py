from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.example.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # Embedding
    embedding_provider: str = "local"
    embedding_model: str = "bge-small-zh-v1.5"
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
