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

    # Vector store
    vector_store: str = "chroma"
    chroma_persist_dir: str = "app/storage/vector_db"

    # Storage paths
    upload_dir: str = "app/storage/papers"
    note_dir: str = "app/storage/notes"
    metadata_dir: str = "app/storage/metadata"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
