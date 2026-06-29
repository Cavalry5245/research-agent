import logging
import os
import tempfile

from app.agents.tools.base import BaseTool, ToolParameter, ToolResult
from app.config import settings
from app.schemas import PaperParseResult
from app.services.chunker import chunk_paper
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient
from app.services.markdown_exporter import save_markdown
from app.services.note_generator import generate_note
from app.services.paper_compare import compare_papers, save_compare_result
from app.services.paper_qa import answer_question
from app.services.pdf_parser import (
    generate_paper_id,
    list_papers,
    load_parsed_result,
    parse_pdf,
    save_parse_result,
)
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


_shared_reranker_cache: dict = {}


def _shared_cross_encoder_reranker(model_name: str):
    if model_name not in _shared_reranker_cache:
        from app.services.reranker import CrossEncoderReranker

        _shared_reranker_cache[model_name] = CrossEncoderReranker(model_name=model_name)
    return _shared_reranker_cache[model_name]


class UploadPaperTool(BaseTool):
    name = "upload_paper"
    description = "上传并解析 PDF 论文文件，返回 paper_id"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="PDF 文件的本地路径",
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            return ToolResult(success=False, error=f"文件不存在: {file_path}")

        if not file_path.lower().endswith(".pdf"):
            return ToolResult(success=False, error="只支持 PDF 文件")

        try:
            upload_dir = settings.upload_dir
            os.makedirs(upload_dir, exist_ok=True)

            paper_id = generate_paper_id(upload_dir)
            pdf_path = os.path.join(upload_dir, os.path.basename(file_path))

            if not os.path.exists(pdf_path):
                import shutil

                shutil.copy2(file_path, pdf_path)

            result = parse_pdf(pdf_path, paper_id)
            save_parse_result(result, settings.metadata_dir)

            return ToolResult(
                success=True,
                data={
                    "paper_id": paper_id,
                    "title": result.title,
                    "sections": len(result.sections),
                    "chars": len(result.full_text),
                },
            )
        except Exception as e:
            logger.exception("Upload failed")
            return ToolResult(success=False, error=str(e))


class ListPapersTool(BaseTool):
    name = "list_papers"
    description = "列出本地论文库中已解析的论文，返回 paper_id、标题和摘要预览"

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    def execute(self, **kwargs) -> ToolResult:
        try:
            papers = list_papers(settings.metadata_dir)
            return ToolResult(
                success=True,
                data={
                    "count": len(papers),
                    "papers": papers,
                },
            )
        except Exception as e:
            logger.exception("List papers failed")
            return ToolResult(success=False, error=str(e))


class GenerateNoteTool(BaseTool):
    name = "generate_note"
    description = "根据已解析的论文生成结构化中文 Markdown 阅读笔记"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="paper_id",
                type="string",
                description="论文 ID",
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        paper_id = kwargs.get("paper_id", "")
        if not paper_id:
            return ToolResult(success=False, error="缺少 paper_id")

        try:
            llm_client = LLMClient()
            content = generate_note(paper_id, llm_client=llm_client)
            note_path = save_markdown(paper_id, content, settings.note_dir)

            return ToolResult(
                success=True,
                data={
                    "paper_id": paper_id,
                    "note_path": note_path,
                    "content_length": len(content),
                },
            )
        except FileNotFoundError:
            return ToolResult(
                success=False, error=f"论文 {paper_id} 的解析结果不存在，请先上传并解析"
            )
        except Exception as e:
            logger.exception("Note generation failed")
            return ToolResult(success=False, error=str(e))


class IndexPaperTool(BaseTool):
    name = "index_paper"
    description = "将已解析的论文切块、向量化并写入向量库"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="paper_id",
                type="string",
                description="论文 ID",
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        paper_id = kwargs.get("paper_id", "")
        if not paper_id:
            return ToolResult(success=False, error="缺少 paper_id")

        try:
            data = load_parsed_result(paper_id, settings.metadata_dir)
            parsed = PaperParseResult(**data)
            chunks = chunk_paper(parsed)

            if not chunks:
                return ToolResult(success=False, error="论文内容为空，无法索引")

            embedding_client = EmbeddingClient()
            embeddings = embedding_client.embed_texts([c.content for c in chunks])

            vector_store = VectorStore()
            vector_store.add_chunks(chunks, embeddings)

            return ToolResult(
                success=True,
                data={
                    "paper_id": paper_id,
                    "chunks_indexed": len(chunks),
                    "vector_backend": vector_store.backend_name(),
                },
            )
        except FileNotFoundError:
            return ToolResult(success=False, error=f"论文 {paper_id} 的解析结果不存在")
        except Exception as e:
            logger.exception("Index failed")
            return ToolResult(success=False, error=str(e))


class QATool(BaseTool):
    name = "qa"
    description = "基于已索引的论文内容进行问答检索"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="question",
                type="string",
                description="用户问题",
            ),
            ToolParameter(
                name="paper_id",
                type="string",
                description="限定单篇论文 ID（可选）",
                required=False,
            ),
            ToolParameter(
                name="top_k",
                type="integer",
                description="检索片段数（默认 5）",
                required=False,
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        question = kwargs.get("question", "")
        paper_id = kwargs.get("paper_id")
        top_k = int(kwargs.get("top_k", 5))

        if not question:
            return ToolResult(success=False, error="缺少 question")

        try:
            from app.config import settings

            llm_client = LLMClient()
            embedding_client = EmbeddingClient()
            vector_store = VectorStore()

            reranker = None
            if settings.enable_rerank:
                from app.services.reranker import CrossEncoderReranker

                reranker = _shared_cross_encoder_reranker(settings.rerank_model)

            retriever = None
            if settings.retriever == "bm25":
                from app.services.bm25_retriever import BM25Retriever

                retriever = BM25Retriever(vector_store)
            elif settings.retriever == "hybrid":
                from app.services.bm25_retriever import BM25Retriever
                from app.services.hybrid_retriever import HybridRetriever

                retriever = HybridRetriever(
                    vector_store=vector_store,
                    embedding_client=embedding_client,
                    bm25_retriever=BM25Retriever(vector_store),
                    alpha=settings.hybrid_alpha,
                    recall_top_k=settings.hybrid_recall_top_k,
                )

            result = answer_question(
                question=question,
                vector_store=vector_store,
                embedding_client=embedding_client,
                llm_client=llm_client,
                paper_id=paper_id,
                top_k=settings.rerank_top_k if reranker else top_k,
                reranker=reranker,
                recall_top_k=settings.rerank_recall_top_k if reranker else None,
                retriever=retriever,
            )

            return ToolResult(
                success=True,
                data={
                    "question": question,
                    "answer": result["answer"],
                    "sources_count": len(result["sources"]),
                    "sources": [
                        {
                            "paper_id": s["paper_id"],
                            "title": s["title"],
                            "section": s["section"],
                        }
                        for s in result["sources"]
                    ],
                },
            )
        except Exception as e:
            logger.exception("QA failed")
            return ToolResult(success=False, error=str(e))


class ComparePapersTool(BaseTool):
    name = "compare_papers"
    description = "对多篇论文进行结构化对比分析"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="paper_ids",
                type="array",
                description="论文 ID 列表，至少 2 篇，最多 5 篇",
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        paper_ids = kwargs.get("paper_ids", [])
        if not isinstance(paper_ids, list) or len(paper_ids) < 2:
            return ToolResult(success=False, error="请提供至少 2 篇论文 ID")
        if len(paper_ids) > 5:
            return ToolResult(success=False, error="最多支持 5 篇论文对比")

        try:
            llm_client = LLMClient()
            comparison = compare_papers(
                paper_ids,
                settings.metadata_dir,
                llm_client=llm_client,
            )
            output_path = save_compare_result(comparison.markdown, settings.note_dir)

            return ToolResult(
                success=True,
                data={
                    "paper_ids": paper_ids,
                    "output_path": output_path,
                    "content_length": len(comparison.markdown),
                    "aspects_count": len(comparison.aspects),
                },
            )
        except Exception as e:
            logger.exception("Compare failed")
            return ToolResult(success=False, error=str(e))


class ExportMarkdownTool(BaseTool):
    name = "export_markdown"
    description = "导出论文笔记或对比结果为 Markdown 文件"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="paper_id",
                type="string",
                description="论文 ID（导出笔记时使用）",
                required=False,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="要导出的 Markdown 内容",
                required=False,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="导出路径（可选，默认保存到 notes 目录）",
                required=False,
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        paper_id = kwargs.get("paper_id")
        content = kwargs.get("content")
        output_path = kwargs.get("output_path")

        if not content and not paper_id:
            return ToolResult(success=False, error="请提供 paper_id 或直接传入 content")

        try:
            if output_path:
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return ToolResult(success=True, data={"output_path": output_path})

            if content:
                import uuid

                filename = f"export_{uuid.uuid4().hex[:8]}.md"
                full_path = os.path.join(settings.note_dir, filename)
                os.makedirs(settings.note_dir, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return ToolResult(success=True, data={"output_path": full_path})

            note_path = os.path.join(settings.note_dir, f"{paper_id}_note.md")
            if not os.path.isfile(note_path):
                return ToolResult(success=False, error=f"笔记文件不存在: {note_path}")

            return ToolResult(success=True, data={"output_path": note_path})
        except Exception as e:
            logger.exception("Export failed")
            return ToolResult(success=False, error=str(e))
