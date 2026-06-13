import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.mcp_health import build_mcp_hub_health
from app.research_workflow.schemas import ResearchRunCreateRequest, ResearchRunOptions
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore
from app.research_workflow.zotero_intake import CollectionIntakeService, ZoteroLocalHttpClient
from app.schemas import Chunk, PaperParseResult, QARequest, SourceItem
from app.services.chunker import chunk_paper
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient
from app.services.markdown_exporter import save_markdown
from app.services.note_generator import generate_note
from app.services.paper_compare import compare_papers, save_compare_result
from app.services.paper_manager import delete_paper_assets
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


@st.cache_resource
def get_research_run_service():
    storage_root = Path(settings.metadata_dir).parent
    return ResearchRunService(
        store=FileResearchRunStore(storage_root / "research_runs.json"),
        vault_root=settings.obsidian_vault_root,
    )


@st.cache_resource
def get_collection_intake_service():
    return CollectionIntakeService(ZoteroLocalHttpClient())


@st.cache_resource
def get_paper_processing_service():
    return PaperProcessingService(
        upload_dir=settings.upload_dir,
        metadata_dir=settings.metadata_dir,
        note_dir=settings.note_dir,
        vector_store=get_vector_store(),
        embedding_client=get_embedding_client(),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


@st.cache_data(ttl=30)
def get_tool_health_status():
    storage_root = Path(settings.metadata_dir).parent
    return build_mcp_hub_health(
        service=get_research_run_service(),
        storage_root=storage_root,
    )


@st.cache_data(ttl=60)
def load_zotero_collections(limit: int = 100) -> list[dict]:
    client = ZoteroLocalHttpClient()
    return [collection.model_dump() for collection in client.list_collections(limit=limit)]


def format_zotero_collection_option(collection: dict) -> str:
    label = f"{collection.get('name') or collection.get('key')} ({collection.get('key')})"
    if collection.get("num_items") is not None:
        label = f"{label}, {collection['num_items']} items"
    return label


def refresh_papers():
    papers = list_papers(settings.metadata_dir)
    st.session_state["papers"] = papers
    st.session_state["paper_ids"] = [p["paper_id"] for p in papers]


def load_paper_options():
    papers = list_papers(settings.metadata_dir)
    options = {p["paper_id"]: p["title"][:60] for p in papers}
    return options, papers


def save_uploaded_files(uploaded_files) -> list[dict]:
    os.makedirs(settings.upload_dir, exist_ok=True)
    saved_files = []

    for uploaded in uploaded_files:
        paper_id = generate_paper_id(settings.upload_dir)
        storage_path = os.path.join(settings.upload_dir, uploaded.name)
        if os.path.exists(storage_path):
            name, ext = os.path.splitext(uploaded.name)
            storage_path = os.path.join(settings.upload_dir, f"{name}__new{ext}")

        with open(storage_path, "wb") as f:
            f.write(uploaded.getbuffer())

        saved_files.append(
            {
                "paper_id": paper_id,
                "filename": uploaded.name,
                "storage_path": storage_path,
            }
        )

    return saved_files


def parse_saved_files(saved_files: list[dict]) -> list[dict]:
    parsed_results = []

    for item in saved_files:
        result = parse_pdf(item["storage_path"], item["paper_id"])
        save_parse_result(result, settings.metadata_dir)
        parsed_results.append(
            {
                "paper_id": item["paper_id"],
                "filename": item["filename"],
                "title": result.title,
                "sections": len(result.sections),
                "chars": len(result.full_text),
            }
        )

    return parsed_results


def format_task_status(job: dict) -> str:
    labels = {
        "queued": "排队中",
        "running": "执行中",
        "completed": "已完成",
        "failed": "失败",
        "cancelled": "已取消",
    }
    status = labels.get(job.get("status", ""), job.get("status", "unknown"))
    progress = int(float(job.get("progress", 0.0)) * 100)
    job_type = job.get("job_type", "task")
    error = job.get("error")
    if error:
        return f"{job_type}: {status} ({progress}%) — {error}"
    return f"{job_type}: {status} ({progress}%)"


def index_parsed_files(saved_files: list[dict]) -> list[dict]:
    indexed_results = []
    vector_store = get_vector_store()

    for item in saved_files:
        parsed_data = load_parsed_result(item["paper_id"], settings.metadata_dir)
        parsed = PaperParseResult(**parsed_data)
        chunks = chunk_paper(parsed)

        if not chunks:
            indexed_results.append(
                {
                    "paper_id": item["paper_id"],
                    "filename": item["filename"],
                    "status": "skipped_empty",
                    "chunks_indexed": 0,
                }
            )
            continue

        embedding_client = get_embedding_client()
        embeddings = embedding_client.embed_texts([chunk.content for chunk in chunks])
        vector_store.add_chunks(chunks, embeddings)
        indexed_results.append(
            {
                "paper_id": item["paper_id"],
                "filename": item["filename"],
                "status": "indexed",
                "chunks_indexed": len(chunks),
                "embedding_device": embedding_client.device,
                "embedding_batch_size": embedding_client.batch_size,
                "vector_backend": vector_store.backend_name(),
                "vector_store_path": vector_store.metadata()["store_path"],
                "vector_chunk_total": vector_store.metadata()["chunk_count"],
            }
        )

    return indexed_results


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📄 ResearchAgent")
    st.caption("论文阅读与实验分析助手")

    st.divider()
    tab = st.radio(
        "导航",
        [
            "Research Workflow",
            "📤 论文上传",
            "📝 笔记生成",
            "💬 论文问答",
            "📊 论文对比",
            "🗄️ 知识库",
            "🤖 Agent 助手",
            "🔍 Agent 监控",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    # Status
    st.subheader("系统状态")
    if settings.llm_api_key:
        st.success("LLM API Key 已配置")
    else:
        st.warning("LLM API Key 未配置 — 在 .env 中设置 LLM_API_KEY")

    try:
        emb = get_embedding_client()
        st.success(
            f"Embedding: {emb.model_name} @ {emb.device} | batch={emb.batch_size}"
        )
    except Exception:
        st.warning("Embedding 模型未就绪")

    vs = get_vector_store()
    vs_meta = vs.metadata()
    st.caption(f"已索引 chunks: {vs.count()} | 向量后端: {vs_meta['backend']}")

    st.divider()
    st.caption(f"uvicorn → :8888  |  streamlit → :8501")


# ── Tab 1: Upload ─────────────────────────────────────────────────────────────

if tab == "Research Workflow":
    st.header("Research Workflow")
    st.caption("Start from a Zotero collection and initialize a ResearchAgent knowledge pack.")

    service = get_research_run_service()
    selected_research_run_id = st.session_state.get("selected_research_run_id")

    st.subheader("MCP Hub")
    for tool in get_tool_health_status():
        tool_name = tool.get("tool_name", "unknown")
        provider = tool.get("provider", "unknown")
        available = bool(tool.get("available"))
        fallback_active = bool(tool.get("fallback_active"))
        fallback_available = bool(tool.get("fallback_available"))
        message = tool.get("message", "")
        state = "available" if available else "unavailable"
        if fallback_active:
            state = "fallback active"
        fallback = "fallback available" if fallback_available else "no fallback"
        st.caption(f"{tool_name} ({provider}): {state}, {fallback}. {message}")
    st.caption("MCP Hub shows real server state, tool(s) discovered, and fallback activity.")
    st.caption("ResearchAgent MCP Server, Semantic Scholar, arXiv, Zotero, and Obsidian status are shown above.")

    if st.button("Load Zotero Collections", use_container_width=True):
        try:
            load_zotero_collections.clear()
            st.session_state["zotero_collections"] = load_zotero_collections()
            st.session_state["zotero_collection_selector"] = 0
        except Exception as exc:
            st.error(
                "Unable to load Zotero Collections. "
                "Please confirm Zotero is open and Local API port 23119 is reachable. "
                f"Details: {exc}"
            )
        else:
            if st.session_state["zotero_collections"]:
                st.success(
                    f"Loaded {len(st.session_state['zotero_collections'])} Zotero collections."
                )
            else:
                st.warning("No Zotero collections were returned. Manual input is still available.")

    zotero_collections = st.session_state.get("zotero_collections", [])
    selected_collection = None
    if zotero_collections:
        selected_index = st.session_state.get("zotero_collection_selector", 0)
        if selected_index not in range(len(zotero_collections)):
            st.session_state["zotero_collection_selector"] = 0
        selected_collection_index = st.selectbox(
            "Zotero Collection",
            range(len(zotero_collections)),
            format_func=lambda index: format_zotero_collection_option(
                zotero_collections[index]
            ),
            key="zotero_collection_selector",
        )
        selected_collection = zotero_collections[selected_collection_index]
        st.session_state["research_collection_id_input"] = selected_collection["key"]
        st.session_state["research_collection_name_input"] = selected_collection["name"]

    with st.form("research_run_form"):
        collection_id = st.text_input(
            "Zotero Collection ID",
            placeholder="COLL123",
            key="research_collection_id_input",
        )
        collection_name = st.text_input(
            "Collection Name",
            placeholder="IRSTD",
            key="research_collection_name_input",
        )
        goal = st.text_area(
            "Goal",
            value="Generate a literature review and experiment plan from this Zotero collection.",
            height=100,
        )
        max_papers = st.number_input("Max papers", min_value=1, max_value=50, value=5)
        semantic_scholar = st.checkbox("Enable Semantic Scholar enrichment", value=False)
        arxiv = st.checkbox("Enable arXiv fallback", value=False)
        obsidian_publish = st.checkbox("Publish to Obsidian", value=False)
        submitted = st.form_submit_button("Initialize Research Run")

    if submitted:
        if not collection_id.strip() or not collection_name.strip():
            st.error("Collection ID and Collection Name are required.")
        else:
            try:
                run = service.create_run(
                    ResearchRunCreateRequest(
                        collection_id=collection_id.strip(),
                        collection_name=collection_name.strip(),
                        goal=goal.strip(),
                        options=ResearchRunOptions(
                            max_papers=int(max_papers),
                            semantic_scholar=semantic_scholar,
                            arxiv=arxiv,
                            obsidian_publish=obsidian_publish,
                        ),
                    )
                )
            except Exception as exc:
                st.error(f"Unable to initialize research run: {exc}")
            else:
                st.session_state["selected_research_run_id"] = run.run_id
                st.success(f"Research run initialized: {run.run_id}")
                st.rerun()

    try:
        runs = service.list_runs()
    except Exception as exc:
        st.error(f"Unable to load recent research runs: {exc}")
        runs = []

    st.subheader("Recent Runs")
    if not runs:
        st.info("No research runs yet.")
    else:
        run_ids = [run.run_id for run in runs]
        widget_selected_run_id = st.session_state.get("research_run_selector")
        if widget_selected_run_id in run_ids:
            selected_research_run_id = widget_selected_run_id

        if selected_research_run_id not in run_ids:
            selected_research_run_id = run_ids[0]
            st.session_state["selected_research_run_id"] = selected_research_run_id

        selected_run_index = run_ids.index(selected_research_run_id)
        selected_run_id = st.selectbox(
            "Select run",
            run_ids,
            index=selected_run_index,
            key="research_run_selector",
        )
        st.session_state["selected_research_run_id"] = selected_run_id

        try:
            run = service.get_run(selected_run_id)
        except Exception as exc:
            st.error(f"Unable to load selected research run: {exc}")
        else:
            st.metric("Status", run.status)
            st.progress(run.progress)
            st.write(f"Collection: {run.collection_name}")
            st.write(f"Output: {run.output_dir}")
            if run.error:
                st.error(f"Run error: {run.error}")

            st.subheader("Agent Timeline")
            for step in run.steps:
                st.write(f"{step.agent}: {step.status} ({step.progress:.0%})")

            col_execute, col_refresh = st.columns(2)
            with col_execute:
                if st.button("Process Local Collection", type="primary", use_container_width=True):
                    try:
                        run = service.execute_local_run(
                            run.run_id,
                            paper_processor=get_paper_processing_service(),
                        )
                    except Exception as exc:
                        st.error(f"Unable to process local collection: {exc}")
                    else:
                        st.session_state["selected_research_run_id"] = run.run_id
                        if run.status == "failed" or run.error:
                            st.error(
                                f"Local collection processing failed: {run.error or 'Unknown error'}"
                            )
                        else:
                            st.success("Local collection processing completed.")
                        st.rerun()
            with col_refresh:
                if st.button("Refresh Run", use_container_width=True):
                    st.rerun()

            st.subheader("Paper Items")
            if not run.paper_items:
                st.info("No Zotero paper items have been collected yet.")
            else:
                for item in run.paper_items:
                    with st.expander(f"{item.title} - {item.status}", expanded=item.status != "completed"):
                        st.write(f"Zotero Item: {item.zotero_item_id}")
                        st.write(f"Paper ID: {item.paper_id or 'not synced'}")
                        st.write(f"PDF: {item.pdf_path or 'missing'}")
                        st.progress(item.progress)
                        if item.error:
                            st.error(item.error)
                        for artifact in item.artifacts:
                            st.write(f"{artifact.label}: {artifact.path}")

            st.subheader("Knowledge Pack Outputs")
            output_labels = {
                "Literature Review",
                "Method Matrix",
                "Research Gaps",
                "Experiment Plan",
                "Reading Roadmap",
            }
            knowledge_pack_outputs = [
                artifact for artifact in run.artifacts if artifact.label in output_labels
            ]
            if knowledge_pack_outputs:
                for artifact in knowledge_pack_outputs:
                    st.write(f"{artifact.label}: {artifact.path}")
            else:
                st.info("Knowledge Pack Outputs will appear after local collection processing.")
            st.caption("Tool-call trace: tool-calls.jsonl")

            st.subheader("Artifacts")
            for artifact in run.artifacts:
                st.write(f"{artifact.label}: {artifact.path}")

elif tab == "📤 论文上传":
    st.header("📤 上传论文 PDF")
    st.caption("支持点击选择或直接拖拽多个 PDF 到下方上传框")

    if "pending_uploads" not in st.session_state:
        st.session_state["pending_uploads"] = []
    if "last_parsed_uploads" not in st.session_state:
        st.session_state["last_parsed_uploads"] = []
    if "last_indexed_uploads" not in st.session_state:
        st.session_state["last_indexed_uploads"] = []
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0
    if "delete_confirm_paper_id" not in st.session_state:
        st.session_state["delete_confirm_paper_id"] = None

    uploaded_files = st.file_uploader(
        "选择 PDF 论文文件（可拖拽多篇 PDF 到这里）",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"pdf_uploader_{st.session_state['uploader_key']}",
        help="拖拽上传后，需要点击“保存上传文件”，再点击“开始解析”。",
    )

    if uploaded_files:
        st.caption(
            f"当前已选 {len(uploaded_files)} 个文件（拖拽后如果这里有文件名，说明 Streamlit 已接收到文件）"
        )
        for uploaded in uploaded_files:
            st.caption(f"已选: {uploaded.name}")

    col_upload, col_parse, col_clear = st.columns(3)

    with col_upload:
        if st.button(
            "📥 保存上传文件", use_container_width=True, key="btn_save_uploads"
        ):
            if not uploaded_files:
                st.warning("请先选择或拖拽至少 1 个 PDF 文件")
            else:
                new_saved_files = save_uploaded_files(uploaded_files)
                st.session_state["pending_uploads"] = [
                    *st.session_state.get("pending_uploads", []),
                    *new_saved_files,
                ]
                st.session_state["last_parsed_uploads"] = []
                st.session_state["last_indexed_uploads"] = []
                st.session_state["uploader_key"] += 1
                st.success(
                    f"本次新保存 {len(new_saved_files)} 个文件，当前共有 {len(st.session_state['pending_uploads'])} 个待解析文件，请点击“开始解析”"
                )
                st.rerun()

    with col_parse:
        if st.button(
            "🧠 开始解析",
            use_container_width=True,
            type="primary",
            key="btn_parse_uploads",
        ):
            pending_uploads = st.session_state.get("pending_uploads", [])
            if not pending_uploads:
                st.warning("没有待解析的文件，请先上传并保存 PDF")
            else:
                with st.spinner(f"正在解析并入库 {len(pending_uploads)} 篇论文..."):
                    try:
                        parsed_results = parse_saved_files(pending_uploads)
                        indexed_results = index_parsed_files(pending_uploads)
                        st.session_state["last_parsed_uploads"] = parsed_results
                        st.session_state["last_indexed_uploads"] = indexed_results
                        st.session_state["pending_uploads"] = []
                        refresh_papers()
                        indexed_count = sum(
                            1 for item in indexed_results if item["status"] == "indexed"
                        )
                        st.success(
                            f"✅ 成功解析 {len(parsed_results)} 篇论文，并完成 {indexed_count} 篇入库"
                        )
                    except Exception as e:
                        st.error(f"解析失败: {e}")

    with col_clear:
        if st.button(
            "🗑️ 清空待解析", use_container_width=True, key="btn_clear_uploads"
        ):
            st.session_state["pending_uploads"] = []
            st.session_state["last_parsed_uploads"] = []
            st.session_state["last_indexed_uploads"] = []
            st.session_state["uploader_key"] += 1
            st.rerun()

    pending_uploads = st.session_state.get("pending_uploads", [])
    if pending_uploads:
        st.info(f"当前有 {len(pending_uploads)} 个待解析文件")
        for item in pending_uploads:
            st.caption(f"待解析: {item['filename']} → {item['paper_id']}")

    if st.session_state.get("last_parsed_uploads"):
        st.subheader("最近解析结果")
        for item in st.session_state["last_parsed_uploads"]:
            st.json(item)

    if st.session_state.get("last_indexed_uploads"):
        st.subheader("最近入库结果")
        for item in st.session_state["last_indexed_uploads"]:
            st.json(item)
            if item.get("status") == "indexed":
                st.caption(
                    f"设备: {item.get('embedding_device', '-') } | batch={item.get('embedding_batch_size', '-') } | "
                    f"后端: {item.get('vector_backend', '-') } | chunks总数: {item.get('vector_chunk_total', '-') }"
                )
                st.caption(f"存储路径: {item.get('vector_store_path', '-')}")

    st.divider()
    st.subheader("已上传论文")

    if st.button("刷新列表"):
        refresh_papers()

    options, papers = load_paper_options()
    if not papers:
        st.info("暂无已上传论文")
    else:
        for p in papers:
            paper_id = p["paper_id"]
            with st.expander(f"{paper_id} — {p['title'][:80]}"):
                st.caption(f"ID: {paper_id}")
                st.caption(f"摘要: {p['abstract'][:200]}...")

                delete_col, confirm_col = st.columns(2)
                with delete_col:
                    if st.button("删除这篇论文", key=f"delete_paper_{paper_id}"):
                        st.session_state["delete_confirm_paper_id"] = paper_id
                        st.rerun()

                if st.session_state.get("delete_confirm_paper_id") == paper_id:
                    st.warning(
                        f"确认删除 {paper_id} 吗？此操作会同时删除原始 PDF、解析结果、笔记和向量索引。"
                    )
                    with confirm_col:
                        if st.button(
                            "确认删除",
                            key=f"confirm_delete_paper_{paper_id}",
                            type="primary",
                        ):
                            try:
                                result = delete_paper_assets(
                                    paper_id=paper_id,
                                    upload_dir=settings.upload_dir,
                                    metadata_dir=settings.metadata_dir,
                                    note_dir=settings.note_dir,
                                    vector_store=get_vector_store(),
                                )
                                st.session_state["delete_confirm_paper_id"] = None
                                st.success(
                                    f"已删除 {paper_id}，移除文件 {len(result['deleted_files'])} 个，向量块 {result['deleted_chunks']} 个"
                                )
                                refresh_papers()
                                st.rerun()
                            except Exception as e:
                                st.error(f"删除失败: {e}")

                    if st.button("取消删除", key=f"cancel_delete_paper_{paper_id}"):
                        st.session_state["delete_confirm_paper_id"] = None
                        st.rerun()


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

                        pdf_path = find_pdf_path(
                            selected_id, settings.upload_dir, settings.metadata_dir
                        )
                        result = parse_pdf(pdf_path, selected_id)
                        save_parse_result(result, settings.metadata_dir)
                        st.success("解析完成")
                    except Exception as e:
                        st.error(f"解析失败: {e}")

        with col2:
            if st.button(
                "🤖 生成笔记",
                use_container_width=True,
                type="primary",
                key="btn_generate",
            ):
                with st.spinner("LLM 生成笔记中（可能需要 30-60 秒）..."):
                    llm = get_llm_client()
                    try:
                        content = generate_note(selected_id, llm_client=llm)
                        note_path = save_markdown(
                            selected_id, content, settings.note_dir
                        )
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

    question = st.text_area(
        "输入问题", placeholder="例如：这篇论文的核心创新点是什么？", key="qa_question"
    )
    top_k = st.slider("检索片段数", 1, 10, 3, key="qa_topk")

    if st.button("🔍 提问", type="primary", disabled=not question, key="btn_qa"):
        if not question.strip():
            st.warning("请输入问题")
        else:
            with st.spinner("检索 + 推理中..."):
                try:
                    llm_client = get_llm_client()
                    embedding_client = get_embedding_client()
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
                            with st.expander(
                                f"来源 {i}: {src['paper_id']} / {src['section']}"
                            ):
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
                        comparison = compare_papers(
                            selected_ids,
                            settings.metadata_dir,
                            llm_client=llm,
                        )
                        output_path = save_compare_result(
                            comparison.markdown, settings.note_dir
                        )
                        st.session_state["compare_content"] = comparison.markdown
                        st.session_state["compare_result"] = comparison
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
                file_name=os.path.basename(
                    st.session_state.get("compare_path", "compare.md")
                ),
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
            if st.button(
                "📥 索引到向量库",
                use_container_width=True,
                type="primary",
                key="btn_index",
            ):
                with st.spinner("切块 + 向量化 + 写入中..."):
                    try:
                        data = load_parsed_result(index_paper_id, settings.metadata_dir)
                        parsed = PaperParseResult(**data)
                        chunks = chunk_paper(parsed)

                        if not chunks:
                            st.error("论文内容为空，无法索引")
                        else:
                            emb_client = get_embedding_client()
                            embeddings = emb_client.embed_texts(
                                [c.content for c in chunks]
                            )
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


# ── Tab 6: Agent ─────────────────────────────────────────────────────────────


elif tab == "🤖 Agent 助手":
    st.header("🤖 Agent 助手")
    st.caption("自然语言驱动的论文研究助手 — 支持多步工具调用和工作流编排")

    # Workflow selector
    workflow_mode = st.radio(
        "工作模式",
        ["自由对话", "完整论文分析工作流", "多论文对比工作流"],
        horizontal=True,
        key="agent_workflow_mode",
    )

    if workflow_mode == "完整论文分析工作流":
        st.subheader("完整论文分析工作流: parse → index → note → qa")
        uploaded = st.file_uploader(
            "上传论文 PDF",
            type=["pdf"],
            accept_multiple_files=False,
            key="agent_workflow_upload",
        )

        question = st.text_input(
            "分析问题（可选）",
            placeholder="例如：这篇论文的核心创新是什么？",
            key="agent_wf_question",
        )

        if st.button(
            "▶️ 执行工作流",
            type="primary",
            disabled=not uploaded,
            key="btn_run_workflow",
        ):
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = tmp.name

            with st.spinner("执行中: parse → index → note → qa..."):
                from app.agents.workflows.research_workflow import (
                    build_research_workflow,
                )

                graph = build_research_workflow()
                state = graph.invoke(
                    {
                        "paper_id": "",
                        "file_path": tmp_path,
                        "question": question,
                        "top_k": 5,
                        "parsed": False,
                        "indexed": False,
                        "note_generated": False,
                        "title": "",
                        "sections_count": 0,
                        "chars": 0,
                        "chunks_indexed": 0,
                        "note_path": "",
                        "note_length": 0,
                        "answer": "",
                        "sources_count": 0,
                        "error": "",
                    }
                )

            if state.get("error"):
                st.error(f"工作流执行失败: {state['error']}")
            else:
                st.success(f"工作流完成: {state['paper_id']}")
                st.metric(
                    "解析",
                    f"{state.get('title', '-')} ({state.get('sections_count', 0)} 章节)",
                )
                st.metric("索引", f"{state.get('chunks_indexed', 0)} chunks")
                st.metric("笔记", f"{state.get('note_length', 0)} 字符")

                if state.get("note_path"):
                    with open(state["note_path"], "r", encoding="utf-8") as f:
                        with st.expander("查看笔记内容"):
                            st.markdown(f.read())

                if state.get("answer"):
                    st.subheader("分析回答")
                    st.markdown(state["answer"])

            # Cleanup
            import os as _os

            _os.unlink(tmp_path)

    elif workflow_mode == "多论文对比工作流":
        st.subheader("多论文对比工作流: parse → compare → export")
        uploaded_files = st.file_uploader(
            "上传多篇论文 PDF (2-5 篇)",
            type=["pdf"],
            accept_multiple_files=True,
            key="agent_compare_upload",
        )

        if st.button(
            "▶️ 执行对比",
            type="primary",
            disabled=not uploaded_files or len(uploaded_files) < 2,
            key="btn_run_compare",
        ):
            import os as _os
            import tempfile

            tmp_paths = []
            for uf in uploaded_files:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(uf.getbuffer())
                    tmp_paths.append(tmp.name)

            with st.spinner(f"对比 {len(tmp_paths)} 篇论文..."):
                from app.agents.workflows.comparison_workflow import (
                    build_comparison_workflow,
                )

                graph = build_comparison_workflow()
                state = graph.invoke(
                    {
                        "file_paths": tmp_paths,
                        "paper_ids": [],
                        "all_parsed": False,
                        "compared": False,
                        "exported": False,
                        "titles": [],
                        "output_path": "",
                        "content_length": 0,
                        "aspects_count": 0,
                        "error": "",
                    }
                )

            if state.get("error"):
                st.error(f"对比失败: {state['error']}")
            else:
                st.success(f"对比完成: {len(state.get('paper_ids', []))} 篇论文")
                st.metric("对比维度", f"{state.get('aspects_count', 0)} 个")

                if state.get("output_path"):
                    with open(state["output_path"], "r", encoding="utf-8") as f:
                        with st.expander("查看对比结果"):
                            st.markdown(f.read())

            for p in tmp_paths:
                _os.unlink(p)

    else:
        # Free conversation mode
        from ui.components.agent_chat import render_agent_chat

        render_agent_chat()


# ── Tab 7: Agent Monitor ─────────────────────────────────────────────────────


elif tab == "🔍 Agent 监控":
    from ui.pages.agent_monitor import render_agent_monitor

    render_agent_monitor()
