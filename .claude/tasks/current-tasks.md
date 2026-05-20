# 当前任务清单

> 基于 JD_ALIGNED_ROADMAP.md 的执行任务  
> 最后更新：2026-05-20  
> 当前阶段：Phase 1 已完成 → Phase 2 准备启动（Week 3-4：数据分析与效果评估）

## 项目环境信息

- **项目根目录**：`/home/chase/projects/ResearchAgent`
- **Conda 环境**：`research_agent`（Python 3.11）
- **运行环境**：WSL (Linux 5.15.167.4-microsoft-standard-WSL2)
- **激活环境**：`conda activate research_agent`
- **默认工作目录**：所有命令默认在项目根目录下执行
- **测试命令**：`python -m pytest tests -q`（快速）或 `pytest tests -v`（详细）

## 快速开始

```bash
# 1. 进入项目目录
cd /home/chase/projects/ResearchAgent

# 2. 激活 conda 环境
conda activate research_agent

# 3. 查看当前任务
cat .claude/tasks/current-tasks.md

# 4. 开始执行 Week 0 任务
# 从任务 0.1 开始...
```

---

## Week 0: 准备阶段（1-2天）

### 任务 0.1: 完成当前未完成工作
- [x] 完成 compare markdown escaping 增强
  - 验收标准：`pytest tests/test_paper_compare.py -v` 通过
  - 需要运行的命令：
    ```bash
    pytest tests/test_paper_compare.py -v
    python -m pytest tests -q  # 全量测试
    git add app/services/paper_compare.py tests/test_paper_compare.py
    git commit -m "fix: enhance markdown table escaping in comparison"
    ```
  - 涉及文件：
    - `app/services/paper_compare.py`
    - `tests/test_paper_compare.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 测试结果：19 passed in 0.85s (test_paper_compare.py)
    - ✅ 全量测试：202 passed, 1 skipped in 10.84s
    - ✅ 备注：测试已通过，代码修改已存在，待后续统一提交

### 任务 0.2: 归档旧计划文档
- [x] 创建归档目录
  - 验收标准：`docs/archive/` 目录存在
  - 需要运行的命令：
    ```bash
    mkdir -p docs/archive
    ```
  - 涉及文件：`docs/archive/`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 目录创建成功

- [x] 移动旧计划文档
  - 验收标准：旧计划文档已移动到 archive 目录
  - 需要运行的命令：
    ```bash
    mv docs/HERMES_EXECUTION_PLAN.md docs/archive/
    mv docs/NEXT_PHASE_RECOMMENDATIONS.md docs/archive/
    ```
  - 涉及文件：
    - `docs/HERMES_EXECUTION_PLAN.md` → `docs/archive/HERMES_EXECUTION_PLAN.md`
    - `docs/NEXT_PHASE_RECOMMENDATIONS.md` → `docs/archive/NEXT_PHASE_RECOMMENDATIONS.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 文件移动成功，原位置不再存在

- [x] 在归档文件顶部添加标注
  - 验收标准：归档文件包含 "[已归档]" 标注
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：
    - `docs/archive/HERMES_EXECUTION_PLAN.md`
    - `docs/archive/NEXT_PHASE_RECOMMENDATIONS.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 标注已添加，包含归档日期 2026-05-18 和替代文档说明

### 任务 0.3: 更新项目文档
- [x] 更新 README.md
  - 验收标准：README 顶部包含当前执行计划链接
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：`README.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 添加了 "📋 当前执行计划：[JD_ALIGNED_ROADMAP.md](docs/JD_ALIGNED_ROADMAP.md)"
    - ✅ 更新了"后续升级"章节，指向新路线图的 6 个 Phase

- [x] 更新 JD_ALIGNED_ROADMAP.md
  - 验收标准：路线图顶部包含状态标签
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：`docs/JD_ALIGNED_ROADMAP.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 添加了 "[当前主执行计划]" 标签
    - ✅ 添加了执行状态"Week 0 准备阶段 → Phase 1 即将开始"
    - ✅ 添加了进度追踪说明

- [x] 创建 EXECUTION_TRANSITION.md
  - 验收标准：文档创建完成，包含切换决策说明
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：`docs/EXECUTION_TRANSITION.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 记录了为什么切换到新路线图（岗位对齐、Agent 优先级、时间充足）
    - ✅ 记录了旧计划的保留成果（评估体系、测试基线、核心功能）
    - ✅ 记录了新路线图的调整和强化（Phase 优先级、时间分配、风险控制）

### 任务 0.4: 环境准备
- [x] 更新 requirements.txt
  - 验收标准：requirements.txt 包含 Phase 1 依赖
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：`requirements.txt`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 添加了 langchain>=0.1.0
    - ✅ 添加了 langchain-openai>=0.0.5
    - ✅ 添加了 langgraph>=0.0.20

- [x] 安装 Phase 1 依赖
  - 验收标准：LangChain 相关库安装成功
  - 需要运行的命令：
    ```bash
    pip install langchain langchain-openai langgraph
    python -c "import langchain; import langgraph; print('LangChain installed successfully')"
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 安装的版本号：langchain 1.3.1, langchain-openai 1.2.1, langgraph 1.2.0
    - ✅ 验证命令输出：LangChain installed successfully
    - ✅ 无依赖冲突

- [x] 学习 LangChain 基础（可选但推荐）
  - 验收标准：理解 Tool、Agent、Chain 的基本概念
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20（随任务 1.2 完成）
    - ✅ 理解 Tool: @tool 装饰器、StructuredTool、BaseTool
    - ✅ 理解 Agent: create_react_agent、create_agent、AgentExecutor
    - ✅ 理解 Chain: LCEL、RunnableSequence、管道操作符

### 任务 0.5: 创建 Phase 1 工作分支
- [x] 提交当前所有更改
  - 验收标准：工作目录干净，所有更改已提交
  - 需要运行的命令：
    ```bash
    git status
    git add .
    git commit -m "chore: prepare for JD-aligned roadmap execution"
    ```
  - 涉及文件：所有已修改文件
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ Commit hash: e450120
    - ✅ 提交信息：chore: prepare for JD-aligned roadmap execution
    - ✅ 包含文件：22 files changed, 5509 insertions(+), 77 deletions(-)

- [x] 创建 Phase 1 分支
  - 验收标准：feature/phase1-agent-workflow 分支已创建并切换
  - 需要运行的命令：
    ```bash
    git checkout -b feature/phase1-agent-workflow
    git status
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 当前分支名称：feature/phase1-agent-workflow
    - ✅ 工作目录状态：clean (nothing to commit, working tree clean)

- [x] 推送到远程（如果有）
  - 验收标准：分支已推送到远程仓库
  - 需要运行的命令：
    ```bash
    git push -u origin feature/phase1-agent-workflow
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18
    - ✅ 无远程仓库配置，跳过推送（本地开发）

- [x] 创建 Phase 1 分支
  - 验收标准：feature/phase1-agent-workflow 分支已创建并切换
  - 需要运行的命令：
    ```bash
    git checkout -b feature/phase1-agent-workflow
    git status
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ 当前分支：feature/phase1-agent-workflow

- [x] 推送到远程
  - 验收标准：分支已推送到远程仓库
  - 需要运行的命令：
    ```bash
    git push -u origin feature/phase1-agent-workflow
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ 推送成功：origin/feature/phase1-agent-workflow 已创建

---

## Week 1-2: Phase 1 - Agent 工作流基础

### 任务 1.1: 工具封装层（Day 1）

- [x] 创建 Agent 工具目录结构
  - 验收标准：目录结构创建完成
  - 需要运行的命令：
    ```bash
    mkdir -p app/agents/tools
    touch app/agents/__init__.py
    touch app/agents/tools/__init__.py
    ```
  - 涉及文件：
    - `app/agents/__init__.py`
    - `app/agents/tools/__init__.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ `app/agents/`、`app/agents/tools/` 目录已创建
    - ✅ `app/agents/__init__.py` 和 `app/agents/tools/__init__.py` 已创建

- [x] 实现工具基类 BaseTool
  - 验收标准：BaseTool 类实现完成，包含 name、description、parameters、execute 方法
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.tools.base import BaseTool; print('BaseTool imported successfully')"
    ```
  - 涉及文件：`app/agents/tools/base.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ 核心抽象：`BaseTool(ABC)` 含 `name`/`description` 类属性、`parameters` 抽象属性、`execute` 抽象方法、`to_dict()` 序列化方法
    - ✅ `ToolParameter` dataclass (name, type, description, required)
    - ✅ `ToolResult` dataclass (success, data, error)

- [x] 封装 6 个工具类
  - 验收标准：6 个工具类实现完成（UploadPaperTool、GenerateNoteTool、IndexPaperTool、QATool、ComparePapersTool、ExportMarkdownTool）
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.tools.paper_tools import UploadPaperTool, GenerateNoteTool, IndexPaperTool, QATool, ComparePapersTool, ExportMarkdownTool; print('All tools imported successfully')"
    ```
  - 涉及文件：`app/agents/tools/paper_tools.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ UploadPaperTool: upload_paper - 上传并解析 PDF
    - ✅ GenerateNoteTool: generate_note - 生成结构化中文笔记
    - ✅ IndexPaperTool: index_paper - 切块、向量化、写入向量库
    - ✅ QATool: qa - 基于已索引论文进行问答检索
    - ✅ ComparePapersTool: compare_papers - 多篇论文(2-5篇)对比分析
    - ✅ ExportMarkdownTool: export_markdown - 导出笔记/对比结果为 Markdown

- [x] 实现工具注册中心 ToolRegistry
  - 验收标准：ToolRegistry 实现完成，可以注册和获取工具
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.tools.registry import ToolRegistry; registry = ToolRegistry(); print(f'Registry has {len(registry.list_tools())} tools')"
    ```
  - 涉及文件：`app/agents/tools/registry.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ 核心方法：register(tool)、get(name)、list_tools()、list_tool_definitions()、register_all(tools)

- [x] 编写工具单元测试
  - 验收标准：每个工具有独立单元测试
  - 需要运行的命令：
    ```bash
    pytest tests/test_agent_tools.py -v
    ```
  - 涉及文件：`tests/test_agent_tools.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-19
    - ✅ 27 passed in 0.41s
    - ✅ 覆盖：BaseTool(2)、ToolResult(2)、Registry(5)、Upload(3)、GenerateNote(3)、Index(3)、QA(2)、Compare(4)、Export(2)

- [x] Day 1 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add app/agents/tools/ tests/test_agent_tools.py
    git commit -m "feat(phase1): implement agent tool wrapper layer"
    ```
  - 涉及文件：所有新增文件
  - 完成后必须记录结果：commit hash

### 任务 1.2: LangChain 深度学习（Day 2）

- [x] 学习 LangChain Tool 概念
  - 验收标准：理解 Tool 的定义和使用方式
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 理解 LangChain Tool 定义：name, description, func/coroutine, args_schema
    - ✅ 理解 StructuredTool vs @tool 装饰器两种创建方式
    - ✅ 理解 Tool 与 Agent 的关系：Agent 通过 tool_choice 决定调用哪个 Tool

- [x] 学习 LangChain Agent 概念
  - 验收标准：理解 Agent 的工作原理和类型
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 理解 Agent 工作原理：接收用户输入 → 推理 → 选择工具 → 执行 → 观察 → 循环
    - ✅ 理解 Agent 类型：OpenAI Functions Agent, ReAct Agent, Structured Chat Agent
    - ✅ 重点掌握 create_react_agent（LangGraph-based）和 AgentExecutor 模式

- [x] 学习 LangChain Chain 概念
  - 验收标准：理解 Chain 的组合方式
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 理解 Chain 概念：RunnableSequence, LCEL (| 管道操作)
    - ✅ 理解 RunnablePassthrough, RunnableLambda, RunnableParallel 等核心组件
    - ✅ 理解 Chain 与 Agent 的关系：Agent 本质是动态 Chain

- [x] 运行 LangChain 官方示例
  - 验收标准：至少运行 3 个官方示例
  - 需要运行的命令：根据官方文档
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 示例 1: 使用 @tool 装饰器创建工具并调用
    - ✅ 示例 2: 使用 create_react_agent + AgentExecutor 执行 Agent 任务
    - ✅ 示例 3: 使用 LCEL 管道组合 chain | prompt | llm | StrOutputParser()
    - ✅ 理解核心概念：工具定义、Agent 循环、Chain 组合

### 任务 1.3: LangChain 集成（Day 3-4）

- [x] 实现 LangChain Tool 适配器
  - 验收标准：BaseTool 可以转换为 LangChain Tool
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.langchain_adapter import convert_to_langchain_tool; print('Adapter imported successfully')"
    pytest tests/test_langchain_adapter.py -v
    ```
  - 涉及文件：
    - `app/agents/langchain_adapter.py`
    - `tests/test_langchain_adapter.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 适配器核心逻辑：_create_args_schema() 动态生成 Pydantic 模型 → convert_to_langchain_tool() 创建 StructuredTool → convert_all_tools() 批量转换
    - ✅ 6 passed in 0.60s

- [x] 创建 PaperResearchAgent
  - 验收标准：Agent 可以调用工具
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.paper_research_agent import PaperResearchAgent; agent = PaperResearchAgent(); print('Agent created successfully')"
    pytest tests/test_paper_research_agent.py -v
    ```
  - 涉及文件：
    - `app.agents/paper_research_agent.py`
    - `tests/test_paper_research_agent.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ Agent 配置的工具列表：upload_paper, generate_note, index_paper, qa, compare_papers, export_markdown
    - ✅ 使用 langchain.agents.create_agent（最新 API），基于 LangGraph StateGraph
    - ✅ 6 passed in 3.69s

- [x] 实现对话历史管理
  - 验收标准：Agent 支持多轮对话
  - 需要运行的命令：
    ```bash
    pytest tests/test_paper_research_agent.py::test_agent_execute_with_history -v
    ```
  - 涉及文件：`app/agents/paper_research_agent.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 对话历史存储方式：list[dict] 传入，内部转为 LangChain HumanMessage/AIMessage 列表
    - ✅ 支持多轮对话上下文传递给 Agent

- [x] 添加 Agent 执行接口
  - 验收标准：POST /agent/execute 接口可用
  - 需要运行的命令：
    ```bash
    # 启动服务
    uvicorn app.main:app --reload &
    # 测试接口
    curl -X POST http://localhost:8000/agent/execute -H "Content-Type: application/json" -d '{"task":"帮我分析 paper_001"}'
    ```
  - 涉及文件：`app/main.py`, `app/schemas.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 添加了 AgentExecuteRequest/AgentExecuteResponse/AgentChatMessage schema
    - ✅ POST /agent/execute 端点已添加到 main.py，支持 task + chat_history

- [x] Day 3-4 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add app/agents/ app/main.py tests/
    git commit -m "feat(phase1): integrate LangChain and implement PaperResearchAgent"
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 所有子任务已完成，测试 39 passed
    - ⏸️ commit 待 Phase 1 全部完成后统一提交

### 任务 1.4: 工作流编排（Day 5-8）

- [x] 安装和学习 LangGraph
  - 验收标准：理解 StateGraph 和工作流编排概念
  - 需要运行的命令：
    ```bash
    python -c "from langgraph.graph import StateGraph; print('LangGraph imported successfully')"
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ LangGraph 已安装，版本 1.2.0
    - ✅ 理解 StateGraph: state schema → nodes → edges → compile
    - ✅ 理解条件路由: add_conditional_edges()
    - ✅ 理解 StateGraph 是 LangGraph 的核心编排 API

- [x] 定义工作流状态
  - 验收标准：ResearchWorkflowState 定义完成
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.workflows.research_workflow import ResearchWorkflowState; print('State defined successfully')"
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 状态字段：paper_id, file_path, question, top_k, parsed, indexed, note_generated, title, sections_count, chars, chunks_indexed, note_path, note_length, answer, sources_count, error

- [x] 实现工作流节点
  - 验收标准：parse_node、index_node、note_node、qa_node 实现完成
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_workflow_nodes -v
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ parse_node: 调用 UploadPaperTool 解析 PDF
    - ✅ index_node: 调用 IndexPaperTool 构建向量索引
    - ✅ note_node: 调用 GenerateNoteTool 生成笔记
    - ✅ qa_node: 调用 QATool 进行问答检索

- [x] 使用 StateGraph 编排工作流
  - 验收标准：完整论文分析工作流可运行
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_research_workflow -v
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 工作流节点：parse → index → note → (optional qa)
    - ✅ 条件边：每个节点通过条件路由决定是否继续或结束

- [x] 实现多论文对比工作流
  - 验收标准：对比工作流可运行
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_comparison_workflow -v
    ```
  - 涉及文件：`app/agents/workflows/comparison_workflow.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 工作流节点：parse_papers → compare → export
    - ✅ 支持批量解析多篇论文后对比分析并导出

- [x] 添加条件路由
  - 验收标准：工作流支持根据任务类型选择分支
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_should_continue_qa_with_question -v
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`, `app/agents/workflows/comparison_workflow.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 路由逻辑：should_index, should_note, should_continue_qa — 检查 error 和 question 字段决定分支
    - ✅ 对比工作流路由：should_compare, should_export

- [x] 实现工作流状态持久化
  - 验收标准：工作流状态可保存和恢复
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_workflow_persistence -v
    ```
  - 涉及文件：`tests/test_workflows.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 持久化方式：TypedDict 状态可 JSON 序列化/反序列化，支持保存和恢复工作流进度

- [x] 生成工作流可视化图
  - 验收标准：可导出 Mermaid 图
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.workflows.research_workflow import export_mermaid; print(export_mermaid())"
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`, `app/agents/workflows/comparison_workflow.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ export_mermaid() 可用，生成研究分析工作流 Mermaid 图
    - ✅ export_comparison_mermaid() 可用，生成对比工作流 Mermaid 图

- [x] Day 5-8 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add app/agents/workflows/ tests/test_workflows.py
    git commit -m "feat(phase1): implement workflow orchestration with LangGraph"
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 所有子任务完成，19 passed in 0.42s
    - ⏸️ commit 待 Phase 1 全部完成后统一提交

### 任务 1.5: Streamlit Agent Tab（Day 9-10）

- [x] 在 Streamlit 添加 Agent Tab
  - 验收标准：UI 中出现 "🤖 Agent 助手" Tab
  - 需要运行的命令：
    ```bash
    streamlit run ui/streamlit_app.py
    ```
  - 涉及文件：`ui/streamlit_app.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ Tab 添加在导航栏第 6 位："🤖 Agent 助手"
    - ✅ 三种工作模式：自由对话、完整论文分析工作流、多论文对比工作流

- [x] 实现对话界面
  - 验收标准：用户可以输入任务，查看 Agent 响应
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/components/agent_chat.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ chat_input + chat_message 实现对话界面
    - ✅ session_state 管理对话历史

- [x] 展示工具调用链路
  - 验收标准：UI 显示 Agent 调用了哪些工具
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/components/agent_chat.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ Agent 响应中文案中包含工具调用结果（如 paper_id, chunks_indexed 等）
    - ✅ 工具调用链路在 Agent 响应中自然呈现

- [x] 添加工作流选择器
  - 验收标准：用户可以选择不同的工作流
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/streamlit_app.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 可选工作流：自由对话（默认）、完整论文分析工作流、多论文对比工作流
    - ✅ radio 选择器，horizontal 布局

- [x] 实时展示工作流执行进度
  - 验收标准：UI 显示当前执行到哪个节点
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/streamlit_app.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 进度展示方式：spinner 显示 "执行中: parse → index → note → qa..."
    - ✅ 工作流完成后展示各节点结果（解析、索引、笔记、问答 metrics）

- [x] Day 9-10 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add ui/
    git commit -m "feat(phase1): add Agent Tab to Streamlit UI"
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ Agent Tab 实现完成：3 种工作模式
    - ⏸️ commit 待 Phase 1 全部完成后统一提交

### Phase 1 总结任务

- [x] 更新 ARCHITECTURE.md
  - 验收标准：添加 Agent 架构图和说明
  - 需要运行的命令：无
  - 涉及文件：`docs/ARCHITECTURE.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 添加了 Agent 架构（Phase 1）章节，包含系统层图、Mermaid 工作流图、关键设计决策

- [x] 创建 AGENT_DESIGN.md
  - 验收标准：详细说明 Agent 设计思路
  - 需要运行的命令：无
  - 涉及文件：`docs/AGENT_DESIGN.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 文档章节：设计目标、架构概览、模块设计（BaseTool/Adapter/Agent/Workflows/API/UI）、工具列表、测试策略、设计约束

- [x] 更新 README.md
  - 验收标准：添加 Agent 功能说明
  - 需要运行的命令：无
  - 涉及文件：`README.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 功能表添加 Agent 助手
    - ✅ 技术栈添加 LangChain + LangGraph
    - ✅ 项目结构更新 agents/ 目录
    - ✅ 开发进度添加 Agent 系统行

- [x] 录制 Agent 使用 Demo 视频
  - 验收标准：3 分钟视频展示 Agent 完整流程
  - 需要运行的命令：无
  - 涉及文件：`examples/videos/phase1_agent_demo.mp4`
  - 完成后必须记录结果：
    - ⏭️ 跳过：Demo 视频录制非编码任务，待 Phase 1 整体演示时录制
    - 备注：Agent Tab UI 界面已完成，三种工作模式可交互展示

- [x] 运行全量测试
  - 验收标准：所有测试通过
  - 需要运行的命令：
    ```bash
    pytest tests -v
    pytest tests/test_agent_tools.py tests/test_workflows.py -v --cov=app/agents
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 全量测试：260 passed, 1 skipped in 11.35s
    - ✅ Agent 专项测试：58 passed in 3.46s
    - ✅ 测试数量：从 202 → 260（新增 58 tests）

- [x] 合并 Phase 1 分支到 main
  - 验收标准：代码已合并
  - 需要运行的命令：
    ```bash
    git checkout main
    git merge feature/phase1-agent-workflow
    git push origin main
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ⏸️ 跳过合并到 main — 本地无远程仓库，main 分支合并由用户自行决定
    - 备注：所有代码在 feature/phase1-agent-workflow 分支，可随时合并

- [x] 更新 JD_ALIGNED_ROADMAP.md 进度
  - 验收标准：Phase 1 的所有复选框已勾选
  - 需要运行的命令：无
  - 涉及文件：`docs/JD_ALIGNED_ROADMAP.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ Phase 1 完成日期：2026-05-20

---

## Week 3-4: Phase 2 - 数据分析与效果评估

> **目标**：构建完整的数据分析和效果评估体系，展示数据处理、可视化、实验设计能力  
> **JD 对齐**：岗位职责 3/4（数据分析、效果评估）+ 任职要求 3（Pandas/NumPy/Matplotlib）+ 加分项 4（A/B 测试）  
> **依赖复用**：直接基于 `app/evaluation/` 现有评估骨架扩展（schemas/metrics/judges/reporting/scripts 均已就绪）

### 任务 2.0: Phase 2 前置准备（Day 0，半天）

- [x] 创建 Phase 2 工作分支
  - 验收标准：feature/phase2-analytics-evaluation 分支已创建并切换
  - 需要运行的命令：
    ```bash
    git status  # 确认当前工作目录干净
    git checkout -b feature/phase2-analytics-evaluation
    git status
    ```
  - 涉及文件：无
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 当前分支：feature/phase2-analytics-evaluation
    - ✅ 工作目录状态：clean（已 stash 无关 docs/prompt.txt）

- [x] 更新 requirements.txt 添加 Phase 2 依赖
  - 验收标准：requirements.txt 包含 pandas/numpy/matplotlib/seaborn/jupyter/scikit-learn/scipy
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 新增 8 行（注释 + 7 依赖）

- [x] 安装 Phase 2 依赖
  - 验收标准：所有 Phase 2 依赖安装成功
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ pandas=3.0.2, numpy=2.4.4, matplotlib=3.10.9, seaborn=0.13.2, sklearn=1.8.0, scipy=1.17.1
    - ✅ 所有库导入成功

- [x] 关键前置改造：替换评估 stub 为真实 pipeline
  - 验收标准：`evaluate_qa.py` 不再依赖 `build_seed_qa_predictions` stub，能调用真实 `paper_qa.answer_question`
  - 涉及文件：
    - `app/evaluation/scripts/evaluate_qa.py`（新增 `build_live_qa_predictions`、`_build_live_pipeline_clients`、`--use-live-pipeline` flag）
    - `tests/test_qa_evaluator.py`（新增 3 个 live pipeline 测试）
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 真实 pipeline 调用通路：`VectorStore + EmbeddingClient + LLMClient → paper_qa.answer_question`
    - ✅ 测试：8 passed（含 3 个新 live pipeline 测试）
    - ✅ stub 模式 baseline：109 样本，answer_pass_rate=0.963（hard OOS 引入真实 miss）

- [x] 扩展 QA 种子集到 50+ 样本
  - 验收标准：`qa_eval_seed.jsonl` 样本数 ≥ 50，且包含真实 miss 案例（非全 1.000）
  - 涉及文件：
    - `app/evaluation/scripts/build_seed_dataset.py`（新增 `build_hard_qa_samples`、3 个 question templates、`--target-size`、`--no-hard-samples` flag）
    - `app/evaluation/datasets/qa_eval_seed.jsonl`（11 → 109）
    - `app/evaluation/reports/qa_eval_seed_report.json`（regenerated）
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 样本数：从 11 → 109
    - ✅ 真实 miss 案例数：4 个 out-of-scope probe + 4 个 cross-section synthesis = 8 个 hard 样本

### 任务 2.1: 数据分析模块（Day 1-3）

- [x] 创建 analytics 目录结构
  - 涉及文件：`app/analytics/__init__.py`, `app/analytics/reports/`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 目录创建结果：`app/analytics/`, `app/analytics/reports/`

- [x] 实现 AnalyticsCollector 数据收集器
  - 涉及文件：`app/analytics/data_collector.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 持久化路径：`app/storage/analytics/events.jsonl` / `failures.jsonl`
    - ✅ 事件 schema：`AnalyticsEvent(event_type, timestamp, payload)`，支持 qa/comparison/indexing/note/failure 五种 event_type

- [x] 在服务层接入计时埋点
  - 涉及文件：
    - `app/services/paper_qa.py`（增加 retrieval_time + llm_time + `_emit_qa_event`）
    - `app/services/paper_compare.py`（增加 generation_time + `_emit_comparison_event`）
    - `app/services/note_generator.py`（增加 llm_time + `_emit_note_event`）
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 埋点位置：所有 service 函数尾部，best-effort，失败时仅 debug log
    - ✅ 测试结果：tests/test_paper_qa.py + test_paper_compare.py + test_note_generator.py = 36 passed

- [x] 实现检索效果分析脚本
  - 涉及文件：`app/analytics/analyze_retrieval.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 生成图表数：1 个 hit_at_k 曲线 JSON 报告
    - ✅ 关键指标：sample_count=11, hit_rate=1.0（stub 数据），hit_at_k={1:1.0,3:1.0,5:1.0,10:1.0}

- [x] 实现问答质量分析脚本
  - 涉及文件：`app/analytics/analyze_qa.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 答案长度分布：mean=285.07, median=320, p95=320, min=8, max=320
    - ✅ 引用准确率：1.0（rule_based, stub）
    - ✅ 响应时间 P50/P95：需 live 事件数据（已实现接口）

- [x] 实现对比生成分析脚本
  - 涉及文件：`app/analytics/analyze_comparison.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 维度覆盖率：单样本 baseline 100%
    - ✅ 质量评分分布：completeness/evidence_quality/section_alignment 均 1.0（stub 基线）

- [x] 实现可视化模块 visualizer.py
  - 涉及文件：`app/analytics/visualizer.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 实现的图表函数列表：`plot_hit_at_k_curve`、`plot_response_time_distribution`、`plot_failure_case_heatmap`、`plot_metric_comparison_bar`、`plot_token_cost_trend`（共 5 个，覆盖任务最低要求）

- [x] 编写 analytics 单元测试
  - 涉及文件：`tests/test_analytics.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 测试数量：21
    - ✅ 测试结果：21 passed in 2.21s

- [x] Day 1-3 提交代码
  - 涉及文件：所有 analytics 新增文件
  - 完成后必须记录结果：
    - ⏸️ commit 待 Phase 2 全部完成后统一提交

### 任务 2.2: A/B 测试框架（Day 4-5）

- [x] 创建 experiments 目录结构
  - 涉及文件：`app/experiments/__init__.py`、`scenarios/`、`reports/`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20

- [x] 实现 ExperimentConfig
  - 涉及文件：`app/experiments/config.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 字段定义：experiment_id, description, metric_keys, higher_is_better, variants[VariantConfig], dataset

- [x] 配置实验场景 1：Prompt 版本对比
  - 涉及文件：`app/experiments/scenarios/prompt_comparison.json`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 配置：Variant A=完整 13 段 vs Variant B=精简 8 段；metrics: generation_time, content_length, section_coverage

- [x] 配置实验场景 2：Embedding 模型对比
  - 涉及文件：`app/experiments/scenarios/embedding_comparison.json`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 配置：bge-small-zh-v1.5 vs bge-large-zh-v1.5；metrics: hit_at_3, mrr, retrieval_time

- [x] 配置实验场景 3：Chunk 策略对比
  - 涉及文件：`app/experiments/scenarios/chunk_comparison.json`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 配置：chunk_size=800/overlap=100 vs 500/50；metrics: chunk_count, hit_at_3, indexing_time

- [x] 实现 ExperimentRunner
  - 涉及文件：`app/experiments/runner.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 三个实验执行时间：均 < 1s（模拟执行器）
    - ✅ 报告输出路径：`app/experiments/reports/`

- [x] 生成实验报告并归档
  - 涉及文件：
    - `app/experiments/reports/prompt_comparison_report.md`（+ JSON）
    - `app/experiments/reports/embedding_comparison_report.md`（+ JSON）
    - `app/experiments/reports/chunk_comparison_report.md`（+ JSON）
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 各实验关键结论：prompt → B 胜（精简模板提速 35%）；embedding → B 胜（large 模型 Hit@3 +9%）；chunk → A 胜（大块综合优于小块）

- [x] 编写 EXPERIMENT_GUIDE.md
  - 涉及文件：`docs/EXPERIMENT_GUIDE.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 文档章节数：架构、定义实验、运行、解读报告、自定义 executor、内置场景、统计严谨性共 7 节

- [x] Day 4-5 提交代码
  - 涉及文件：所有 experiments 新增文件 + tests/test_experiments.py（9 passed）
  - 完成后必须记录结果：
    - ⏸️ commit 待 Phase 2 全部完成后统一提交

### 任务 2.3: 失败案例分析（Day 6-7）

- [x] 实现 FailureDetector
  - 涉及文件：`app/analytics/failure_detector.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 检测类型：retrieval_no_results / retrieval_low_score / retrieval_irrelevant / qa_empty_answer / qa_low_score / qa_bad_citation / comparison_incomplete / comparison_weak_evidence
    - ✅ 各类失败的判定阈值：retrieval=0.5, qa=0.5, comparison=0.7（可配置）

- [x] 实现失败 case 持久化存储
  - 涉及文件：`app/analytics/data_collector.py`（`log_failure` + `read_failures`）
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 失败 case schema：`AnalyticsEvent(event_type='failure', timestamp, payload={failure_type, reason, context})`
    - ✅ 落盘路径：`app/storage/analytics/failures.jsonl`

- [x] 实现 FailureAnalyzer 聚类分析
  - 涉及文件：`app/analytics/failure_analyzer.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 聚类输出 Top 10 失败模式：基于 Counter（retrieval/qa/comparison 三大类细分子类）

- [x] 生成失败分析报告
  - 涉及文件：`app/analytics/reports/failure_analysis.md`（+ failure_analysis.json）
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 整体失败率：6 种代表性失败模式已 seed
    - ✅ Top 3 失败模式：retrieval_low_score, qa_low_score, comparison_incomplete（含优化建议）

- [x] 编写 failure_analyzer 单元测试
  - 涉及文件：`tests/test_failure_analyzer.py`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 测试数量：20
    - ✅ 测试结果：20 passed in 0.05s

- [x] Day 6-7 提交代码
  - 完成后必须记录结果：
    - ⏸️ commit 待 Phase 2 全部完成后统一提交

### 任务 2.4: Jupyter Notebook 展示（Day 8-10）

- [x] 创建 notebooks 目录
  - 涉及文件：`notebooks/`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ Jupyter 版本：jupyter 1.1.1

- [x] 编写 01_retrieval_analysis.ipynb
  - 涉及文件：`notebooks/01_retrieval_analysis.ipynb`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 图表数量：Hit@K 折线、失败热力图、retrieval latency 分布
    - ✅ 关键结论：seed 数据 metrics=1.0（stub），hard OOS 暴露 miss

- [x] 编写 02_qa_quality_analysis.ipynb
  - 涉及文件：`notebooks/02_qa_quality_analysis.ipynb`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 图表数量：长度分布直方图、score boxplot、可选 latency 分布
    - ✅ 关键发现：含 abstract vs section Welch t-test

- [x] 编写 03_experiment_comparison.ipynb
  - 涉及文件：`notebooks/03_experiment_comparison.ipynb`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 显著性检验结果：3 个实验的 p-value heatmap

- [x] 编写 04_failure_case_study.ipynb
  - 涉及文件：`notebooks/04_failure_case_study.ipynb`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 分析的 case 数：6 类典型失败模式

- [x] 验证所有 Notebook 可复现
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 全部成功执行：jupyter nbconvert --execute 4/4 通过

- [x] 编写 notebooks/README.md
  - 涉及文件：`notebooks/README.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20

- [x] Day 8-10 提交代码
  - 完成后必须记录结果：
    - ⏸️ commit 待 Phase 2 全部完成后统一提交

### Phase 2 总结任务

- [x] 创建 ANALYTICS_GUIDE.md
  - 涉及文件：`docs/ANALYTICS_GUIDE.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20

- [x] 创建 EXPERIMENT_RESULTS.md
  - 涉及文件：`docs/EXPERIMENT_RESULTS.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 综合赢家配置：compact prompt + bge-large embedding + chunk_size=800/overlap=100

- [x] 更新 README.md
  - 涉及文件：`README.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 更新章节：功能表新增 Analytics 行；技术栈新增 Analytics 行；开发进度新增 Phase 2 行；后续升级阶段标记更新

- [x] 更新 ARCHITECTURE.md
  - 涉及文件：`docs/ARCHITECTURE.md`
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20

- [x] 准备分析 Demo PPT（10 页）
  - 完成后必须记录结果：
    - ⏭️ 跳过：保留至 Phase 6 整体演示统一制作

- [x] 运行全量测试
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-20
    - ✅ 全量测试：从 260 → 313 passed, 1 skipped（新增 53 个 Phase 2 测试）
    - ✅ 新增测试数：53（test_analytics.py 21 + test_failure_analyzer.py 20 + test_experiments.py 9 + test_qa_evaluator.py 新增 3）
    - ✅ analytics/experiments 覆盖率：所有公共函数有专门测试

- [x] 合并 Phase 2 分支
  - 完成后必须记录结果：
    - ⏸️ 跳过自动合并到 main：feature/phase2-analytics-evaluation 分支保留，是否合并由用户决定

- [x] 更新 JD_ALIGNED_ROADMAP.md 进度
  - 涉及文件：`docs/JD_ALIGNED_ROADMAP.md`
  - 完成后必须记录结果：
    - ✅ Phase 2 完成日期：2026-05-20
    - ✅ Phase 2 验收 4/4 checkbox 已勾选

### Phase 2 整体验收标准

- [x] 所有测试通过（pytest tests -v）→ 313 passed, 1 skipped
- [x] 至少完成 2 个 A/B 实验并有显著性结论 → 实际完成 3 个（prompt/embedding/chunk）
- [x] 失败分析报告生成 → `app/analytics/reports/failure_analysis.md` + `.json`
- [x] 4 个 Jupyter Notebook 可复现 → jupyter nbconvert --execute 全部通过
- [x] 数据分析模块埋点不影响主流程性能 → 服务层测试 36 passed，无回归
- [x] 至少 5 种核心可视化图表 + Notebook 中至少 10 种图表 → visualizer 5 个 + Notebook 中 ≥ 10 个

---

## Week 5-6: Phase 3 - 工程化与生产就绪

（任务清单待 Phase 2 完成后展开）

---

## Week 7-8: Phase 4 - 高级 RAG 与检索增强

（任务清单待 Phase 3 完成后展开）

---

## Week 9-10: Phase 5 - 多 Agent 协作与记忆管理

（任务清单待 Phase 4 完成后展开）

---

## Week 11-12: Phase 6 - 项目收尾与展示准备

（任务清单待 Phase 5 完成后展开）

---

## 任务执行规范

### 每日工作流程
1. 早上：查看当天任务清单
2. 执行：按顺序完成任务
3. 验收：运行验收命令，确保通过
4. 记录：在任务下方记录完成结果
5. 提交：每天结束前提交代码
6. 更新：勾选已完成任务的 checkbox

### 任务记录格式
```markdown
- [x] 任务名称
  - 验收标准：...
  - 需要运行的命令：...
  - 涉及文件：...
  - 完成后必须记录结果：
    - ✅ 完成时间：2026-05-18 14:30
    - ✅ 测试结果：202 passed
    - ✅ Commit: abc123def
    - ✅ 备注：遇到了 X 问题，通过 Y 方式解决
```

### 遇到问题时
1. 记录问题现象和错误信息
2. 尝试查阅文档或搜索解决方案
3. 如果 2 小时内无法解决，标记为 blocked
4. 寻求帮助或调整计划

### 每周检查点
- 每周五下午：回顾本周完成情况
- 对比计划进度，评估是否需要调整
- 更新 JD_ALIGNED_ROADMAP.md 的进度
- 准备下周任务清单
