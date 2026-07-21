import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)

_MODULE_AVAILABLE = None
_MODULE_IMPORT_ERROR = None
BGE_MODEL_ALIASES = {
    "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
    "bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
    "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
    "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
    "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
    "bge-m3": "BAAI/bge-m3",
    "m3e-base": "moka-ai/m3e-base",
    "m3e-small": "moka-ai/m3e-small",
    "m3e-large": "moka-ai/m3e-large",
}
EMBEDDING_LOAD_RETRIES = 2
EMBEDDING_LOAD_BACKOFF_SECONDS = 1.0
CLOSED_CLIENT_MARKERS = (
    "client has been closed",
    "client is closed",
    "cannot send a request, as the client has been closed",
)


def _check_available() -> bool:
    global _MODULE_AVAILABLE, _MODULE_IMPORT_ERROR
    if _MODULE_AVAILABLE is not None:
        return _MODULE_AVAILABLE
    try:
        import torch  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401

        _MODULE_AVAILABLE = True
        _MODULE_IMPORT_ERROR = None
    except Exception as exc:
        _MODULE_AVAILABLE = False
        _MODULE_IMPORT_ERROR = exc
    return _MODULE_AVAILABLE


def _resolve_model_name(model_name: str) -> str:
    return BGE_MODEL_ALIASES.get(model_name, model_name)


def _resolve_device(explicit_device: str | None = None) -> str:
    device = explicit_device or settings.embedding_device
    if device != "auto":
        return device

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


def _is_closed_client_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in CLOSED_CLIENT_MARKERS)


class EmbeddingClient:
    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ):
        self.model_name = model_name or settings.embedding_model
        self._resolved_model_name = _resolve_model_name(self.model_name)
        self.device = _resolve_device(device)
        self.batch_size = batch_size or settings.embedding_batch_size
        self._provider = settings.embedding_provider
        self._model = None  # local sentence-transformers model cache
        self._api_client = None  # OpenAI client, lazily built for api mode

    @property
    def provider(self) -> str:
        return self._provider

    # --- API mode (OpenAI-compatible /v1/embeddings) --------------------------
    def _ensure_api_client(self):
        if self._api_client is not None:
            return
        if not settings.embedding_base_url or not settings.embedding_api_key:
            raise RuntimeError(
                "embedding_provider=api 需配置 EMBEDDING_BASE_URL 和 EMBEDDING_API_KEY"
            )
        from openai import OpenAI

        self._api_client = OpenAI(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
        )
        logger.info(
            "Embedding API client ready: base_url_configured=%s, model=%s",
            bool(settings.embedding_base_url),
            self.model_name,
        )

    def _api_embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure_api_client()
        out: list[list[float]] = []
        # Some providers cap input batch size; chunk to be safe.
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = self._api_client.embeddings.create(
                # Keep model_name logical for collection/manifest compatibility.
                # The rebuild contract's git_head prevents resuming across alias
                # mapping/code changes, while providers receive the resolved wire ID.
                model=self._resolved_model_name,
                input=batch,
            )
            items = list(resp.data)
            indices = [getattr(item, "index", None) for item in items]
            if (
                any(type(index) is not int for index in indices)
                or len(indices) != len(batch)
                or set(indices) != set(range(len(batch)))
            ):
                raise ValueError(
                    "Embedding API response indices must be unique built-in ints "
                    "covering exactly the requested batch"
                )
            # Response data may come back out of order; sort only after validation.
            for item in sorted(items, key=lambda item: item.index):
                out.append(list(item.embedding))
        return out

    # --- local mode (sentence-transformers) -----------------------------------
    def _ensure_model(self):
        if self._model is not None:
            return
        if not _check_available():
            detail = f"原始错误: {_MODULE_IMPORT_ERROR}" if _MODULE_IMPORT_ERROR else ""
            raise RuntimeError(
                "sentence-transformers / torch 在当前环境中不可用。"
                f"{detail}"
            ) from _MODULE_IMPORT_ERROR
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(f"sentence-transformers 未安装: {e}") from e

        logger.info(
            "Loading embedding model: %s on device=%s",
            self._resolved_model_name,
            self.device,
        )
        last_error = None
        for attempt in range(1, EMBEDDING_LOAD_RETRIES + 1):
            try:
                self._model = SentenceTransformer(
                    self._resolved_model_name, device=self.device
                )
                break
            except Exception as e:
                last_error = e
                if _is_closed_client_error(e) and attempt < EMBEDDING_LOAD_RETRIES:
                    sleep_seconds = EMBEDDING_LOAD_BACKOFF_SECONDS * (
                        2 ** (attempt - 1)
                    )
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
        logger.info("Embedding model loaded, dim=%d, device=%s", dim, self.device)

    def _rebuild_model(self) -> None:
        self._model = None
        self._ensure_model()

    def _encode_with_recovery(self, texts: list[str]):
        self._ensure_model()
        try:
            return self._model.encode(
                texts, show_progress_bar=False, batch_size=self.batch_size
            )
        except RuntimeError as e:
            if not _is_closed_client_error(e):
                raise
            logger.warning(
                "Embedding model encode hit closed client, rebuilding model and retrying once"
            )
            self._rebuild_model()
            return self._model.encode(
                texts, show_progress_bar=False, batch_size=self.batch_size
            )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._provider == "api":
            return self._api_embed(texts)
        embeddings = self._encode_with_recovery(texts)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        if self._provider == "api":
            return self._api_embed([query])[0]
        return self._encode_with_recovery([query])[0].tolist()
