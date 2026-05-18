# 执行计划切换说明

> 文档创建时间：2026-05-18  
> 切换决策：从 HERMES_EXECUTION_PLAN.md 切换到 JD_ALIGNED_ROADMAP.md

## 为什么切换到新路线图

### 背景
项目原有执行计划 HERMES_EXECUTION_PLAN.md 聚焦于评估体系和 RAG 深化，已执行 7/20 轮，取得了一定进展（202 passed tests, evaluation 骨架已建立）。

### 切换原因
1. **岗位对齐需求**：用户创建了基于「大语言模型与 Agent 应用开发实习生」岗位 JD 的新路线图
2. **核心优先级调整**：用户明确优先看重 **Agent 系统能力**（任务拆解、工具调用、工作流编排、多Agent协作）
3. **时间投入充足**：用户有 12 周全职投入（每周 4-5 天），足以完成新路线图的 6 个 Phase
4. **技术栈升级**：新路线图引入 LangChain/LangGraph/AutoGen/CrewAI 等业界主流 Agent 框架，更符合岗位要求

### 决策过程
经过详细的计划审查和用户确认：
- **探索阶段**：3 个并行 agents 分析了项目现状、计划冲突、路线图质量
- **用户决策**：用户选择完全切换到新路线图，优先 Agent 系统能力
- **风险评估**：识别了学习曲线、环境配置、时间压力等风险，并制定了应对措施

## 旧计划的保留成果

### 已完成的工作（保留并继续使用）
1. **评估体系骨架**：
   - `app/evaluation/schemas.py`：QAEvalSample, ComparisonEvalSample, RetrievalEvalResult
   - `app/evaluation/scripts/`：build_seed_dataset, evaluate_retrieval, evaluate_qa, evaluate_comparison
   - `app/evaluation/datasets/`：qa_eval_seed.jsonl, comparison_eval_seed.jsonl
   - `app/evaluation/reports/`：baseline_report.md, retrieval/qa 报告

2. **测试基线**：
   - 202 passed, 1 skipped
   - 测试覆盖率约 70%
   - 核心功能测试完整

3. **核心功能**：
   - PDF 解析、笔记生成、RAG 问答、多论文对比
   - 5 篇真实论文数据
   - Streamlit 5-Tab UI
   - FastAPI 13 endpoints

4. **文档**：
   - ARCHITECTURE.md, MVP_REQUIREMENTS.md, DEVELOPMENT_LOG.md
   - 详细的执行状态日志

### 如何利用这些成果
- **Phase 2（数据分析与效果评估）**：直接使用现有 evaluation 骨架，扩展数据分析和可视化
- **Phase 4（高级 RAG）**：在现有 RAG 基础上增强 Rerank、Hybrid Search 等技术
- **Phase 6（项目收尾）**：利用现有文档和测试基线，补充 Agent 相关文档

### 归档处理
- 旧计划文档已移至 `docs/archive/`
- 添加了归档标注，说明替代文档
- 保留 EXECUTION_STATUS.md 和 CRON_WORK_LOG.md 作为历史记录

## 新路线图的调整和强化

### 基于 Agent 优先级的调整

#### Phase 优先级排序
**高优先级（必须完成）**：
1. Phase 1: Agent 工作流基础（Week 1-2）- **核心优先级**
2. Phase 5: 多 Agent 协作与记忆管理（Week 9-10）- **核心优先级**
3. Phase 2: 数据分析与效果评估（Week 3-4）- 展示数据能力
4. Phase 6: 项目收尾与展示准备（Week 11-12）- 面试必需

**中优先级（尽量完成）**：
5. Phase 4: 高级 RAG 与检索增强（Week 7-8）- 技术深度

**可简化优先级**：
6. Phase 3: 工程化与生产就绪（Week 5-6）- 可简化为异步任务+日志

#### Phase 1 强化（Agent 工作流基础）
- **Day 1**: 工具封装层（压缩到 1 天）
- **Day 2**: LangChain 深度学习（新增，确保理解透彻）
- **Day 3-4**: LangChain 集成
- **Day 5-8**: 工作流编排（延长到 4 天，这是难点）
- **Day 9-10**: Streamlit Agent Tab

#### Phase 5 强化（多 Agent 协作）
- 提前在 Week 8 确定多 Agent 框架选型（AutoGen vs CrewAI）
- 增加 Agent 协作场景（从 3 个增加到 5 个）
- 增加 Agent 决策可视化和调试工具

### 风险控制措施

#### 技术风险
- **LangChain 学习曲线**：Week 0 提前学习，Day 2 深度学习，准备降级方案
- **环境配置复杂**：Week 4 提前准备 Docker Compose，使用官方镜像
- **多 Agent 框架选型**：Week 8 Day 10 专门对比实验

#### 时间风险
- **每周检查点**：严格执行，及时调整
- **缓冲时间**：每周预留 0.5 天
- **降级方案**：Phase 3 和 Phase 4 可简化

#### 质量风险
- **测试覆盖率**：每个 Phase 完成后立即补充测试
- **代码质量**：每周运行 black/flake8
- **文档完整性**：边开发边写文档

## 执行路径

### Week 0（准备阶段，1-2天）
- [x] 任务 0.1: 完成当前未完成工作（compare markdown escaping）
- [x] 任务 0.2: 归档旧计划文档
- [x] 任务 0.3: 更新项目文档（进行中）
- [ ] 任务 0.4: 环境准备（安装 LangChain/LangGraph）
- [ ] 任务 0.5: 创建 Phase 1 工作分支

### Week 1-12（6 个 Phase）
详见 [JD_ALIGNED_ROADMAP.md](JD_ALIGNED_ROADMAP.md)

## 成功标准

### 最低成功标准（必须达成）
- Phase 1 完成：Agent 工具调用和基础工作流
- Phase 2 完成：数据分析和可视化
- Phase 6 完成：文档和展示材料
- 测试覆盖率 > 70%
- 至少 1 个完整的 Agent 工作流可演示

### 理想成功标准（尽量达成）
- Phase 1-6 全部完成
- 测试覆盖率 > 80%
- 3 个 Agent 工作流可演示
- 多 Agent 协作场景可演示
- 所有文档和展示材料完整

### 卓越成功标准（超预期）
- 所有 Phase 高质量完成
- 测试覆盖率 > 85%
- 5+ 个 Agent 工作流场景
- 多 Agent 协作有创新应用
- 项目可部署到云端演示

## 回滚方案

如果新路线图执行遇到严重问题，可以回退到旧计划：
1. 恢复 `docs/archive/HERMES_EXECUTION_PLAN.md` 到 `docs/`
2. 继续执行 P0 评估体系和 P1 RAG 深化
3. 所有历史记录都保留，可随时恢复

但基于当前评估，新路线图是可行的，建议坚持执行。

## 相关文档

- **新执行计划**：[JD_ALIGNED_ROADMAP.md](JD_ALIGNED_ROADMAP.md)
- **任务清单**：[.claude/tasks/current-tasks.md](../.claude/tasks/current-tasks.md)
- **详细计划**：[.claude/plans/current-plan.md](../.claude/plans/current-plan.md)
- **归档计划**：[archive/HERMES_EXECUTION_PLAN.md](archive/HERMES_EXECUTION_PLAN.md)
- **岗位 JD**：[JD.md](JD.md)
