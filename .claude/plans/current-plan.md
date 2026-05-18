# 执行计划：审查和优化 JD_ALIGNED_ROADMAP.md

## Context（背景）

用户创建了一份详细的 12 周项目升级路线图 `docs/JD_ALIGNED_ROADMAP.md`（1820 行），目标是将 ResearchAgent 项目打造成符合「大语言模型与 Agent 应用开发实习生」岗位要求的完整案例。

**问题背景**：
1. 项目中存在多个执行计划文档，可能产生冲突
2. 新路线图非常宏大（12 周 6 个 Phase），需要评估可行性
3. 用户要求审查这份计划，确保其完整性、可执行性和合理性

**当前项目状态**：
- 已完成 MVP：PDF 解析、笔记生成、RAG 问答、多论文对比
- 测试基线：202 passed, 1 skipped
- 现有执行计划：HERMES_EXECUTION_PLAN.md（聚焦评估体系和 RAG 深化）
- 新路线图：JD_ALIGNED_ROADMAP.md（聚焦 Agent 系统和工程化）

**项目环境**：
- 项目根目录：`/home/chase/projects/ResearchAgent`
- Conda 环境：`research_agent`（Python 3.11）
- 运行环境：WSL (Linux 5.15.167.4-microsoft-standard-WSL2)
- 激活环境：`conda activate research_agent`
- 所有命令默认在项目根目录下、已激活 conda 环境中执行

**核心矛盾**：
- 现有计划（HERMES_EXECUTION_PLAN.md）：务实、小步迭代、已有进展（7/20 轮）
- 新路线图（JD_ALIGNED_ROADMAP.md）：宏大、技术栈激进、与当前进展不一致

## 目标边界

### 要完成什么
1. **审查新路线图的质量**：评估其完整性、可执行性、时间安排合理性
2. **识别计划冲突**：分析新旧计划的冲突点，提出处理建议
3. **优化路线图**：针对发现的问题提出具体改进建议
4. **制定决策方案**：帮助用户决定如何处理多个计划文档

### 不做什么
1. ❌ 不立即执行路线图中的任何任务
2. ❌ 不修改现有代码或配置
3. ❌ 不删除或归档任何文档
4. ❌ 不做技术选型的最终决策（由用户决定）

## 涉及文件清单

### 需要深度分析的文件
1. `/home/chase/projects/ResearchAgent/docs/JD_ALIGNED_ROADMAP.md` - 新路线图（主要审查对象）
2. `/home/chase/projects/ResearchAgent/docs/JD.md` - 岗位 JD（对齐基准）
3. `/home/chase/projects/ResearchAgent/docs/HERMES_EXECUTION_PLAN.md` - 现有执行计划
4. `/home/chase/projects/ResearchAgent/docs/NEXT_PHASE_RECOMMENDATIONS.md` - 当前阶段建议
5. `/home/chase/projects/ResearchAgent/docs/EXECUTION_STATUS.md` - 执行状态日志

### 需要参考的文件
6. `/home/chase/projects/ResearchAgent/docs/ARCHITECTURE.md` - 系统架构
7. `/home/chase/projects/ResearchAgent/docs/MVP_REQUIREMENTS.md` - MVP 需求
8. `/home/chase/projects/ResearchAgent/requirements.txt` - 当前依赖
9. `/home/chase/projects/ResearchAgent/README.md` - 项目说明

### 可能需要创建的文件
10. `/home/chase/projects/ResearchAgent/docs/ROADMAP_REVIEW.md` - 路线图审查报告（可选）
11. `/home/chase/projects/ResearchAgent/docs/EXECUTION_DECISION.md` - 执行决策文档（可选）

## 分阶段任务列表

### Phase 1: 深度分析（已完成 ✅）
通过 3 个并行 Explore agents 完成：

**任务 1.1**: 检查计划冲突 ✅
- 识别现有执行计划文档
- 分析新旧计划的冲突点
- 评估未完成任务

**任务 1.2**: 探索项目当前状态 ✅
- 项目结构和已实现功能
- 测试状态和文档现状
- 当前技术栈和依赖

**任务 1.3**: 分析路线图质量 ✅
- 检查 JD 覆盖度
- 评估任务可执行性
- 识别潜在问题

### Phase 2: 综合评估（当前阶段）

**任务 2.1**: 整合探索结果
- 汇总 3 个 agents 的发现
- 识别关键问题和风险
- 提炼核心建议

**任务 2.2**: 制定优化方案
- 针对时间压力问题：调整 Phase 优先级
- 针对技术风险：准备降级方案
- 针对计划冲突：提出处理建议

**任务 2.3**: 准备决策选项
- 方案 A：保留现有计划，归档新路线图
- 方案 B：融合两个计划，分阶段采纳
- 方案 C：切换到新路线图（不推荐）

### Phase 3: 用户确认

**任务 3.1**: 询问用户意图
- 是否要立即切换到新路线图？
- 是否要保留现有执行进展？
- 优先级如何排序（Agent vs 评估体系 vs 工程化）？

**任务 3.2**: 根据用户反馈调整计划

### Phase 4: 输出最终建议

**任务 4.1**: 编写执行计划
- 明确下一步行动
- 提供具体的文档更新建议
- 给出风险控制措施

## 每个任务的验收标准

### Phase 1 验收标准 ✅
- [x] 3 个 Explore agents 成功完成
- [x] 识别出所有计划文档及其关系
- [x] 分析出新路线图的优点和问题
- [x] 了解项目当前状态和技术栈

### Phase 2 验收标准
- [ ] 整合报告清晰列出关键发现
- [ ] 优化方案具体可操作
- [ ] 决策选项有明确的利弊分析

### Phase 3 验收标准
- [ ] 用户明确表达了意图和优先级
- [ ] 确认了下一步执行方向

### Phase 4 验收标准
- [ ] 执行计划文件完整
- [ ] 包含明确的行动步骤
- [ ] 风险和应对措施清晰

## 需要运行的测试/评估命令

本次任务为计划审查，不涉及代码修改，因此**无需运行测试**。

如果后续执行路线图中的任务，需要运行：
```bash
# 基线测试
python -m pytest tests -q

# 特定模块测试（根据修改内容）
python -m pytest tests/test_agent_tools.py -v
python -m pytest tests/test_workflows.py -v
```

## 风险点和回滚方案

### 风险 1: 计划冲突导致执行混乱
**影响**: 不清楚应该执行哪个计划，浪费时间

**应对措施**:
- 明确标注每个计划文档的状态（主执行计划 / 长期参考 / 已归档）
- 在文档顶部添加醒目的状态标签
- 只保留一个"当前主执行计划"

**回滚方案**:
- 如果新路线图执行失败，可以回退到 HERMES_EXECUTION_PLAN.md
- 保留所有历史文档，不做删除

### 风险 2: 新路线图过于激进，无法完成
**影响**: 12 周内无法完成所有 6 个 Phase

**应对措施**:
- 识别核心 Phase（Phase 1, 2, 4, 6）和可选 Phase（Phase 3, 5）
- 准备降级方案（如 Phase 3 只做异步任务，不做数据库）
- 每周检查点严格执行，及时调整

**回滚方案**:
- 如果某个 Phase 严重超时，跳过该 Phase 继续下一个
- 优先保证核心功能（Agent、RAG、文档）

### 风险 3: 技术栈学习成本过高
**影响**: LangChain/LangGraph/Celery 等框架学习耗时

**应对措施**:
- 提前学习（Week 0 预习 LangChain）
- 准备降级方案（自实现简化版 Agent）
- 优先使用熟悉的技术栈

**回滚方案**:
- 如果 LangChain 学习困难，使用 OpenAI Function Calling 替代
- 如果 Celery 配置复杂，使用 FastAPI BackgroundTasks 替代

### 风险 4: 丢失现有执行进展
**影响**: 已完成的 7 轮执行成果被废弃

**应对措施**:
- 不删除 HERMES_EXECUTION_PLAN.md 和 EXECUTION_STATUS.md
- 新路线图应该在现有基础上增量构建
- 保留评估体系相关的已完成工作

**回滚方案**:
- 如果新路线图不适合，完全回退到旧计划
- 所有历史记录都保留，可随时恢复

## 最终交付物

### 1. 执行计划文档（本文件）
- [x] 背景和目标
- [x] 任务分解
- [x] 验收标准
- [x] 风险控制

### 2. 审查报告（口头或文档）
包含以下内容：
- **关键发现**：新旧计划的冲突、路线图的优缺点
- **优化建议**：时间调整、技术选型、优先级排序
- **决策选项**：3 个方案的利弊分析
- **下一步行动**：具体的执行建议

### 3. 用户决策确认
- 用户选择的执行方案
- 明确的优先级排序
- 下一步的具体任务

### 4. 文档更新建议（可选）
如果用户决定采纳新路线图，需要：
- 在 JD_ALIGNED_ROADMAP.md 顶部添加状态标签
- 在 HERMES_EXECUTION_PLAN.md 顶部添加"已暂停"标记
- 更新 README.md 指向新的执行计划

## 核心发现总结（基于 Phase 1 探索）

### 发现 1: 计划冲突严重
- **现有计划**：HERMES_EXECUTION_PLAN.md 聚焦评估体系和 RAG 深化，已执行 7/20 轮
- **新路线图**：JD_ALIGNED_ROADMAP.md 聚焦 Agent 系统和工程化，尚未启动
- **冲突点**：优先级完全不同，技术栈差异大

### 发现 2: 新路线图质量高但过于激进
**优点**：
- 完整覆盖 JD 要求
- 任务具体可执行
- 技术选型合理
- 验收标准明确

**问题**：
- 时间压力大（12 周完成 6 个 Phase）
- 技术栈学习成本高（LangChain/LangGraph/Celery/AutoGen）
- 与当前进展不一致（当前聚焦 compare contract hardening）
- 部分 Phase 任务密集（Phase 3 工程化 10 天完成 4 个系统）

### 发现 3: 项目基线稳定
- 202 个测试通过
- 核心功能完整（PDF → 笔记 → RAG → 对比）
- 评测框架已建立
- 5 篇真实论文数据

### 推荐方案：融合式执行

**核心思路**：保留现有执行计划为主线，选择性吸收新路线图的合理元素

**具体建议**：
1. **继续 HERMES_EXECUTION_PLAN.md**：完成 P0 评估体系和 P1 RAG 深化
2. **从新路线图提取**：
   - Phase 2 的数据分析思路 → 融入评估报告
   - Phase 4 的部分 RAG 技术 → 融入 P1 RAG 深化
   - Phase 6 的文档和展示 → 作为最终收尾阶段
3. **暂缓 Agent 系统**：Phase 1 和 Phase 5 的 Agent 工作流暂不启动，避免架构大改
4. **简化工程化**：Phase 3 只做必要的异步任务和日志，数据库和缓存可选

**时间线**：
- Week 1-2: 完成 P0 评估体系（当前计划）
- Week 3-4: 完成 P1 RAG 深化 + 数据分析可视化（融合）
- Week 5-6: 完成 P2 工程化（简化版）
- Week 7-8: 文档完善和展示准备（新路线图 Phase 6）

## 用户决策确认 ✅

**用户选择**：
1. **执行方向**：完全切换到新路线图（JD_ALIGNED_ROADMAP.md）
2. **核心优先级**：Agent 系统能力（任务拆解、工具调用、工作流编排、多Agent协作）
3. **时间投入**：12周全职（每周4-5天）

**决策影响**：
- ✅ 启动 Phase 1-6 的完整执行
- ✅ 优先保证 Phase 1（Agent基础）和 Phase 5（多Agent协作）的质量
- ✅ 有足够时间学习 LangChain/LangGraph/AutoGen/CrewAI
- ⚠️ 需要暂停 HERMES_EXECUTION_PLAN.md 的执行
- ⚠️ 需要明确处理现有执行进展（7/20轮）

## 基于用户决策的优化建议

### 调整后的 Phase 优先级

根据用户优先看重 **Agent 系统能力**，建议调整执行顺序：

**高优先级（必须完成）**：
1. **Phase 1: Agent 工作流基础**（Week 1-2）- 核心优先级
2. **Phase 5: 多 Agent 协作与记忆管理**（Week 9-10）- 核心优先级
3. **Phase 2: 数据分析与效果评估**（Week 3-4）- 展示数据能力
4. **Phase 6: 项目收尾与展示准备**（Week 11-12）- 面试必需

**中优先级（尽量完成）**：
5. **Phase 4: 高级 RAG 与检索增强**（Week 7-8）- 技术深度

**可简化优先级**：
6. **Phase 3: 工程化与生产就绪**（Week 5-6）- 可简化为异步任务+日志，数据库和缓存可选

### 针对 Agent 优先级的强化建议

既然用户最看重 Agent 系统能力，建议在原路线图基础上强化：

**Phase 1 强化**（Week 1-2）：
- 增加 0.5 天用于 LangChain 深度学习
- 工作流编排从 3 天延长到 4 天（这是难点）
- 增加更多工作流场景（从 3 个增加到 5 个）

**Phase 5 强化**（Week 9-10）：
- 提前在 Week 8 确定多 Agent 框架选型（AutoGen vs CrewAI）
- 增加 Agent 协作场景（从 3 个增加到 5 个）
- 增加 Agent 决策可视化和调试工具

**新增：Phase 1.5 Agent 实战应用**（Week 2.5，可选）：
- 用 Agent 系统重构现有功能（论文分析流程）
- 展示 Agent 相比传统流程的优势
- 积累 Agent 实战经验


## 具体执行计划

### 立即行动（Week 0，准备阶段，1-2天）

#### 任务 0.1: 完成当前未完成工作（2小时）
**目标**：快速完成 compare markdown escaping，为新路线图清理障碍

**步骤**：
1. 完成 `app/services/paper_compare.py` 的表格转义增强
2. 运行测试确保通过：`pytest tests/test_paper_compare.py -v`
3. 提交代码：`git commit -m "fix: enhance markdown table escaping in comparison"`

**验收**：
- [ ] 测试通过
- [ ] 代码已提交

#### 任务 0.2: 归档旧计划文档（30分钟）
**目标**：明确标注文档状态，避免执行混乱

**步骤**：
1. 创建 `docs/archive/` 目录
2. 移动文件：
   ```bash
   mkdir -p docs/archive
   mv docs/HERMES_EXECUTION_PLAN.md docs/archive/
   mv docs/NEXT_PHASE_RECOMMENDATIONS.md docs/archive/
   ```
3. 在归档文件顶部添加标注：
   ```markdown
   > [已归档 - 2026-05-18] 本计划已被 JD_ALIGNED_ROADMAP.md 替代。
   > 保留此文档作为历史记录和参考。
   ```
4. 保留 `docs/EXECUTION_STATUS.md` 和 `docs/CRON_WORK_LOG.md` 作为历史记录

**验收**：
- [ ] 归档目录创建
- [ ] 旧计划文档已移动并标注
- [ ] 历史记录文档保留

#### 任务 0.3: 更新项目文档（1小时）
**目标**：让所有文档指向新的执行计划

**步骤**：
1. 更新 `README.md`：
   - 在顶部添加："📋 当前执行计划：[JD_ALIGNED_ROADMAP.md](docs/JD_ALIGNED_ROADMAP.md)"
   - 更新"后续升级"章节，指向新路线图的 6 个 Phase
   
2. 更新 `docs/JD_ALIGNED_ROADMAP.md`：
   - 在顶部添加状态标签：
     ```markdown
     > **[当前主执行计划]** 最后更新：2026-05-18  
     > **执行状态**：Phase 0 准备阶段 → Phase 1 即将开始  
     > **进度追踪**：见本文档各 Phase 的验收标准
     ```

3. 创建 `docs/EXECUTION_TRANSITION.md` 记录切换决策：
   - 为什么切换到新路线图
   - 旧计划的哪些成果被保留
   - 新路线图的调整和强化

**验收**：
- [ ] README.md 已更新
- [ ] JD_ALIGNED_ROADMAP.md 添加状态标签
- [ ] EXECUTION_TRANSITION.md 创建完成

#### 任务 0.4: 环境准备（1-2小时）
**目标**：提前安装 Phase 1 需要的依赖，避免开发时被环境问题阻塞

**步骤**：
1. 更新 `requirements.txt`，添加 Phase 1 依赖：
   ```txt
   # Phase 1: Agent 工作流
   langchain>=0.1.0
   langchain-openai>=0.0.5
   langgraph>=0.0.20
   ```

2. 安装依赖：
   ```bash
   pip install langchain langchain-openai langgraph
   ```

3. 验证安装：
   ```python
   python -c "import langchain; import langgraph; print('LangChain installed successfully')"
   ```

4. 提前学习 LangChain 基础（可选，建议）：
   - 阅读 [LangChain Quick Start](https://python.langchain.com/docs/get_started/quickstart)
   - 运行官方示例代码
   - 理解 Tool、Agent、Chain 的基本概念

**验收**：
- [ ] requirements.txt 已更新
- [ ] LangChain 相关库安装成功
- [ ] 基础概念已了解（可选）

#### 任务 0.5: 创建 Phase 1 工作分支（10分钟）
**目标**：使用 Git 分支管理开发，便于回滚和代码审查

**步骤**：
1. 提交当前所有更改：
   ```bash
   git add .
   git commit -m "chore: prepare for JD-aligned roadmap execution"
   ```

2. 创建 Phase 1 分支：
   ```bash
   git checkout -b feature/phase1-agent-workflow
   ```

3. 推送到远程：
   ```bash
   git push -u origin feature/phase1-agent-workflow
   ```

**验收**：
- [ ] 当前更改已提交
- [ ] Phase 1 分支已创建
- [ ] 分支已推送到远程

### Week 1-2: Phase 1 执行（Agent 工作流基础）

**执行策略**：严格按照 `docs/JD_ALIGNED_ROADMAP.md` 中 Phase 1 的任务清单执行

**关键调整**（基于 Agent 优先级）：
1. **Day 1**: 工具封装层（压缩到 1 天，任务相对简单）
2. **Day 2**: LangChain 深度学习（新增，确保理解透彻）
3. **Day 3-4**: LangChain 集成（按原计划）
4. **Day 5-8**: 工作流编排（延长到 4 天，这是难点）
5. **Day 9-10**: Streamlit Agent Tab（按原计划）

**每日验收**：
- 每天结束前运行测试：`pytest tests -v`
- 每天提交代码：`git commit -m "feat(phase1): [具体功能]"`
- 每天更新 JD_ALIGNED_ROADMAP.md 中的验收标准复选框

**Week 1-2 结束验收**：
- [ ] 所有 Phase 1 任务完成
- [ ] 测试通过：`pytest tests/test_agent_tools.py tests/test_workflows.py -v`
- [ ] Agent Tab 可用，能演示完整工作流
- [ ] 文档更新：ARCHITECTURE.md, AGENT_DESIGN.md
- [ ] 录制 3 分钟 Demo 视频

### Week 3-12: 后续 Phase 执行

**执行顺序**（基于 Agent 优先级调整）：
- **Week 3-4**: Phase 2（数据分析与效果评估）
- **Week 5-6**: Phase 3（工程化，简化版：只做异步任务+日志）
- **Week 7-8**: Phase 4（高级 RAG）
- **Week 9-10**: Phase 5（多 Agent 协作，重点强化）
- **Week 11-12**: Phase 6（项目收尾与展示准备）

**每个 Phase 的执行流程**：
1. 创建新分支：`git checkout -b feature/phaseN-xxx`
2. 按路线图任务清单逐项执行
3. 每日提交代码和更新文档
4. Phase 结束时合并到 main 并推送：
   ```bash
   git checkout main
   git merge feature/phaseN-xxx
   git push origin main
   ```
5. 更新 README.md 和 JD_ALIGNED_ROADMAP.md 的进度

## 关键里程碑和检查点

### Week 2 检查点（Phase 1 完成）
**必须达成**：
- [ ] Agent 工具封装完成（6个工具）
- [ ] LangChain 集成成功
- [ ] 至少 1 个工作流可运行
- [ ] Agent Tab 可用

**如果未达成**：
- 评估是否需要延长 Phase 1（最多延长 3 天）
- 简化工作流数量（从 3 个减少到 2 个）
- 寻求帮助或查阅更多文档

### Week 4 检查点（Phase 2 完成）
**必须达成**：
- [ ] 数据分析模块可用
- [ ] 至少 1 个 A/B 实验完成
- [ ] 至少 2 个 Jupyter Notebook 完成

### Week 6 检查点（Phase 3 完成）
**必须达成**：
- [ ] 异步任务系统正常（Celery + Redis）
- [ ] 结构化日志系统运行

**可选**：
- [ ] 数据库迁移（如果时间充裕）
- [ ] Redis 缓存（如果时间充裕）

### Week 8 检查点（Phase 4 完成）
**必须达成**：
- [ ] Rerank 集成完成
- [ ] 至少 2 个检索优化实验完成
- [ ] 检索效果提升可量化

**关键决策**：
- [ ] 确定 Phase 5 使用的多 Agent 框架（AutoGen vs CrewAI）

### Week 10 检查点（Phase 5 完成）
**必须达成**：
- [ ] 4 个专业化 Agent 实现
- [ ] 多 Agent 协作场景可演示
- [ ] 记忆系统正常工作

### Week 12 检查点（Phase 6 完成，项目交付）
**必须达成**：
- [ ] 所有文档完成（30+ 页）
- [ ] 代码质量达标（black/flake8/mypy）
- [ ] 测试覆盖率 > 80%
- [ ] 3 个 Demo 视频录制完成
- [ ] 3 套 PPT 制作完成
- [ ] 面试脚本准备完整

## 风险控制措施（更新）

### 风险 1: Phase 1 学习曲线陡峭
**概率**: 中  
**影响**: 高（Phase 1 是基础，延期会影响后续所有 Phase）

**预防措施**：
- Week 0 提前学习 LangChain 基础
- Day 2 专门用于深度学习
- 准备降级方案：如果 LangGraph 太难，先用简单的 Chain

**应对措施**：
- 如果 Day 5 还不理解 LangGraph，立即查阅官方文档和示例
- 如果 Day 7 还无法实现工作流，考虑使用更简单的方案（自实现状态机）
- 最多延长 Phase 1 到 3 周（Week 1-3）

### 风险 2: 环境配置问题（Celery + Redis）
**概率**: 中  
**影响**: 中（只影响 Phase 3）

**预防措施**：
- Week 4 提前准备 Docker Compose 配置
- 使用官方镜像，避免手动安装

**应对措施**：
- 如果 Redis 安装失败，使用 Docker 运行
- 如果 Celery 配置复杂，简化为 FastAPI BackgroundTasks
- Phase 3 可以简化或跳过，不影响核心 Agent 能力展示

### 风险 3: 多 Agent 框架选型困难
**概率**: 低  
**影响**: 高（Phase 5 是核心）

**预防措施**：
- Week 8 Day 10 专门用于框架对比实验
- 提前阅读 AutoGen 和 CrewAI 的文档
- 准备两个框架的快速 Demo（各 2 小时）

**应对措施**：
- 如果两个框架都难以上手，选择文档更完善的（推荐 AutoGen）
- 如果框架学习成本过高，自实现简化版多 Agent 系统
- 最坏情况：Phase 5 只做基础协作，不用复杂框架

### 风险 4: 时间不足
**概率**: 中  
**影响**: 中

**预防措施**：
- 严格执行每周检查点
- 每周预留 0.5 天缓冲时间
- 优先保证高优先级 Phase（1, 2, 5, 6）

**应对措施**：
- 如果某个 Phase 超时 3 天，立即简化或跳过
- Phase 3 和 Phase 4 可以适当简化
- 最坏情况：只完成 Phase 1, 2, 5, 6（核心 Agent + 数据分析 + 文档）

## 成功标准

### 最低成功标准（必须达成）
- [ ] Phase 1 完成：Agent 工具调用和基础工作流
- [ ] Phase 2 完成：数据分析和可视化
- [ ] Phase 6 完成：文档和展示材料
- [ ] 测试覆盖率 > 70%
- [ ] 至少 1 个完整的 Agent 工作流可演示

### 理想成功标准（尽量达成）
- [ ] Phase 1-6 全部完成
- [ ] 测试覆盖率 > 80%
- [ ] 3 个 Agent 工作流可演示
- [ ] 多 Agent 协作场景可演示
- [ ] 所有文档和展示材料完整

### 卓越成功标准（超预期）
- [ ] 所有 Phase 高质量完成
- [ ] 测试覆盖率 > 85%
- [ ] 5+ 个 Agent 工作流场景
- [ ] 多 Agent 协作有创新应用
- [ ] 项目可部署到云端演示
- [ ] 有技术博客或分享 PPT

## 下一步行动（立即执行）

1. **确认计划**：用户确认是否接受此执行计划
2. **开始 Week 0**：执行任务 0.1-0.5（预计 1-2 天）
3. **启动 Phase 1**：从 Day 1 工具封装层开始

**第一个具体任务**：
```bash
# 任务 0.1: 完成 compare markdown escaping
# 预计时间：2 小时
# 验收：pytest tests/test_paper_compare.py -v 通过
```

