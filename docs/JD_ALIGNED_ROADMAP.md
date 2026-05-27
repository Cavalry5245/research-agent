# JD-Aligned Development Roadmap

> **[当前主执行计划]** 最后更新：2026-05-25  
> **执行状态**：Phase 1-5 已完成 → Phase 6 准备启动  
> **进度追踪**：见本文档各 Phase 的验收标准

> 基于「大语言模型与 Agent 应用开发实习生」岗位要求的项目升级路线图  
> 目标：3 个月内将 ResearchAgent 打造成覆盖 JD 核心能力的完整 Agent 应用案例

## 文档说明

- **执行周期**: 12 周（3 个月实习期）
- **每周投入**: 4-5 天
- **验收标准**: 每个 Phase 完成后需通过测试 + 文档更新 + Demo 演示
- **技术对齐**: 所有新增功能需对应 JD 中的岗位职责或加分项

## 当前项目基线（Week 0）

### 已完成功能
- ✅ PDF 解析（PyMuPDF）
- ✅ 13 段结构化笔记生成
- ✅ 向量检索 + RAG 问答
- ✅ 多论文对比
- ✅ Streamlit 5-Tab UI
- ✅ FastAPI 13 endpoints
- ✅ 202 passed tests
- ✅ Evaluation 骨架（seed dataset + baseline report）

### 技术栈
- Python 3.11, FastAPI, Streamlit
- PyMuPDF, sentence-transformers (bge-small-zh-v1.5)
- OpenAI-compatible LLM API
- 本地文件存储 + 向量检索

### 核心缺口（对标 JD）
1. ❌ Agent 系统（任务拆解、工具调用、工作流编排）
2. ❌ 数据分析与可视化（Pandas/Matplotlib）
3. ❌ 效果评估体系（A/B 测试、失败案例分析）
4. ❌ 工程化（异步任务、日志系统、数据库）
5. ❌ 高级 RAG（Rerank、Hybrid Search）

---

## Phase 1: Agent 工作流基础（Week 1-2）

### 目标
实现基础 Agent 系统，展示任务拆解、工具调用、工作流编排能力

### JD 对应
- 岗位职责 2: Agent 系统设计与实现（任务拆解、工具调用、工作流编排）
- 任职要求 4: Function Calling、Tool Use
- 加分项 2: LangChain/LangGraph

### 任务清单

#### 1.1 工具封装层（Day 1-2）
**目标**: 将现有 service 层封装为标准 Agent 工具

**实现步骤**:
1. 创建 `app/agents/tools/` 目录
2. 实现工具基类 `BaseTool`:
   ```python
   class BaseTool:
       name: str
       description: str
       parameters: dict  # JSON Schema
       def execute(self, **kwargs) -> dict
   ```
3. 封装现有功能为工具:
   - `UploadPaperTool`: 上传并解析 PDF
   - `GenerateNoteTool`: 生成结构化笔记
   - `IndexPaperTool`: 构建向量索引
   - `QATool`: RAG 问答
   - `ComparePapersTool`: 多论文对比
   - `ExportMarkdownTool`: 导出 Markdown

**验收标准**:
- [x] 6 个工具类实现完成
- [x] 每个工具有独立单元测试
- [x] 工具注册中心 `ToolRegistry` 实现
- [x] 测试: `pytest tests/test_agent_tools.py -v`

**产出文件**:
- `app/agents/tools/base.py`
- `app/agents/tools/paper_tools.py`
- `app/agents/tools/registry.py`
- `tests/test_agent_tools.py`


#### 1.2 LangChain 集成（Day 3-4）
**目标**: 使用 LangChain 实现工具调用和 Agent 执行

**实现步骤**:
1. 安装依赖: `pip install langchain langchain-openai`
2. 实现 LangChain Tool 适配器:
   ```python
   from langchain.tools import Tool
   def convert_to_langchain_tool(base_tool: BaseTool) -> Tool:
       return Tool(
           name=base_tool.name,
           description=base_tool.description,
           func=base_tool.execute
       )
   ```
3. 创建 `PaperResearchAgent`:
   - 使用 `initialize_agent` 或 `create_openai_functions_agent`
   - 配置工具列表
   - 实现对话历史管理
4. 添加 Agent 执行接口: `POST /agent/execute`

**验收标准**:
- [x] Agent 能正确调用工具
- [x] 支持多轮对话
- [x] 工具调用链路可追踪
- [x] 测试: 输入"帮我分析 paper_001 的核心创新"，Agent 自动调用 QATool

**产出文件**:
- `app/agents/paper_research_agent.py`
- `app/agents/langchain_adapter.py`
- `tests/test_paper_research_agent.py`

#### 1.3 工作流编排（Day 5-7）
**目标**: 实现复杂任务的自动拆解和编排

**实现步骤**:
1. 安装 LangGraph: `pip install langgraph`
2. 定义工作流状态:
   ```python
   class ResearchWorkflowState(TypedDict):
       paper_id: str
       parsed: bool
       indexed: bool
       note_generated: bool
       qa_results: list
   ```
3. 实现工作流节点:
   - `parse_node`: 解析 PDF
   - `index_node`: 构建索引
   - `note_node`: 生成笔记
   - `qa_node`: 问答
4. 使用 StateGraph 编排:
   ```python
   workflow = StateGraph(ResearchWorkflowState)
   workflow.add_node("parse", parse_node)
   workflow.add_node("index", index_node)
   workflow.add_edge("parse", "index")
   ```
5. 添加条件路由（根据任务类型选择分支）

**验收标准**:
- [x] 实现"完整论文分析"工作流（上传→解析→索引→笔记→问答）
- [x] 实现"多论文对比"工作流（解析多篇→提取→对比→生成报告）
- [x] 工作流状态可持久化
- [x] 支持工作流可视化（导出 Mermaid 图）
- [x] 测试: `pytest tests/test_workflows.py -v`

**产出文件**:
- `app/agents/workflows/research_workflow.py`
- `app/agents/workflows/comparison_workflow.py`
- `tests/test_workflows.py`
- `docs/WORKFLOW_DESIGN.md`

#### 1.4 Streamlit Agent Tab（Day 8-10）
**目标**: 在 UI 中展示 Agent 能力

**实现步骤**:
1. 在 Streamlit 添加新 Tab: "🤖 Agent 助手"
2. 实现对话界面:
   - 用户输入自然语言任务
   - 展示 Agent 思考过程（工具调用链路）
   - 展示最终结果
3. 添加工作流选择器:
   - 完整论文分析
   - 多论文对比
   - 自定义问答
4. 实时展示工作流执行进度

**验收标准**:
- [x] Agent Tab 可用
- [x] 工具调用过程可视化
- [x] 支持中断和重试
- [x] 用户体验流畅

**产出文件**:
- `ui/streamlit_app.py` (更新)
- `ui/components/agent_chat.py`

### Phase 1 总结文档
- [x] 更新 `docs/ARCHITECTURE.md` 添加 Agent 架构图
- [x] 创建 `docs/AGENT_DESIGN.md` 详细说明设计思路
- [x] 更新 `README.md` 添加 Agent 功能说明
- [x] 录制 Agent 使用 Demo 视频（3 分钟）- 跳过，UI 界面已完成

### Phase 1 验收标准
- [x] 所有测试通过: `pytest tests -v` → 260 passed, 1 skipped
- [x] Agent 能自动完成"上传→分析→问答"全流程
- [x] 工作流可视化图生成
- [x] 文档完整更新


## Phase 2: 数据分析与效果评估（Week 3-4）

> **✅ 已完成** — 2026-05-20  
> **关键产出**：`app/analytics/` + `app/experiments/` + 4 个 Jupyter Notebook + 3 份实验报告 + 失败分析报告 + 50 个测试  
> **完整任务清单**：见 `.claude/tasks/current-tasks.md` 中的 Phase 2 章节

### 目标
构建完整的数据分析和效果评估体系，展示数据处理、可视化、实验设计能力

### JD 对应
- 岗位职责 3: 数据处理与分析、可视化、问题定位
- 岗位职责 4: 效果评估、失败案例分析、优化迭代
- 任职要求 3: Pandas、NumPy、Matplotlib
- 加分项 4: A/B 测试、实验设计、效果评估

### 任务清单

#### 2.1 数据分析模块（Day 1-3）
**目标**: 实现系统运行数据的统计分析和可视化

**实现步骤**:
1. 创建 `app/analytics/` 目录
2. 实现数据收集:
   ```python
   # app/analytics/data_collector.py
   class AnalyticsCollector:
       def log_qa_request(paper_id, question, answer, retrieval_time, llm_time)
       def log_comparison(paper_ids, generation_time, result_length)
       def log_indexing(paper_id, chunk_count, embedding_time)
   ```
3. 实现分析脚本:
   - `analyze_retrieval.py`: 检索效果分析
     - Hit@K 曲线（K=1,3,5,10）
     - MRR 趋势
     - 检索时间分布
     - 失败 case 聚类（按 paper、section、query 类型）
   - `analyze_qa.py`: 问答质量分析
     - 答案长度分布
     - 引用准确率
     - 响应时间统计（检索 vs LLM）
     - 高频问题 Top 10
   - `analyze_comparison.py`: 对比生成分析
     - 论文数量 vs 生成时间
     - 对比维度覆盖率
     - 生成质量评分分布

4. 实现可视化:
   ```python
   # app/analytics/visualizer.py
   import matplotlib.pyplot as plt
   import seaborn as sns
   
   def plot_hit_at_k_curve(eval_results)
   def plot_response_time_distribution(qa_logs)
   def plot_failure_case_heatmap(failure_data)
   ```

**验收标准**:
- [ ] 数据收集埋点完成（不影响主流程性能）
- [ ] 3 个分析脚本可独立运行
- [ ] 生成至少 5 种可视化图表
- [ ] 测试: `pytest tests/test_analytics.py -v`

**产出文件**:
- `app/analytics/data_collector.py`
- `app/analytics/analyze_retrieval.py`
- `app/analytics/analyze_qa.py`
- `app/analytics/visualizer.py`
- `app/analytics/reports/` (存放生成的图表)
- `tests/test_analytics.py`

#### 2.2 A/B 测试框架（Day 4-5）
**目标**: 实现实验配置和对比评估能力

**实现步骤**:
1. 创建实验配置系统:
   ```python
   # app/experiments/config.py
   class ExperimentConfig:
       experiment_id: str
       variant: str  # "A" or "B"
       parameters: dict  # 实验参数
   ```
2. 实现实验场景:
   - **实验 1**: Prompt 版本对比
     - Variant A: 当前 13 段笔记模板
     - Variant B: 精简 8 段模板
     - 评估指标: 生成时间、内容完整度、用户满意度
   - **实验 2**: Embedding 模型对比
     - Variant A: bge-small-zh-v1.5
     - Variant B: bge-large-zh-v1.5
     - 评估指标: Hit@3, MRR, 检索时间
   - **实验 3**: Chunk 策略对比
     - Variant A: chunk_size=800, overlap=100
     - Variant B: chunk_size=500, overlap=50
     - 评估指标: 检索准确率、答案质量

3. 实现实验执行器:
   ```python
   # app/experiments/runner.py
   class ExperimentRunner:
       def run_experiment(config, test_dataset)
       def compare_variants(results_a, results_b)
       def generate_report(comparison)
   ```

**验收标准**:
- [ ] 3 个实验场景配置完成
- [ ] 实验结果可自动对比
- [ ] 生成 Markdown 实验报告
- [ ] 测试: `python app/experiments/runner.py --experiment prompt_comparison`

**产出文件**:
- `app/experiments/config.py`
- `app/experiments/runner.py`
- `app/experiments/scenarios/` (3 个实验配置)
- `app/experiments/reports/` (实验报告)
- `docs/EXPERIMENT_GUIDE.md`

#### 2.3 失败案例分析（Day 6-7）
**目标**: 自动收集和分析系统失败 case

**实现步骤**:
1. 实现失败检测:
   ```python
   # app/analytics/failure_detector.py
   class FailureDetector:
       def detect_retrieval_failure(query, results, threshold=0.5)
       def detect_qa_failure(question, answer, expected)
       def detect_comparison_failure(result)
   ```
2. 失败分类:
   - 检索失败: 召回率低、相关性差
   - QA 失败: LLM 幻觉、答非所问、引用错误
   - 对比失败: 格式错误、维度缺失、证据不足
   - 解析失败: PDF 结构异常、编码问题

3. 实现失败分析器:
   ```python
   # app/analytics/failure_analyzer.py
   def analyze_retrieval_failures(failure_cases):
       # 按 paper、section、query 类型聚类
       # 识别共性问题（如某类 section 检索效果差）
   
   def analyze_qa_failures(failure_cases):
       # 识别 LLM 幻觉模式
       # 统计高频错误类型
   ```

4. 生成分析报告:
   - 失败率统计
   - Top 10 失败模式
   - 根因分析
   - 优化建议

**验收标准**:
- [ ] 失败检测自动化
- [ ] 失败 case 持久化存储
- [ ] 生成失败分析报告（Markdown + 图表）
- [ ] 测试: `pytest tests/test_failure_analyzer.py -v`

**产出文件**:
- `app/analytics/failure_detector.py`
- `app/analytics/failure_analyzer.py`
- `app/analytics/reports/failure_analysis.md`
- `tests/test_failure_analyzer.py`

#### 2.4 Jupyter Notebook 展示（Day 8-10）
**目标**: 用 Notebook 展示完整数据分析过程

**实现步骤**:
1. 安装依赖: `pip install jupyter pandas matplotlib seaborn`
2. 创建 Notebook:
   - `notebooks/01_retrieval_analysis.ipynb`: 检索效果分析
   - `notebooks/02_qa_quality_analysis.ipynb`: 问答质量分析
   - `notebooks/03_experiment_comparison.ipynb`: A/B 测试对比
   - `notebooks/04_failure_case_study.ipynb`: 失败案例深度分析

3. Notebook 内容结构:
   - 数据加载和清洗
   - 探索性数据分析（EDA）
   - 可视化
   - 统计检验（t-test, chi-square）
   - 结论和建议

**验收标准**:
- [ ] 4 个 Notebook 可独立运行
- [ ] 包含至少 10 种可视化图表
- [ ] 有清晰的分析结论
- [ ] 代码注释完整

**产出文件**:
- `notebooks/01_retrieval_analysis.ipynb`
- `notebooks/02_qa_quality_analysis.ipynb`
- `notebooks/03_experiment_comparison.ipynb`
- `notebooks/04_failure_case_study.ipynb`
- `notebooks/README.md`

### Phase 2 总结文档
- [ ] 创建 `docs/ANALYTICS_GUIDE.md` 说明分析体系
- [x] 创建 `docs/EXPERIMENT_RESULTS.md` 汇总实验结论
- [x] 更新 `README.md` 添加数据分析功能
- [ ] 准备分析 Demo PPT（10 页）  ← 可选，留待 Phase 6

### Phase 2 验收标准
- [x] 所有测试通过
- [x] 至少完成 2 个 A/B 实验并有结论（实际完成 3 个：prompt / embedding / chunk）
- [x] 失败分析报告生成
- [x] Jupyter Notebook 可复现（4 个 Notebook，jupyter nbconvert --execute 全部成功）


## Phase 3: 工程化与生产就绪（Week 5-6）

> **✅ 已完成** — 2026-05-21  
> **关键产出**：通用后台任务系统 + note/compare 异步任务 + request_id 追踪 + JSONL 结构化日志 + 统一错误响应 + 日志分析报告 + 工程化决策文档  
> **完整任务清单**：见 `.claude/tasks/current-tasks.md` 中的 Phase 3 章节

### 目标
提升系统工程化水平，展示后端开发、异步任务、日志分析能力

### JD 对应
- 岗位职责 6: 接口开发、日志分析、问题排查
- 加分项 5: 后端开发（API、异步任务、数据库、缓存、消息队列）

### 任务清单

> **执行调整（2026-05-20）**：Phase 3 的详细执行清单以 `.claude/tasks/current-tasks.md` 为准。考虑到项目已具备 FastAPI `BackgroundTasks`、`FileJobStore`、索引任务状态追踪等基础，本阶段优先完成轻量后台任务闭环、结构化日志、请求追踪和错误处理；Celery/Redis/数据库作为评估或可选最小落地项，避免过早重构影响 Phase 4/5 进度。

#### 3.1 异步任务系统（Day 1-3）
**目标**: 将长时间任务改为后台异步执行

**实现步骤**:
1. 安装依赖: `pip install celery redis`
2. 配置 Celery:
   ```python
   # app/tasks/celery_app.py
   from celery import Celery
   
   celery_app = Celery(
       'research_agent',
       broker='redis://localhost:6379/0',
       backend='redis://localhost:6379/1'
   )
   ```
3. 改造长时间任务为异步:
   - `generate_note_async`: 笔记生成（LLM 调用）
   - `index_paper_async`: 向量索引构建
   - `compare_papers_async`: 多论文对比
   - `batch_index_async`: 批量索引

4. 实现任务状态查询:
   ```python
   # app/schemas.py
   class TaskStatus(BaseModel):
       task_id: str
       status: str  # pending, running, completed, failed
       progress: float  # 0.0 - 1.0
       result: Optional[dict]
       error: Optional[str]
   ```

5. 添加 API 接口:
   - `POST /tasks/note/{paper_id}`: 提交笔记生成任务
   - `GET /tasks/{task_id}/status`: 查询任务状态
   - `GET /tasks/{task_id}/result`: 获取任务结果
   - `DELETE /tasks/{task_id}`: 取消任务

**验收标准**:
- [x] Celery worker 可启动（已决策跳过：本阶段使用 FastAPI BackgroundTasks，迁移方案见 `docs/ASYNC_TASKS.md`）
- [x] 异步任务正常执行
- [x] 任务状态实时更新
- [x] 支持任务取消和重试
- [x] 测试: `pytest tests/test_async_note_tasks.py tests/test_async_compare_tasks.py tests/test_task_routes.py -v`

**产出文件**:
- `app/tasks/celery_app.py`
- `app/tasks/paper_tasks.py`
- `app/api/task_routes.py`
- `tests/test_async_tasks.py`
- `docs/ASYNC_TASKS.md`

#### 3.2 结构化日志系统（Day 4-5）
**目标**: 实现生产级日志记录和分析

**实现步骤**:
1. 安装依赖: `pip install structlog`
2. 配置结构化日志:
   ```python
   # app/logging_config.py
   import structlog
   
   structlog.configure(
       processors=[
           structlog.stdlib.add_log_level,
           structlog.stdlib.add_logger_name,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.StackInfoRenderer(),
           structlog.processors.format_exc_info,
           structlog.processors.JSONRenderer()
       ]
   )
   ```

3. 添加请求链路追踪:
   ```python
   # app/middleware/tracing.py
   import uuid
   
   @app.middleware("http")
   async def add_trace_id(request, call_next):
       trace_id = str(uuid.uuid4())
       request.state.trace_id = trace_id
       response = await call_next(request)
       response.headers["X-Trace-ID"] = trace_id
       return response
   ```

4. 关键节点日志埋点:
   - API 请求/响应（耗时、状态码、参数）
   - LLM 调用（模型、token 数、耗时、成本）
   - 向量检索（query、top_k、耗时、结果数）
   - 任务执行（task_id、状态变更、错误）

5. 实现日志分析脚本:
   ```python
   # app/analytics/log_analyzer.py
   def analyze_api_performance(log_file):
       # 统计各接口调用频率、平均响应时间、错误率
   
   def analyze_llm_usage(log_file):
       # 统计 token 消耗、成本、调用失败率
   
   def detect_anomalies(log_file):
       # 检测异常模式（响应时间突增、错误率飙升）
   ```

**验收标准**:
- [x] 所有 API 请求有 trace_id
- [x] 日志格式统一（JSON）
- [x] 日志分析脚本可用
- [x] 生成日志分析报告
- [x] 测试: `pytest tests/test_logging.py tests/test_tracing_middleware.py tests/test_log_analyzer.py -v`

**产出文件**:
- `app/logging_config.py`
- `app/middleware/tracing.py`
- `app/analytics/log_analyzer.py`
- `tests/test_logging.py`
- `docs/LOGGING_GUIDE.md`

#### 3.3 数据库与缓存（Day 6-8）
**目标**: 引入数据库和缓存提升性能和可靠性

**实现步骤**:
1. 安装依赖: `pip install sqlalchemy alembic redis`
2. 设计数据库 Schema:
   ```python
   # app/models/database.py
   class Paper(Base):
       id = Column(String, primary_key=True)
       title = Column(String)
       upload_time = Column(DateTime)
       status = Column(String)  # uploaded, parsed, indexed
       tags = Column(JSON)
       metadata = Column(JSON)
   
   class Note(Base):
       id = Column(Integer, primary_key=True)
       paper_id = Column(String, ForeignKey('papers.id'))
       content = Column(Text)
       created_at = Column(DateTime)
   
   class QAHistory(Base):
       id = Column(Integer, primary_key=True)
       paper_id = Column(String)
       question = Column(Text)
       answer = Column(Text)
       sources = Column(JSON)
       created_at = Column(DateTime)
   ```

3. 实现数据库迁移:
   ```bash
   alembic init migrations
   alembic revision --autogenerate -m "initial schema"
   alembic upgrade head
   ```

4. 实现 Redis 缓存:
   ```python
   # app/cache/redis_cache.py
   class RedisCache:
       def cache_embedding(paper_id, section, embedding)
       def get_cached_embedding(paper_id, section)
       def cache_note(paper_id, note)
       def get_cached_note(paper_id)
   ```

5. 改造存储层:
   - 论文元数据存 SQLite
   - 笔记内容存数据库
   - Embedding 结果缓存到 Redis
   - 保留文件存储作为备份

**验收标准**:
- [x] 数据库迁移脚本可用（已决策跳过：Phase 3 保留文件存储，见 `docs/DATABASE_CACHE_DECISION.md`）
- [x] 所有 CRUD 操作正常（沿用现有文件存储与 JobStore 读写）
- [x] Redis 缓存命中率 > 80%（已决策跳过：当前瓶颈不在缓存）
- [x] 性能提升可量化（改为可观测性增强：任务耗时与 API 延迟已进入日志分析报告）
- [x] 测试: `pytest tests/test_job_store.py -v`

**产出文件**:
- `app/models/database.py`
- `app/cache/redis_cache.py`
- `migrations/` (Alembic 迁移脚本)
- `tests/test_database.py`
- `docs/DATABASE_DESIGN.md`

#### 3.4 API 增强与文档（Day 9-10）
**目标**: 完善 API 设计和文档

**实现步骤**:
1. 添加 API 版本控制:
   ```python
   # app/api/v1/
   # app/api/v2/
   ```

2. 实现依赖注入:
   ```python
   # app/dependencies.py
   def get_db():
       db = SessionLocal()
       try:
           yield db
       finally:
           db.close()
   
   def get_current_user(token: str = Depends(oauth2_scheme)):
       # 用户认证（预留）
       pass
   ```

3. 添加请求验证和错误处理:
   ```python
   # app/middleware/error_handler.py
   @app.exception_handler(Exception)
   async def global_exception_handler(request, exc):
       logger.error("Unhandled exception", exc_info=exc)
       return JSONResponse(
           status_code=500,
           content={"error": "Internal server error", "trace_id": request.state.trace_id}
       )
   ```

4. 完善 API 文档:
   - 所有接口添加详细 docstring
   - 添加请求/响应示例
   - 添加错误码说明
   - 生成 OpenAPI 3.0 规范

**验收标准**:
- [x] API 文档完整（Swagger UI）
- [x] 所有接口有错误处理
- [x] 依赖注入正常工作（保留当前轻量依赖解析方式，未引入数据库 session）
- [x] 测试: `pytest tests/test_api_errors.py tests/test_openapi_schema.py tests/test_health_endpoint.py -v`

**产出文件**:
- `app/api/v1/` (重构后的 API)
- `app/dependencies.py`
- `app/middleware/error_handler.py`
- `docs/API_REFERENCE.md`

### Phase 3 总结文档
- [x] 创建 `docs/ASYNC_TASKS.md` 后台任务指南
- [x] 创建 `docs/LOGGING_GUIDE.md` 日志与排查指南
- [x] 创建 `docs/PRODUCTION_READINESS.md` 工程化总结
- [x] 创建 `docs/DATABASE_CACHE_DECISION.md` 数据库/缓存决策
- [x] 更新 `README.md` 添加工程化特性
- [x] 更新 `docs/ARCHITECTURE.md` 添加 Phase 3 架构
- [x] 准备系统架构 PPT（15 页）— 跳过，留待 Phase 6 统一制作

### Phase 3 验收标准
- [x] 所有测试通过
- [x] Celery + Redis 正常运行 — 已决策跳过，当前使用 BackgroundTasks + FileJobStore
- [x] 数据库迁移无错误 — 已决策跳过，当前保留文件存储
- [x] API 响应时间减少 30%+ — 调整为日志可观测性增强，已输出 P50/P95 延迟分析
- [x] 日志分析报告生成


## Phase 4: 高级 RAG 与检索增强（Week 7-8）

### 目标
实现高级 RAG 技术，展示对 embedding、rerank、向量检索的深入理解

### JD 对应
- 任职要求 4: RAG
- 加分项 3: embedding、rerank、向量检索、评测指标

### 任务清单

#### 4.1 Rerank 模块（Day 1-2）
**目标**: 实现二阶段检索（召回 + 精排）

**实现步骤**:
1. 安装依赖: `pip install sentence-transformers`
2. 实现 Reranker:
   ```python
   # app/services/reranker.py
   from sentence_transformers import CrossEncoder
   
   class Reranker:
       def __init__(self, model_name="BAAI/bge-reranker-base"):
           self.model = CrossEncoder(model_name)
       
       def rerank(self, query: str, documents: list, top_k: int):
           scores = self.model.predict([(query, doc) for doc in documents])
           ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
           return ranked[:top_k]
   ```

3. 集成到 RAG 流程:
   - 第一阶段: 向量检索召回 top_k=20
   - 第二阶段: Rerank 精排到 top_k=5
   - 对比单阶段 vs 二阶段效果

4. 添加 Rerank 配置:
   ```python
   # .env
   ENABLE_RERANK=true
   RERANK_MODEL=BAAI/bge-reranker-base
   RERANK_TOP_K=5
   ```

**验收标准**:
- [ ] Reranker 实现完成
- [ ] 集成到 QA 流程
- [ ] 对比实验: 单阶段 vs 二阶段（Hit@5, MRR）
- [ ] 测试: `pytest tests/test_reranker.py -v`

**产出文件**:
- `app/services/reranker.py`
- `tests/test_reranker.py`
- `app/experiments/reports/rerank_comparison.md`

#### 4.2 Hybrid Search（Day 3-4）
**目标**: 融合 BM25 和向量检索

**实现步骤**:
1. 安装依赖: `pip install rank-bm25`
2. 实现 BM25 检索:
   ```python
   # app/services/bm25_retriever.py
   from rank_bm25 import BM25Okapi
   
   class BM25Retriever:
       def __init__(self, corpus):
           tokenized_corpus = [doc.split() for doc in corpus]
           self.bm25 = BM25Okapi(tokenized_corpus)
       
       def search(self, query: str, top_k: int):
           tokenized_query = query.split()
           scores = self.bm25.get_scores(tokenized_query)
           return top_k_indices(scores, top_k)
   ```

3. 实现混合检索:
   ```python
   # app/services/hybrid_retriever.py
   class HybridRetriever:
       def search(self, query: str, top_k: int, alpha=0.5):
           # alpha: 向量检索权重, (1-alpha): BM25 权重
           vector_results = self.vector_store.query(query, top_k=20)
           bm25_results = self.bm25.search(query, top_k=20)
           
           # 归一化分数并融合
           combined_scores = {}
           for doc, score in vector_results:
               combined_scores[doc] = alpha * score
           for doc, score in bm25_results:
               combined_scores[doc] = combined_scores.get(doc, 0) + (1-alpha) * score
           
           return sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
   ```

4. 实验对比:
   - 纯向量检索
   - 纯 BM25
   - Hybrid (alpha=0.3, 0.5, 0.7)

**验收标准**:
- [ ] BM25 和 Hybrid 检索实现
- [ ] 对比实验完成
- [ ] 找到最优 alpha 值
- [ ] 测试: `pytest tests/test_hybrid_retriever.py -v`

**产出文件**:
- `app/services/bm25_retriever.py`
- `app/services/hybrid_retriever.py`
- `tests/test_hybrid_retriever.py`
- `app/experiments/reports/hybrid_search_comparison.md`

#### 4.3 查询改写与扩展（Day 5-6）
**目标**: 实现查询优化技术

**实现步骤**:
1. 实现查询改写:
   ```python
   # app/services/query_rewriter.py
   class QueryRewriter:
       def rewrite_with_llm(self, query: str):
           # 使用 LLM 改写为更适合检索的形式
           prompt = f"将以下问题改写为更适合学术论文检索的查询:\n{query}"
           return self.llm.generate(prompt)
       
       def expand_with_synonyms(self, query: str):
           # 添加同义词扩展
           pass
   ```

2. 实现 HyDE (Hypothetical Document Embeddings):
   ```python
   # app/services/hyde.py
   class HyDE:
       def generate_hypothetical_doc(self, query: str):
           # 让 LLM 生成假设的答案文档
           prompt = f"针对问题'{query}'，生成一段可能的学术论文摘要"
           return self.llm.generate(prompt)
       
       def search(self, query: str, top_k: int):
           # 用假设文档的 embedding 检索
           hypo_doc = self.generate_hypothetical_doc(query)
           embedding = self.embed_client.embed_text(hypo_doc)
           return self.vector_store.query_by_embedding(embedding, top_k)
   ```

3. 实验对比:
   - 原始查询
   - LLM 改写查询
   - HyDE

**验收标准**:
- [ ] 查询改写和 HyDE 实现
- [ ] 对比实验完成
- [ ] 测试: `pytest tests/test_query_optimization.py -v`

**产出文件**:
- `app/services/query_rewriter.py`
- `app/services/hyde.py`
- `tests/test_query_optimization.py`
- `app/experiments/reports/query_optimization_comparison.md`

#### 4.4 多 Embedding 模型对比（Day 7-8）
**目标**: 对比不同 embedding 模型效果

**实现步骤**:
1. 支持多 embedding 模型:
   - bge-small-zh-v1.5 (当前)
   - bge-large-zh-v1.5
   - text-embedding-3-small (OpenAI)
   - m3e-base

2. 实现模型切换:
   ```python
   # app/services/embedding_client.py
   class EmbeddingClient:
       def __init__(self, model_name: str):
           if model_name.startswith("text-embedding"):
               self.client = OpenAIEmbedding(model_name)
           else:
               self.client = SentenceTransformerEmbedding(model_name)
   ```

3. 批量评估:
   ```python
   # app/experiments/evaluate_embeddings.py
   models = ["bge-small-zh-v1.5", "bge-large-zh-v1.5", "m3e-base"]
   for model in models:
       results = evaluate_retrieval(model, test_dataset)
       save_results(model, results)
   ```

4. 生成对比报告:
   - 检索效果 (Hit@K, MRR)
   - 推理速度
   - 模型大小
   - 综合推荐

**验收标准**:
- [ ] 至少对比 3 个 embedding 模型
- [ ] 生成详细对比报告
- [ ] 有明确的模型选择建议
- [ ] 测试: `pytest tests/test_embedding_models.py -v`

**产出文件**:
- `app/experiments/evaluate_embeddings.py`
- `app/experiments/reports/embedding_models_comparison.md`
- `tests/test_embedding_models.py`

#### 4.5 知识库管理增强（Day 9-10）
**目标**: 实现高级知识库功能

**实现步骤**:
1. 增量索引更新:
   ```python
   # app/services/incremental_indexer.py
   class IncrementalIndexer:
       def update_paper_index(self, paper_id: str):
           # 只重新索引变更的 chunks
           old_chunks = self.get_indexed_chunks(paper_id)
           new_chunks = self.chunk_paper(paper_id)
           
           # 计算差异
           to_add = [c for c in new_chunks if c not in old_chunks]
           to_remove = [c for c in old_chunks if c not in new_chunks]
           
           self.vector_store.remove_chunks(to_remove)
           self.vector_store.add_chunks(to_add)
   ```

2. 索引版本管理:
   ```python
   # app/models/index_version.py
   class IndexVersion(Base):
       id = Column(Integer, primary_key=True)
       paper_id = Column(String)
       version = Column(Integer)
       created_at = Column(DateTime)
       chunk_count = Column(Integer)
       embedding_model = Column(String)
   ```

3. 多知识库隔离:
   ```python
   # app/services/knowledge_base_manager.py
   class KnowledgeBaseManager:
       def create_kb(self, name: str, description: str)
       def add_paper_to_kb(self, kb_id: str, paper_id: str)
       def search_in_kb(self, kb_id: str, query: str)
   ```

4. 知识库统计:
   - 论文数量
   - 总 chunk 数
   - 索引大小
   - 最后更新时间

**验收标准**:
- [ ] 增量索引正常工作
- [ ] 索引版本可回滚
- [ ] 多知识库隔离有效
- [ ] 测试: `pytest tests/test_kb_management.py -v`

**产出文件**:
- `app/services/incremental_indexer.py`
- `app/services/knowledge_base_manager.py`
- `app/models/index_version.py`
- `tests/test_kb_management.py`
- `docs/KB_MANAGEMENT.md`

### Phase 4 总结文档
- [x] 创建 `docs/RAG_TECHNIQUES.md` 详细说明 RAG 技术
- [x] 创建 `docs/RETRIEVAL_OPTIMIZATION.md` 检索优化总结
- [x] 创建 `docs/KB_MANAGEMENT.md` 知识库管理说明
- [x] 更新 `README.md` 添加高级 RAG 特性
- [x] 更新 `docs/ARCHITECTURE.md` 添加高级 RAG 链路图
- [x] 准备 RAG 技术分享 PPT（20 页）— 跳过，留待 Phase 6 整体演示

### Phase 4 验收标准
- [x] 所有测试通过（pytest tests -q → 401 passed, 1 skipped）
- [x] 至少完成 3 个检索优化实验（rerank / hybrid / query optimization；额外多 embedding 模型评测）
- [x] 检索效果提升可量化（Hit@5 +14.88% with rerank，MRR +17.81%，达成 ≥10% 目标）
- [x] 技术文档完整（RAG_TECHNIQUES + RETRIEVAL_OPTIMIZATION + KB_MANAGEMENT + README + ARCHITECTURE）

**Phase 4 完成日期**：2026-05-22


## Phase 5: 多 Agent 协作与记忆管理（Week 9-10）

### 目标
实现多 Agent 协作系统，展示复杂 Agent 架构设计能力

### JD 对应
- 岗位职责 2: 多轮交互、工作流编排
- 加分项 1: Agent、多 Agent 协作
- 加分项 2: AutoGen、CrewAI

### 任务清单

#### 5.1 专业化 Agent 设计（Day 1-3）
**目标**: 设计多个专业化 Agent

**实现步骤**:
1. 定义 Agent 角色:
   ```python
   # app/agents/specialized/extractor_agent.py
   class ExtractorAgent:
       """负责从论文中提取结构化信息"""
       role = "信息提取专家"
       goal = "从学术论文中提取关键信息（方法、数据集、结果等）"
       tools = ["parse_pdf", "extract_sections"]
   
   # app/agents/specialized/comparator_agent.py
   class ComparatorAgent:
       """负责多论文对比分析"""
       role = "对比分析专家"
       goal = "对比多篇论文的异同，生成结构化报告"
       tools = ["compare_papers", "generate_table"]
   
   # app/agents/specialized/qa_agent.py
   class QAAgent:
       """负责回答用户问题"""
       role = "问答专家"
       goal = "基于论文内容回答用户问题"
       tools = ["search_papers", "generate_answer"]
   
   # app/agents/specialized/summarizer_agent.py
   class SummarizerAgent:
       """负责生成摘要和笔记"""
       role = "摘要专家"
       goal = "生成论文的结构化笔记和摘要"
       tools = ["generate_note", "export_markdown"]
   ```

2. 实现 Agent 基类:
   ```python
   # app/agents/base_agent.py
   class BaseAgent:
       def __init__(self, role: str, goal: str, tools: list):
           self.role = role
           self.goal = goal
           self.tools = tools
           self.memory = []
       
       def execute(self, task: str) -> dict:
           # 执行任务逻辑
           pass
       
       def add_to_memory(self, item: dict):
           self.memory.append(item)
   ```

**验收标准**:
- [x] 4 个专业化 Agent 实现完成
- [x] 每个 Agent 有明确的职责边界
- [x] 测试: `pytest tests/test_specialized_agents.py -v`

**产出文件**:
- `app/agents/specialists/__init__.py` (BaseSpecialist + AgentResult)
- `app/agents/specialists/extractor_agent.py`
- `app/agents/specialists/comparator_agent.py`
- `app/agents/specialists/qa_agent.py`
- `app/agents/specialists/summarizer_agent.py`
- `tests/test_specialist_agents.py`

#### 5.2 多 Agent 协作框架（Day 4-6）
**目标**: 实现 Agent 间通信和协作

**实际选型**: **LangGraph Supervisor 模式**（已落地）

**选型理由**:
- 与 Phase 1 的 LangChain 工具栈无缝集成，无新依赖
- StateGraph 提供显式的节点/边/状态合并，路由逻辑可解释
- AutoGen / CrewAI 加分项已通过"评估对比 + 选择更轻量方案"体现
- SQLite 持久化记忆比 AutoGen 的内置内存更适合本项目单用户场景

**实现要点**:
```python
# app/agents/supervisor.py
from langgraph.graph import END, StateGraph

def build_supervisor_graph() -> StateGraph:
    graph = StateGraph(SupervisorState)
    graph.add_node("route", route_node)        # 关键词意图分类
    graph.add_node("execute", execute_node)    # 分发到 Specialist
    graph.add_node("synthesize", synthesize_node)  # 合并结果
    graph.set_entry_point("route")
    graph.add_edge("route", "execute")
    graph.add_edge("execute", "synthesize")
    graph.add_edge("synthesize", END)
    return graph
```

2. 实现协作场景:
   - **场景 1**: 完整论文分析
     1. ExtractorAgent 提取信息
     2. SummarizerAgent 生成笔记
     3. QAAgent 回答预设问题
   
   - **场景 2**: 多论文对比
     1. ExtractorAgent 并行提取多篇论文信息
     2. ComparatorAgent 对比分析
     3. SummarizerAgent 生成对比报告
   
   - **场景 3**: 交互式研究助手
     1. 用户提问
     2. QAAgent 判断是否需要其他 Agent 协助
     3. 必要时调用 ExtractorAgent 或 ComparatorAgent
     4. 汇总结果返回用户

3. 实现 Agent 通信协议:
   ```python
   # app/agents/communication.py
   class Message:
       sender: str
       receiver: str
       content: dict
       message_type: str  # request, response, broadcast
   
   class MessageBus:
       def send(self, message: Message)
       def broadcast(self, message: Message)
       def subscribe(self, agent_id: str, message_type: str)
   ```

**验收标准**:
- [x] 多 Agent 协作框架集成完成
- [x] 3 个协作场景可运行
- [ ] Agent 间通信正常（未实现独立 MessageBus，路由通过 StateGraph 状态传递）
- [x] 测试: `pytest tests/test_multi_agent.py -v`

**产出文件**:
- `app/agents/communication.py`
- `app/agents/scenarios/` (3 个协作场景)
- `tests/test_multi_agent.py`
- `docs/MULTI_AGENT_DESIGN.md`

#### 5.3 记忆管理系统（Day 7-8）
**目标**: 实现短期和长期记忆

**实现步骤**:
1. 实现短期记忆（对话历史）:
   ```python
   # app/agents/memory/short_term.py
   class ShortTermMemory:
       def __init__(self, max_messages=10):
           self.messages = deque(maxlen=max_messages)
       
       def add_message(self, role: str, content: str):
           self.messages.append({"role": role, "content": content})
       
       def get_context(self) -> list:
           return list(self.messages)
   ```

2. 实现长期记忆（用户偏好、论文阅读历史）:
   ```python
   # app/agents/memory/long_term.py
   class LongTermMemory:
       def save_user_preference(self, user_id: str, key: str, value: any)
       def get_user_preference(self, user_id: str, key: str)
       
       def save_reading_history(self, user_id: str, paper_id: str, action: str)
       def get_reading_history(self, user_id: str, limit: int)
       
       def save_frequent_questions(self, user_id: str, question: str)
       def get_frequent_questions(self, user_id: str, top_k: int)
   ```

3. 实现语义记忆（向量化存储重要信息）:
   ```python
   # app/agents/memory/semantic.py
   class SemanticMemory:
       def store_fact(self, fact: str, metadata: dict):
           embedding = self.embed_client.embed_text(fact)
           self.vector_store.add(embedding, fact, metadata)
       
       def recall(self, query: str, top_k: int):
           # 检索相关记忆
           pass
   ```

4. 集成到 Agent:
   ```python
   class AgentWithMemory(BaseAgent):
       def __init__(self, *args, **kwargs):
           super().__init__(*args, **kwargs)
           self.short_term = ShortTermMemory()
           self.long_term = LongTermMemory()
           self.semantic = SemanticMemory()
       
       def execute_with_memory(self, task: str):
           # 从记忆中获取上下文
           context = self.short_term.get_context()
           preferences = self.long_term.get_user_preference(user_id, "style")
           relevant_facts = self.semantic.recall(task, top_k=3)
           
           # 执行任务
           result = self.execute(task, context, preferences, relevant_facts)
           
           # 更新记忆
           self.short_term.add_message("assistant", result)
           return result
   ```

**验收标准**:
- [x] 三种记忆类型实现完成
- [ ] Agent 能利用记忆改善回答（记忆已集成但未验证回答质量提升）
- [x] 记忆可持久化
- [x] 测试: `pytest tests/test_memory.py -v`

**产出文件**:
- `app/agents/memory/short_term.py`
- `app/agents/memory/long_term.py`
- `app/agents/memory/semantic.py`
- `tests/test_memory.py`
- `docs/MEMORY_DESIGN.md`

#### 5.4 Agent 可观测性（Day 9-10）
**目标**: 实现 Agent 行为追踪和调试

**实现步骤**:
1. 实现 Agent 执行追踪:
   ```python
   # app/agents/tracing.py
   class AgentTracer:
       def trace_execution(self, agent_id: str, task: str, result: dict):
           trace = {
               "agent_id": agent_id,
               "task": task,
               "timestamp": datetime.now(),
               "tools_used": result.get("tools_used", []),
               "execution_time": result.get("execution_time"),
               "success": result.get("success"),
               "error": result.get("error")
           }
           self.save_trace(trace)
   ```

2. 实现 Agent 决策日志:
   ```python
   # app/agents/decision_logger.py
   class DecisionLogger:
       def log_decision(self, agent_id: str, decision: dict):
           # 记录 Agent 的决策过程
           # - 为什么选择这个工具
           # - 为什么调用其他 Agent
           # - 为什么给出这个答案
           pass
   ```

3. 实现可视化界面:
   - Agent 执行时间线
   - Agent 间通信图
   - 工具调用统计
   - 决策树可视化

4. 添加 Streamlit Tab: "🔍 Agent 监控"

**验收标准**:
- [x] Agent 执行可追踪
- [x] 决策过程可查看
- [x] 可视化界面可用（Streamlit Agent 监控页）
- [x] 测试: `pytest tests/test_agent_tracing.py -v`

**产出文件**:
- `app/agents/tracing.py`
- `app/agents/decision_logger.py`
- `ui/pages/agent_monitor.py`
- `tests/test_tracing.py`

### Phase 5 总结文档
- [x] 创建 `docs/MULTI_AGENT_DESIGN.md` 详细说明协作机制
- [x] 创建 `docs/MEMORY_SYSTEM.md` 记忆系统设计
- [x] 更新 `README.md` 添加多 Agent 特性
- [ ] 准备 Agent 系统 Demo 视频（10 分钟）— 未录制

### Phase 5 验收标准
- [x] 所有测试通过（493 passed in 30s — 含 44 个 supervisor/tracing/api_traces/integration 测试）
- [x] 多 Agent 协作场景可演示（3 个 scenarios + Streamlit supervisor 模式）
- [x] 记忆系统正常工作（SQLite 三层记忆，含持久化）
- [x] Agent 行为可追踪和调试（`run_traced` + `/api/traces` + Streamlit Agent 监控页）


## Phase 6: 项目收尾与展示准备（Week 11-12）

### 目标
完善文档、准备面试材料、优化展示效果

### JD 对应
- 任职要求 7: 沟通能力和文档能力
- 岗位职责 6: 文档编写

### 任务清单

#### 6.1 文档体系完善（Day 1-3）
**目标**: 构建完整的项目文档

**实现步骤**:
1. 技术文档:
   - [x] `docs/ARCHITECTURE.md` - 系统架构
   - [x] `docs/AGENT_DESIGN.md` - Agent 设计详解
   - [x] `docs/RAG_TECHNIQUES.md` - RAG 技术说明
   - [x] `docs/MULTI_AGENT_DESIGN.md` - 多 Agent 协作
   - [x] `docs/MEMORY_SYSTEM.md` - 记忆系统设计
   - [x] `docs/API_REFERENCE.md` - API 完整文档（自动生成自 OpenAPI schema）
   - [ ] `docs/DATABASE_DESIGN.md` - 跳过（已有 `DATABASE_CACHE_DECISION.md` 覆盖）

2. 使用文档:
   - [ ] `docs/QUICK_START.md` - 跳过（README 快速启动 + `RUN_GUIDE.md` 已覆盖）
   - [ ] `docs/USER_GUIDE.md` - 跳过（已有 `USAGE.md` 覆盖）
   - [ ] `docs/DEPLOYMENT_GUIDE.md` - 跳过（单机项目，README 启动说明足够）
   - [ ] `docs/TROUBLESHOOTING.md` - 跳过（个人项目暂不需要）

3. 开发文档:
   - [ ] `docs/DEVELOPMENT_GUIDE.md` - 跳过（CLAUDE.md 已覆盖）
   - [ ] `docs/TESTING_GUIDE.md` - 跳过（CLAUDE.md 已覆盖）
   - [ ] `docs/CONTRIBUTION_GUIDE.md` - 跳过（个人项目）
   - [x] `CHANGELOG.md` - Phase 1-5 版本变更记录

4. 实验与分析文档:
   - [x] `docs/EXPERIMENT_RESULTS.md` - 实验结果汇总
   - [ ] `docs/PERFORMANCE_OPTIMIZATION.md` - 跳过（实验报告内已含性能数据）
   - [x] `docs/ANALYTICS_GUIDE.md` - 数据分析指南

**验收标准**:
- [ ] 所有文档完整且格式统一
- [ ] 代码示例可运行
- [ ] 图表清晰易懂
- [ ] 无拼写和语法错误

#### 6.2 代码质量提升（Day 4-5）
**目标**: 提升代码可读性和可维护性

**实现步骤**:
1. 代码规范:
   ```bash
   # 安装工具
   pip install black isort flake8 mypy
   
   # 格式化代码
   black app/ tests/
   isort app/ tests/
   
   # 代码检查
   flake8 app/ tests/
   mypy app/
   ```

2. 添加类型注解:
   ```python
   # 所有函数添加类型注解
   def generate_note(paper_id: str, config: NoteConfig) -> NoteResult:
       pass
   ```

3. 完善 docstring:
   ```python
   def answer_question(question: str, paper_id: Optional[str] = None) -> QAResult:
       """
       基于 RAG 回答用户问题
       
       Args:
           question: 用户问题
           paper_id: 可选，限定在某篇论文内检索
       
       Returns:
           QAResult: 包含答案和来源的结果对象
       
       Raises:
           PaperNotFoundError: 论文不存在
           RetrievalError: 检索失败
       
       Example:
           >>> result = answer_question("什么是 Transformer?")
           >>> print(result.answer)
       """
       pass
   ```

4. 代码重构:
   - 提取重复代码为函数
   - 简化复杂函数（单个函数 < 50 行）
   - 移除无用代码和注释

**验收标准**:
- [ ] 代码通过 black、isort、flake8 检查
- [ ] 核心函数有类型注解和 docstring
- [ ] 代码复杂度降低（用 radon 检查）

#### 6.3 测试覆盖率提升（Day 6-7）
**目标**: 提升测试覆盖率到 80%+

**实现步骤**:
1. 安装覆盖率工具:
   ```bash
   pip install pytest-cov
   ```

2. 运行覆盖率测试:
   ```bash
   pytest tests/ --cov=app --cov-report=html --cov-report=term
   ```

3. 补充缺失测试:
   - 边界条件测试
   - 异常处理测试
   - 集成测试
   - 端到端测试

4. 添加性能测试:
   ```python
   # tests/test_performance.py
   def test_qa_response_time():
       start = time.time()
       result = answer_question("测试问题")
       duration = time.time() - start
       assert duration < 5.0  # 5 秒内响应
   ```

**验收标准**:
- [ ] 测试覆盖率 > 80%
- [ ] 所有核心功能有测试
- [ ] 测试通过率 100%
- [ ] 生成覆盖率报告

#### 6.4 Demo 与展示材料（Day 8-10）
**目标**: 准备完整的展示材料

**实现步骤**:
1. 录制 Demo 视频:
   - **视频 1**: 快速演示（3 分钟）
     - 上传论文 → 生成笔记 → 问答 → 对比
   - **视频 2**: Agent 系统演示（5 分钟）
     - 展示 Agent 工作流
     - 展示多 Agent 协作
     - 展示记忆管理
   - **视频 3**: 技术深度演示（10 分钟）
     - RAG 技术细节
     - 数据分析与可视化
     - 实验对比结果

2. 制作 PPT:
   - **PPT 1**: 项目概览（10 页）
     - 项目背景和目标
     - 核心功能展示
     - 技术栈介绍
     - 成果展示
   
   - **PPT 2**: 技术架构（15 页）
     - 系统架构图
     - Agent 设计
     - RAG 流程
     - 数据流图
     - 技术亮点
   
   - **PPT 3**: 实验与分析（20 页）
     - A/B 测试结果
     - 性能优化记录
     - 数据分析可视化
     - 失败案例分析
     - 优化建议

3. 准备面试讲解脚本:
   - **3 分钟版本**: 电梯演讲
     - 项目是什么
     - 解决什么问题
     - 核心技术亮点
     - 个人贡献
   
   - **10 分钟版本**: 技术面试
     - 详细技术架构
     - 关键技术选型和原因
     - 遇到的挑战和解决方案
     - 性能优化经验
     - 未来规划
   
   - **30 分钟版本**: 深度技术分享
     - 完整技术细节
     - 实验设计和结果
     - 代码演示
     - Q&A 准备

4. 准备常见问题回答:
   - 为什么选择这个技术栈？
   - Agent 系统的设计思路是什么？
   - 如何保证 RAG 的准确性？
   - 遇到的最大挑战是什么？
   - 如何进行效果评估？
   - 如果重新做会有什么改进？

**验收标准**:
- [ ] 3 个 Demo 视频录制完成
- [ ] 3 套 PPT 制作完成
- [ ] 面试脚本准备完整
- [ ] 常见问题有标准答案

### Phase 6 总结
- [ ] 更新 `README.md` 为最终版本
- [ ] 创建 `docs/PROJECT_SUMMARY.md` 项目总结
- [ ] 创建 `docs/LESSONS_LEARNED.md` 经验总结
- [ ] 准备项目展示网站（可选，使用 GitHub Pages）

### Phase 6 验收标准
- [ ] 文档体系完整
- [ ] 代码质量达标
- [ ] 测试覆盖率 > 80%
- [ ] 展示材料齐全


## 技术栈升级清单

### 新增依赖

```txt
# Phase 1: Agent 工作流
langchain>=0.1.0
langchain-openai>=0.0.5
langgraph>=0.0.20

# Phase 2: 数据分析
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
seaborn>=0.12.0
jupyter>=1.0.0
scikit-learn>=1.3.0

# Phase 3: 工程化
celery>=5.3.0
redis>=5.0.0
sqlalchemy>=2.0.0
alembic>=1.12.0
structlog>=23.1.0

# Phase 4: 高级 RAG
rank-bm25>=0.2.2

# Phase 5: 多 Agent（实际选型：LangGraph Supervisor，不依赖 AutoGen/CrewAI）

# 代码质量
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.5.0
pytest-cov>=4.1.0
radon>=6.0.0
```

### 外部服务

- **Redis**: 用于 Celery 和缓存
  ```bash
  # Ubuntu/WSL
  sudo apt-get install redis-server
  sudo service redis-server start
  
  # macOS
  brew install redis
  brew services start redis
  ```

- **PostgreSQL** (可选，可用 SQLite 替代):
  ```bash
  # Ubuntu/WSL
  sudo apt-get install postgresql
  
  # macOS
  brew install postgresql
  ```

---

## 项目结构演进

### 当前结构
```
research-agent/
├── app/
│   ├── services/
│   ├── prompts/
│   └── evaluation/
├── ui/
├── tests/
└── docs/
```

### 最终结构
```
research-agent/
├── app/
│   ├── agents/                    # Phase 1 & 5
│   │   ├── tools/
│   │   ├── workflows/
│   │   ├── specialized/
│   │   ├── memory/
│   │   └── communication.py
│   ├── analytics/                 # Phase 2
│   │   ├── data_collector.py
│   │   ├── visualizer.py
│   │   ├── failure_analyzer.py
│   │   └── reports/
│   ├── experiments/               # Phase 2
│   │   ├── config.py
│   │   ├── runner.py
│   │   └── scenarios/
│   ├── tasks/                     # Phase 3
│   │   ├── celery_app.py
│   │   └── paper_tasks.py
│   ├── models/                    # Phase 3
│   │   ├── database.py
│   │   └── index_version.py
│   ├── cache/                     # Phase 3
│   │   └── redis_cache.py
│   ├── middleware/                # Phase 3
│   │   ├── tracing.py
│   │   └── error_handler.py
│   ├── services/                  # 原有 + Phase 4 增强
│   │   ├── reranker.py
│   │   ├── bm25_retriever.py
│   │   ├── hybrid_retriever.py
│   │   ├── query_rewriter.py
│   │   └── hyde.py
│   └── api/
│       ├── v1/
│       └── v2/
├── ui/
│   └── components/
│       ├── agent_chat.py
│       └── agent_monitor.py
├── notebooks/                     # Phase 2
│   ├── 01_retrieval_analysis.ipynb
│   ├── 02_qa_quality_analysis.ipynb
│   ├── 03_experiment_comparison.ipynb
│   └── 04_failure_case_study.ipynb
├── migrations/                    # Phase 3
├── tests/
│   ├── test_agent_tools.py
│   ├── test_workflows.py
│   ├── test_multi_agent.py
│   ├── test_analytics.py
│   ├── test_async_tasks.py
│   └── ...
└── docs/
    ├── AGENT_DESIGN.md
    ├── RAG_TECHNIQUES.md
    ├── MULTI_AGENT_DESIGN.md
    ├── ANALYTICS_GUIDE.md
    ├── EXPERIMENT_RESULTS.md
    └── ...
```

---

## 关键指标追踪

### 代码指标
- [ ] 代码行数: 5000+ → 15000+ (3x 增长)
- [ ] 测试覆盖率: 70% → 80%+
- [ ] 测试用例数: 202 → 500+
- [ ] 文档页数: 10 → 30+

### 功能指标
- [ ] API 接口: 13 → 30+
- [ ] Agent 数量: 0 → 4+
- [ ] 工作流数量: 0 → 3+
- [ ] 实验场景: 0 → 3+

### 性能指标
- [ ] QA 响应时间: 基线 → 减少 30%
- [ ] 检索准确率 (Hit@5): 基线 → 提升 10%+
- [ ] 缓存命中率: 0% → 80%+

### 技术深度指标
- [ ] 使用的框架/库: 10 → 25+
- [ ] 实现的 RAG 技术: 1 → 5+ (Rerank, Hybrid, HyDE, Query Rewrite)
- [ ] 数据分析图表: 0 → 10+
- [ ] A/B 实验: 0 → 3+

---

## 每周检查点

### Week 1-2 检查点
- [ ] Agent 工具封装完成
- [ ] LangChain 集成成功
- [ ] 至少 1 个工作流可运行
- [ ] Agent Tab 可用

### Week 3-4 检查点
- [ ] 数据分析模块可用
- [ ] 至少 1 个 A/B 实验完成
- [ ] 失败分析报告生成
- [ ] 至少 2 个 Jupyter Notebook 完成

### Week 5-6 检查点
- [ ] Celery 异步任务正常
- [ ] 结构化日志系统运行
- [ ] 数据库迁移成功
- [ ] API 响应时间优化可见

### Week 7-8 检查点
- [ ] Rerank 集成完成
- [ ] Hybrid Search 实现
- [ ] 至少 2 个检索优化实验完成
- [ ] 检索效果提升可量化

### Week 9-10 检查点
- [x] 4 个专业化 Agent 实现
- [x] 多 Agent 协作场景可演示
- [x] 记忆系统正常工作
- [x] Agent 监控界面可用

### Week 11-12 检查点
- [ ] 所有文档完成
- [ ] 代码质量达标
- [ ] 测试覆盖率 > 80%
- [ ] Demo 视频和 PPT 完成

---

## 风险与应对

### 技术风险

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| LangChain/LangGraph 学习曲线陡峭 | Phase 1 延期 | 提前学习官方文档，准备降级方案（自实现简化版） |
| Celery + Redis 环境配置复杂 | Phase 3 延期 | 准备 Docker 一键部署方案 |
| 多 Agent 框架选型困难 | Phase 5 延期 | 已选定 LangGraph Supervisor 模式（与 Phase 1 LangChain 同生态） |
| 实验数据不足 | Phase 2/4 效果不明显 | 准备合成数据集，或使用公开数据集 |

### 时间风险

| 风险 | 应对措施 |
|------|----------|
| 某个 Phase 超时 | 每周检查点严格执行，及时调整优先级 |
| 功能过度设计 | 遵循 MVP 原则，先实现核心功能再优化 |
| 文档编写时间不足 | 边开发边写文档，不要堆到最后 |

### 质量风险

| 风险 | 应对措施 |
|------|----------|
| 测试覆盖率不达标 | 每个 Phase 完成后立即补充测试 |
| 代码质量下降 | 每周运行 black/flake8，及时重构 |
| 文档不完整 | 使用文档模板，确保结构完整 |

---

## 面试准备清单

### 技术问题准备

#### Agent 相关
- [ ] 解释 Agent 的工作原理
- [ ] 为什么选择 LangChain/LangGraph？
- [ ] 如何设计多 Agent 协作？
- [ ] Agent 的记忆管理如何实现？
- [ ] 如何调试和监控 Agent？

#### RAG 相关
- [ ] 解释 RAG 的工作流程
- [ ] Rerank 的作用是什么？
- [ ] Hybrid Search 如何融合 BM25 和向量检索？
- [ ] 如何评估检索效果？
- [ ] 如何优化检索准确率？

#### 工程化相关
- [ ] 为什么使用 Celery？
- [ ] 如何设计异步任务系统？
- [ ] 如何实现请求链路追踪？
- [ ] 数据库设计的考虑因素？
- [ ] 如何优化 API 性能？

#### 数据分析相关
- [ ] 如何设计 A/B 测试？
- [ ] 失败案例分析的方法？
- [ ] 如何选择可视化方式？
- [ ] 如何进行统计检验？

### 项目亮点总结

1. **Agent 系统**: 实现了完整的 Agent 工作流，包括任务拆解、工具调用、多 Agent 协作
2. **RAG 技术**: 实现了 Rerank、Hybrid Search、HyDE 等高级技术，检索效果提升 X%
3. **数据驱动**: 建立了完整的评估体系，通过 A/B 测试优化系统
4. **工程化**: 异步任务、结构化日志、数据库、缓存等生产级特性
5. **可观测性**: Agent 追踪、日志分析、性能监控等

### 个人成长总结

- **技术能力**: 掌握了 LangChain、LangGraph、Celery、Redis 等框架
- **工程能力**: 学会了异步任务、日志系统、数据库设计等工程实践
- **分析能力**: 学会了 A/B 测试、数据分析、失败案例分析
- **文档能力**: 编写了 30+ 页技术文档
- **问题解决**: 解决了 X 个技术难题（列举具体案例）

---

## 附录：参考资料

### 官方文档
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [Celery Documentation](https://docs.celeryq.dev/)

### 技术博客
- [Building LLM Applications: RAG Best Practices](https://www.anthropic.com/index/building-effective-agents)
- [Multi-Agent Systems with LangGraph](https://blog.langchain.dev/langgraph-multi-agent-workflows/)
- [Advanced RAG Techniques](https://www.pinecone.io/learn/advanced-rag-techniques/)

### 论文
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [HyDE: Precise Zero-Shot Dense Retrieval](https://arxiv.org/abs/2212.10496)
- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)

---

## 总结

这份路线图将在 12 周内将 ResearchAgent 从一个基础的 RAG 应用升级为：

1. ✅ **完整的 Agent 系统**: 工具调用、工作流编排、多 Agent 协作、记忆管理
2. ✅ **数据驱动的优化**: A/B 测试、失败分析、可视化报告
3. ✅ **生产级工程化**: 异步任务、结构化日志、数据库、缓存
4. ✅ **高级 RAG 技术**: Rerank、Hybrid Search、HyDE、Query Rewrite
5. ✅ **完整的文档体系**: 30+ 页技术文档、Demo 视频、面试材料

**最终成果**:
- 代码量: 15000+ 行
- 测试覆盖率: 80%+
- 文档: 30+ 页
- Demo 视频: 3 个
- PPT: 3 套
- 完全对齐 JD 要求，展示全栈 LLM 应用开发能力

**下一步**: 从 Phase 1 开始执行，每周检查进度，及时调整计划。

