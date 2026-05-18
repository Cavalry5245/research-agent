# 当前任务清单

> 基于 JD_ALIGNED_ROADMAP.md 的执行任务  
> 最后更新：2026-05-18  
> 当前阶段：Week 0 准备阶段

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

- [ ] 学习 LangChain 基础（可选但推荐）
  - 验收标准：理解 Tool、Agent、Chain 的基本概念
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：
    - 阅读了哪些文档
    - 运行了哪些示例
    - 理解的核心概念

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

- [ ] 创建 Phase 1 分支
  - 验收标准：feature/phase1-agent-workflow 分支已创建并切换
  - 需要运行的命令：
    ```bash
    git checkout -b feature/phase1-agent-workflow
    git status
    ```
  - 涉及文件：无
  - 完成后必须记录结果：当前分支名称

- [ ] 推送到远程
  - 验收标准：分支已推送到远程仓库
  - 需要运行的命令：
    ```bash
    git push -u origin feature/phase1-agent-workflow
    ```
  - 涉及文件：无
  - 完成后必须记录结果：推送成功确认

---

## Week 1-2: Phase 1 - Agent 工作流基础

### 任务 1.1: 工具封装层（Day 1）

- [ ] 创建 Agent 工具目录结构
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
  - 完成后必须记录结果：目录结构已创建

- [ ] 实现工具基类 BaseTool
  - 验收标准：BaseTool 类实现完成，包含 name、description、parameters、execute 方法
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.tools.base import BaseTool; print('BaseTool imported successfully')"
    ```
  - 涉及文件：`app/agents/tools/base.py`
  - 完成后必须记录结果：基类实现的核心方法

- [ ] 封装 6 个工具类
  - 验收标准：6 个工具类实现完成（UploadPaperTool、GenerateNoteTool、IndexPaperTool、QATool、ComparePapersTool、ExportMarkdownTool）
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.tools.paper_tools import UploadPaperTool, GenerateNoteTool, IndexPaperTool, QATool, ComparePapersTool, ExportMarkdownTool; print('All tools imported successfully')"
    ```
  - 涉及文件：`app/agents/tools/paper_tools.py`
  - 完成后必须记录结果：每个工具的 name 和 description

- [ ] 实现工具注册中心 ToolRegistry
  - 验收标准：ToolRegistry 实现完成，可以注册和获取工具
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.tools.registry import ToolRegistry; registry = ToolRegistry(); print(f'Registry has {len(registry.list_tools())} tools')"
    ```
  - 涉及文件：`app/agents/tools/registry.py`
  - 完成后必须记录结果：注册中心的核心方法

- [ ] 编写工具单元测试
  - 验收标准：每个工具有独立单元测试
  - 需要运行的命令：
    ```bash
    pytest tests/test_agent_tools.py -v
    ```
  - 涉及文件：`tests/test_agent_tools.py`
  - 完成后必须记录结果：测试通过数量、覆盖率

- [ ] Day 1 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add app/agents/tools/ tests/test_agent_tools.py
    git commit -m "feat(phase1): implement agent tool wrapper layer"
    ```
  - 涉及文件：所有新增文件
  - 完成后必须记录结果：commit hash

### 任务 1.2: LangChain 深度学习（Day 2）

- [ ] 学习 LangChain Tool 概念
  - 验收标准：理解 Tool 的定义和使用方式
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：学习笔记、运行的示例代码

- [ ] 学习 LangChain Agent 概念
  - 验收标准：理解 Agent 的工作原理和类型
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：学习笔记、Agent 类型对比

- [ ] 学习 LangChain Chain 概念
  - 验收标准：理解 Chain 的组合方式
  - 需要运行的命令：无
  - 涉及文件：无
  - 完成后必须记录结果：学习笔记、Chain 示例

- [ ] 运行 LangChain 官方示例
  - 验收标准：至少运行 3 个官方示例
  - 需要运行的命令：根据官方文档
  - 涉及文件：无
  - 完成后必须记录结果：运行的示例列表、遇到的问题

### 任务 1.3: LangChain 集成（Day 3-4）

- [ ] 实现 LangChain Tool 适配器
  - 验收标准：BaseTool 可以转换为 LangChain Tool
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.langchain_adapter import convert_to_langchain_tool; print('Adapter imported successfully')"
    pytest tests/test_langchain_adapter.py -v
    ```
  - 涉及文件：
    - `app/agents/langchain_adapter.py`
    - `tests/test_langchain_adapter.py`
  - 完成后必须记录结果：适配器实现的核心逻辑

- [ ] 创建 PaperResearchAgent
  - 验收标准：Agent 可以调用工具
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.paper_research_agent import PaperResearchAgent; agent = PaperResearchAgent(); print('Agent created successfully')"
    pytest tests/test_paper_research_agent.py -v
    ```
  - 涉及文件：
    - `app.agents/paper_research_agent.py`
    - `tests/test_paper_research_agent.py`
  - 完成后必须记录结果：Agent 配置的工具列表

- [ ] 实现对话历史管理
  - 验收标准：Agent 支持多轮对话
  - 需要运行的命令：
    ```bash
    pytest tests/test_paper_research_agent.py::test_multi_turn_conversation -v
    ```
  - 涉及文件：`app/agents/paper_research_agent.py`
  - 完成后必须记录结果：对话历史的存储方式

- [ ] 添加 Agent 执行接口
  - 验收标准：POST /agent/execute 接口可用
  - 需要运行的命令：
    ```bash
    # 启动服务
    uvicorn app.main:app --reload &
    # 测试接口
    curl -X POST http://localhost:8000/agent/execute -H "Content-Type: application/json" -d '{"task":"帮我分析 paper_001"}'
    ```
  - 涉及文件：`app/main.py`
  - 完成后必须记录结果：接口响应示例

- [ ] Day 3-4 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add app/agents/ app/main.py tests/
    git commit -m "feat(phase1): integrate LangChain and implement PaperResearchAgent"
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：commit hash

### 任务 1.4: 工作流编排（Day 5-8）

- [ ] 安装和学习 LangGraph
  - 验收标准：理解 StateGraph 和工作流编排概念
  - 需要运行的命令：
    ```bash
    python -c "from langgraph.graph import StateGraph; print('LangGraph imported successfully')"
    ```
  - 涉及文件：无
  - 完成后必须记录结果：学习笔记、LangGraph 核心概念

- [ ] 定义工作流状态
  - 验收标准：ResearchWorkflowState 定义完成
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.workflows.research_workflow import ResearchWorkflowState; print('State defined successfully')"
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`
  - 完成后必须记录结果：状态字段列表

- [ ] 实现工作流节点
  - 验收标准：parse_node、index_node、note_node、qa_node 实现完成
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_workflow_nodes -v
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`
  - 完成后必须记录结果：每个节点的功能说明

- [ ] 使用 StateGraph 编排工作流
  - 验收标准：完整论文分析工作流可运行
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_research_workflow -v
    ```
  - 涉及文件：`app/agents/workflows/research_workflow.py`
  - 完成后必须记录结果：工作流的节点和边

- [ ] 实现多论文对比工作流
  - 验收标准：对比工作流可运行
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_comparison_workflow -v
    ```
  - 涉及文件：`app/agents/workflows/comparison_workflow.py`
  - 完成后必须记录结果：工作流的节点和边

- [ ] 添加条件路由
  - 验收标准：工作流支持根据任务类型选择分支
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_conditional_routing -v
    ```
  - 涉及文件：`app/agents/workflows/`
  - 完成后必须记录结果：路由逻辑说明

- [ ] 实现工作流状态持久化
  - 验收标准：工作流状态可保存和恢复
  - 需要运行的命令：
    ```bash
    pytest tests/test_workflows.py::test_workflow_persistence -v
    ```
  - 涉及文件：`app/agents/workflows/`
  - 完成后必须记录结果：持久化方式

- [ ] 生成工作流可视化图
  - 验收标准：可导出 Mermaid 图
  - 需要运行的命令：
    ```bash
    python -c "from app.agents.workflows.research_workflow import export_mermaid; print(export_mermaid())"
    ```
  - 涉及文件：`app/agents/workflows/`
  - 完成后必须记录结果：Mermaid 图示例

- [ ] Day 5-8 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add app/agents/workflows/ tests/test_workflows.py
    git commit -m "feat(phase1): implement workflow orchestration with LangGraph"
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：commit hash

### 任务 1.5: Streamlit Agent Tab（Day 9-10）

- [ ] 在 Streamlit 添加 Agent Tab
  - 验收标准：UI 中出现 "🤖 Agent 助手" Tab
  - 需要运行的命令：
    ```bash
    streamlit run ui/streamlit_app.py
    ```
  - 涉及文件：`ui/streamlit_app.py`
  - 完成后必须记录结果：Tab 位置和布局

- [ ] 实现对话界面
  - 验收标准：用户可以输入任务，查看 Agent 响应
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/streamlit_app.py`
  - 完成后必须记录结果：界面截图

- [ ] 展示工具调用链路
  - 验收标准：UI 显示 Agent 调用了哪些工具
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/components/agent_chat.py`
  - 完成后必须记录结果：工具调用展示方式

- [ ] 添加工作流选择器
  - 验收标准：用户可以选择不同的工作流
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/streamlit_app.py`
  - 完成后必须记录结果：可选工作流列表

- [ ] 实时展示工作流执行进度
  - 验收标准：UI 显示当前执行到哪个节点
  - 需要运行的命令：手动测试 UI
  - 涉及文件：`ui/components/agent_chat.py`
  - 完成后必须记录结果：进度展示方式

- [ ] Day 9-10 提交代码
  - 验收标准：代码已提交
  - 需要运行的命令：
    ```bash
    git add ui/
    git commit -m "feat(phase1): add Agent Tab to Streamlit UI"
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：commit hash

### Phase 1 总结任务

- [ ] 更新 ARCHITECTURE.md
  - 验收标准：添加 Agent 架构图和说明
  - 需要运行的命令：无
  - 涉及文件：`docs/ARCHITECTURE.md`
  - 完成后必须记录结果：更新的章节

- [ ] 创建 AGENT_DESIGN.md
  - 验收标准：详细说明 Agent 设计思路
  - 需要运行的命令：无
  - 涉及文件：`docs/AGENT_DESIGN.md`
  - 完成后必须记录结果：文档章节结构

- [ ] 更新 README.md
  - 验收标准：添加 Agent 功能说明
  - 需要运行的命令：无
  - 涉及文件：`README.md`
  - 完成后必须记录结果：更新的章节

- [ ] 录制 Agent 使用 Demo 视频
  - 验收标准：3 分钟视频展示 Agent 完整流程
  - 需要运行的命令：无
  - 涉及文件：`examples/videos/phase1_agent_demo.mp4`
  - 完成后必须记录结果：视频时长、展示的功能

- [ ] 运行全量测试
  - 验收标准：所有测试通过
  - 需要运行的命令：
    ```bash
    pytest tests -v
    pytest tests/test_agent_tools.py tests/test_workflows.py -v --cov=app/agents
    ```
  - 涉及文件：无
  - 完成后必须记录结果：测试通过数量、覆盖率

- [ ] 合并 Phase 1 分支到 main
  - 验收标准：代码已合并
  - 需要运行的命令：
    ```bash
    git checkout main
    git merge feature/phase1-agent-workflow
    git push origin main
    ```
  - 涉及文件：无
  - 完成后必须记录结果：merge commit hash

- [ ] 更新 JD_ALIGNED_ROADMAP.md 进度
  - 验收标准：Phase 1 的所有复选框已勾选
  - 需要运行的命令：无
  - 涉及文件：`docs/JD_ALIGNED_ROADMAP.md`
  - 完成后必须记录结果：Phase 1 完成日期

---

## Week 3-4: Phase 2 - 数据分析与效果评估

（任务清单待 Phase 1 完成后展开）

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
