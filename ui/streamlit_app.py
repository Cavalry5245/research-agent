import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.schemas import Chunk, PaperParseResult, QARequest, SourceItem
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

st.set_page_config(page_title="ResearchAgent", page_icon="📄", layout="wide")


# ── Cached resources ──────────────────────────────────────────────────────────


@st.cache_resource
def get_vector_store():
    return VectorStore()


@st.cache_resource
def get_embedding_client():
    return EmbeddingClient()


@st.cache_resource
def get_llm_client():
    return LLMClient()


# ── Helpers ───────────────────────────────────────────────────────────────────


def refresh_papers():
    papers = list_papers(settings.metadata_dir)
    st.session_state["papers"] = papers
    st.session_state["paper_ids"] = [p["paper_id"] for p in papers]


def load_paper_options():
    papers = list_papers(settings.metadata_dir)
    options = {p["paper_id"]: p["title"][:60] for p in papers}
    return options, papers


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📄 ResearchAgent")
    st.caption("论文阅读与实验分析助手")

    st.divider()
    tab = st.radio("导航", ["📤 论文上传", "📝 笔记生成", "💬 论文问答", "📊 论文对比", "🗄️ 知识库"], label_visibility="collapsed")

    st.divider()

    # Status
    st.subheader("系统状态")
    if settings.llm_api_key:
        st.success("LLM API Key 已配置")
    else:
        st.warning("LLM API Key 未配置 — 在 .env 中设置 LLM_API_KEY")

    try:
        emb = get_embedding_client()
        st.success(f"Embedding: {emb.model_name}")
    except Exception:
        st.warning("Embedding 模型未就绪")

    vs = get_vector_store()
    st.caption(f"已索引 chunks: {vs.count()}")

    st.divider()
    st.caption(f"uvicorn → :8000  |  streamlit → :8501")


# ── Tab 1: Upload ─────────────────────────────────────────────────────────────

if tab == "📤 论文上传":
    st.header("📤 上传论文 PDF")

    uploaded = st.file_uploader("选择 PDF 论文文件", type=["pdf"], key="pdf_uploader")

    if uploaded:
        with st.spinner("上传并解析中..."):
            os.makedirs(settings.upload_dir, exist_ok=True)
            paper_id = generate_paper_id(settings.upload_dir)

            storage_path = os.path.join(settings.upload_dir, uploaded.name)
            if os.path.exists(storage_path):
                name, ext = os.path.splitext(uploaded.name)
                storage_path = os.path.join(settings.upload_dir, f"{name}__new{ext}")

            with open(storage_path, "wb") as f:
                f.write(uploaded.getbuffer())

            result = parse_pdf(storage_path, paper_id)
            save_parse_result(result, settings.metadata_dir)

            st.success(f"✅ 上传并解析成功！")
            st.json({
                "paper_id": paper_id,
                "filename": uploaded.name,
                "title": result.title,
                "sections": len(result.sections),
                "chars": len(result.full_text),
            })

    st.divider()
    st.subheader("已上传论文")

    if st.button("刷新列表"):
        pass

    options, papers = load_paper_options()
    if not papers:
        st.info("暂无已上传论文")
    else:
        for p in papers:
            with st.expander(f"{p['paper_id']} — {p['title'][:80]}"):
                st.caption(f"ID: {p['paper_id']}")
                st.caption(f"摘要: {p['abstract'][:200]}...")


# ── Tab 2: Notes ─────────────────────────────────────────────────────────────


elif tab == "📝 笔记生成":
    st.header("📝 生成论文笔记")

    options, papers = load_paper_options()
    if not papers:
        st.warning("请先上传论文 PDF")
    else:
        selected_id = st.selectbox(
            "选择论文",
            list(options.keys()),
            format_func=lambda pid: f"{pid} — {options[pid]}",
            key="note_select",
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📖 重新解析", use_container_width=True, key="btn_reparse"):
                with st.spinner("解析中..."):
                    try:
                        from app.services.pdf_parser import find_pdf_path
                        pdf_path = find_pdf_path(selected_id, settings.upload_dir, settings.metadata_dir)
                        result = parse_pdf(pdf_path, selected_id)
                        save_parse_result(result, settings.metadata_dir)
                        st.success("解析完成")
                    except Exception as e:
                        st.error(f"解析失败: {e}")

        with col2:
            if st.button("🤖 生成笔记", use_container_width=True, type="primary", key="btn_generate"):
                with st.spinner("LLM 生成笔记中（可能需要 30-60 秒）..."):
                    llm = get_llm_client()
                    try:
                        content = generate_note(selected_id, llm_client=llm)
                        note_path = save_markdown(selected_id, content, settings.note_dir)
                        st.session_state["note_content"] = content
                        st.session_state["note_path"] = note_path
                        st.success(f"笔记已生成: {note_path}")
                    except Exception as e:
                        st.error(f"生成失败: {e}")

        st.divider()

        if "note_content" in st.session_state:
            st.markdown(st.session_state["note_content"])

            st.download_button(
                label="📥 下载 Markdown",
                data=st.session_state["note_content"],
                file_name=f"{selected_id}_note.md",
                mime="text/markdown",
                key="dl_note",
            )


# ── Tab 3: QA ─────────────────────────────────────────────────────────────────


elif tab == "💬 论文问答":
    st.header("💬 论文问答")

    options, papers = load_paper_options()

    qa_scope = st.radio(
        "检索范围",
        ["全库问答", "单篇论文"],
        horizontal=True,
        key="qa_scope",
    )

    selected_paper = None
    if qa_scope == "单篇论文":
        if not papers:
            st.warning("请先上传论文并入库")
        else:
            selected_paper = st.selectbox(
                "选择论文",
                list(options.keys()),
                format_func=lambda pid: f"{pid} — {options[pid]}",
                key="qa_paper_select",
            )

    question = st.text_area("输入问题", placeholder="例如：这篇论文的核心创新点是什么？", key="qa_question")
    top_k = st.slider("检索片段数", 1, 10, 3, key="qa_topk")

    if st.button("🔍 提问", type="primary", disabled=not question, key="btn_qa"):
        if not question.strip():
            st.warning("请输入问题")
        else:
            with st.spinner("检索 + 推理中..."):
                try:
                    llm_client = LLMClient()
                    embedding_client = EmbeddingClient()
                    result = answer_question(
                        question=question.strip(),
                        vector_store=get_vector_store(),
                        embedding_client=embedding_client,
                        llm_client=llm_client,
                        paper_id=selected_paper,
                        top_k=top_k,
                    )

                    st.subheader("回答")
                    st.markdown(result["answer"])

                    if result["sources"]:
                        st.divider()
                        st.subheader("依据片段")
                        for i, src in enumerate(result["sources"], 1):
                            with st.expander(f"来源 {i}: {src['paper_id']} / {src['section']}"):
                                st.caption(f"Chunk: {src['chunk_id']}")
                                st.caption(f"论文: {src['title']}")
                                st.text(src["content"])
                except Exception as e:
                    st.error(f"问答失败: {e}")


# ── Tab 5: Compare ────────────────────────────────────────────────────────────


elif tab == "📊 论文对比":
    st.header("📊 多论文对比")

    options, papers = load_paper_options()

    if len(papers) < 2:
        st.warning("请先上传至少 2 篇论文")
    else:
        selected_ids = st.multiselect(
            "选择要对比的论文 (2–5 篇)",
            list(options.keys()),
            format_func=lambda pid: f"{pid} — {options[pid]}",
            key="compare_select",
        )

        selected_count = len(selected_ids)
        if selected_count > 5:
            st.error("最多支持 5 篇论文对比")
        elif selected_count >= 2:
            if st.button("📊 生成对比表", type="primary", key="btn_compare"):
                with st.spinner(f"对比 {selected_count} 篇论文中..."):
                    try:
                        llm = get_llm_client()
                        content = compare_papers(
                            selected_ids,
                            settings.metadata_dir,
                            llm_client=llm,
                        )
                        output_path = save_compare_result(content, settings.note_dir)
                        st.session_state["compare_content"] = content
                        st.session_state["compare_path"] = output_path
                        st.success(f"对比结果已保存: {output_path}")
                    except Exception as e:
                        st.error(f"对比失败: {e}")

        st.divider()

        if "compare_content" in st.session_state:
            st.markdown(st.session_state["compare_content"])

            st.download_button(
                label="📥 下载对比结果",
                data=st.session_state["compare_content"],
                file_name=os.path.basename(st.session_state.get("compare_path", "compare.md")),
                mime="text/markdown",
                key="dl_compare",
            )
        elif selected_count < 2:
            st.info("请选择 2–5 篇论文后点击生成")


# ── Tab 6: Knowledge Base ─────────────────────────────────────────────────────


elif tab == "🗄️ 知识库":
    st.header("🗄️ 知识库管理")

    st.subheader("论文入库")
    options, papers = load_paper_options()

    if not papers:
        st.warning("请先上传论文 PDF")
    else:
        col1, col2 = st.columns([3, 1])

        with col1:
            index_paper_id = st.selectbox(
                "选择要入库的论文",
                list(options.keys()),
                format_func=lambda pid: f"{pid} — {options[pid]}",
                key="kb_select",
            )

        with col2:
            st.write("")
            st.write("")
            if st.button("📥 索引到向量库", use_container_width=True, type="primary", key="btn_index"):
                with st.spinner("切块 + 向量化 + 写入中..."):
                    try:
                        data = load_parsed_result(index_paper_id, settings.metadata_dir)
                        parsed = PaperParseResult(**data)
                        chunks = chunk_paper(parsed)

                        if not chunks:
                            st.error("论文内容为空，无法索引")
                        else:
                            emb_client = get_embedding_client()
                            embeddings = emb_client.embed_texts([c.content for c in chunks])
                            get_vector_store().add_chunks(chunks, embeddings)
                            st.success(f"✅ 已索引 {len(chunks)} 个 chunks")
                    except Exception as e:
                        st.error(f"入库失败: {e}")

    st.divider()
    st.subheader("向量库状态")

    vs = get_vector_store()
    st.metric("已索引 chunks", vs.count())

    if st.button("🔄 刷新"):
        st.rerun()
