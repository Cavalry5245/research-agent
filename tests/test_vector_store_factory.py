from app.config import Settings


def test_vector_store_settings_have_versioned_chroma_collection():
    configured = Settings(
        _env_file=None,
        vector_store="chroma",
        chroma_persist_dir="tmp/chroma",
        chroma_collection_name="research_papers_bge_m3_v1",
    )
    assert configured.vector_store == "chroma"
    assert configured.chroma_persist_dir == "tmp/chroma"
    assert configured.chroma_collection_name == "research_papers_bge_m3_v1"
