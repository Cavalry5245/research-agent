import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)

_MODULE_AVAILABLE = None
BGE_MODEL_ALIASES = {
    "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
    "bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
    "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
    "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
    "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
    "bge-m3": "BAAI/bge-m3",
}
EMBEDDING_LOAD_RETRIES = 2
EMBEDDING_LOAD_BACKOFF_SECONDS = 1.0
CLOSED_CLIENT_MARKERS = (
    "client has been closed",
    "client is closed",
    "cannot send a request, as the client has been closed",
)


def _check_available() -> bool:
    global _MODULE_AVAILABLE
    if _MODULE_AVAILABLE is not None:
        return _MODULE_AVAILABLE
    try:
        import torch  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401
        _MODULE_AVAILABLE = True
    except Exception:
        _MODULE_AVAILABLE = False
    return _MODULE_AVAILABLE


def _resolve_model_name(model_name: str) -> str:
    return BGE_MODEL_ALIASES.get(model_name, model_name)


def _is_closed_client_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in CLOSED_CLIENT_MARKERS)


class EmbeddingClient:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._resolved_model_name = _resolve_model_name(self.model_name)
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return
        if not _check_available():
            raise RuntimeError(
                "sentence-transformers / torch 在当前环境中不可用，"
                "请确认已安装 Visual C++ Redistributable。"
            )
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(f"sentence-transformers 未安装: {e}") from e

        logger.info("Loading embedding model: %s", self._resolved_model_name)
        last_error = None
        for attempt in range(1, EMBEDDING_LOAD_RETRIES + 1):
            try:
                self._model = SentenceTransformer(self._resolved_model_name)
                break
            except Exception as e:
                last_error = e
                if _is_closed_client_error(e) and attempt < EMBEDDING_LOAD_RETRIES:
                    sleep_seconds = EMBEDDING_LOAD_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Embedding model loader client closed on attempt %d/%d: %s. Retry in %.1fs",
                        attempt,
                        EMBEDDING_LOAD_RETRIES,
                        e,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                    continue
                raise RuntimeError(
                    f"Embedding 模型加载失败: {self._resolved_model_name}. 原始错误: {e}"
                ) from e

        if self._model is None:
            raise RuntimeError(
                f"Embedding 模型加载失败: {self._resolved_model_name}. 原始错误: {last_error}"
            ) from last_error

        dim = self._model.get_embedding_dimension()
        logger.info("Embedding model loaded, dim=%d", dim)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        self._ensure_model()
        return self._model.encode([query], show_progress_bar=False)[0].tolist()
