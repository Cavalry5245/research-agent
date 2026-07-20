# ResearchAgent 项目全景档案

> 本目录是 ResearchAgent 项目的**唯一事实底稿（Single Source of Truth）**。
> 用途：应聘不同岗位时，直接据此裁剪简历项目经历、准备面试回答，无需重新阅读整个代码仓库或回忆项目过程。

---

## 0. 文档说明

### 0.1 文档用途

- 完整、准确、可长期维护地保存 ResearchAgent 的背景、需求、架构、技术实现、设计决策、实验结果、问题排查、个人贡献与求职素材。
- 面向两类使用场景：
  1. **求职**：按目标岗位裁剪简历、准备面试。
  2. **复盘**：作为项目技术底稿长期维护。

### 0.2 信息来源

本档案的结论来自以下证据，按可信度排序：

1. 源代码（`app/`、`frontend/`、`ui/`、`tests/`）
2. 配置文件（`app/config.py`、`.env.example`、`docker-compose.yml`）
3. 实验/评测结果（`app/evaluation/reports/`、`app/analytics/reports/`、`app/storage/mvp_gate_*`）
4. 项目文档（`docs/`、`README.md`、`CHANGELOG.md`、`docs/MVP_REQUIREMENTS.md`）
5. Git 提交记录
6. 用户（项目作者）在建档对话中的明确确认

> 所有关键结论在 `evidence_index.md` 中建立了证据索引。

### 0.3 文档版本

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-07-17 | 首次建档。基于代码仓库全量盘点 + 作者 4 项 P0 决策 + 3 项 P1 决策 |
| v1.1 | 2026-07-21 | 记录 Chroma + API bge-m3 索引重建、激活与只读验证证据 |

### 0.4 已确认范围（作者明确决策）

| 事项 | 结论 |
|---|---|
| 团队规模 | **个人独立项目**（git 仅一名作者，Chase Huang / Chase 为同一人两个身份） |
| 核心叙事主线 | **两条主线并重**：Legacy Paper Tools + Research Pipeline |
| 向量库技术表述 | **默认 Chroma，JSON 仅作显式诊断/回滚后端**；版本化 collection 为 `research_papers_bge_m3_v1` |
| 部署状态 | **仅本地 / Demo 运行**，无真实上线、无真实用户量 |
| 目标岗位 | LLM 应用/RAG/Agent；后端/全栈开发；算法/ML/评测 |
| 项目时间 | 以 git 为准：**2026-05 — 2026-07**（约 2 个月） |
| QA 评测 gold 答案来源 | **自动生成 + 人工校验** |

### 0.5 待补充范围

详见 `11_missing_information.md`。当前主要缺口：
- 真实 A/B 实验结果（`--executor real`）是否留存
- embedding 模型对比真实结果 JSON

### 0.6 保密 / 不可公开内容

- 作者确认：仅本地/Demo 运行，无涉密内容。
- 简历/面试中**不得**声称：真实用户量、生产上线、团队规模>1。
- LLM/Embedding API Key 等凭据不出现在任何档案文本中；本次真实重建使用本地 `.env` 中的实际 key，但从未输出或提交其值。

### 0.6.1 Chroma 索引现状（2026-07-21）

- `chromadb==1.5.9`，默认后端 Chroma，cosine collection `research_papers_bge_m3_v1`。
- embedding 逻辑模型为 API `bge-m3`，provider wire ID 为 `BAAI/bge-m3`；索引统一维度 1024。
- 53 份顶层 `*_parsed.json` 已重建为 8,182 个唯一且回读验证通过的 chunk，manifest 与 collection 均为 `ready`。
- canary 为 1 篇/129 chunks；支持原子 manifest、每篇源哈希与 ID 集校验、断点续跑和只读 `--verify-only`。
- 运行时 Chroma 数据、成功/失败 manifest 均被 Git 忽略且未跟踪；这不代表已部署或已合并到主分支。

### 0.7 事实 / 推断 / 待确认标记规则

全档案统一使用以下标记：

| 标记 | 含义 |
|---|---|
| ✅ 事实 | 有代码/实验/日志/配置直接证明 |
| 📄 文档描述 | 文档明确写了，但代码或结果未完全验证 |
| 🔍 合理推断 | 基于命名、结构、上下文的推断 |
| ⚠️ 矛盾 | 文档/配置与代码实现不一致（详见 `evidence_index.md` 矛盾表） |
| ❓ 待确认 | 材料不足，需作者补充 |
| 🚧 计划/未完成 | 文档提出但代码未实现，或实现为 stub |

### 0.8 档案文件索引

| 文件 | 内容 |
|---|---|
| `README.md` | 本文件：档案说明 + 索引 |
| `00_project_overview.md` | 项目概览、多版本介绍、价值 |
| `01_background_and_requirements.md` | 背景、问题定义、需求与功能 |
| `02_architecture_and_workflows.md` | 总体架构、数据流、运行流程 |
| `03_core_modules.md` | 核心模块详解（统一模板） |
| `04_data_and_evaluation.md` | 数据处理、实验、评测、成果指标 |
| `05_decisions_and_tradeoffs.md` | 技术选型、设计决策、ADR |
| `06_debugging_and_optimization.md` | 问题排查、故障、优化记录 |
| `07_results_and_contributions.md` | 项目成果、个人贡献、能力标签 |
| `08_job_mapping.md` | 岗位映射、不同岗位定位 |
| `09_resume_materials.md` | 简历项目素材库 |
| `10_interview_materials.md` | 面试素材库（STAR + 深挖问题） |
| `11_missing_information.md` | 待补充信息清单（P0/P1/P2） |
| `evidence_index.md` | 证据索引 + 矛盾清单 |

### 0.9 使用建议

- **快速取用简历素材**：只看 `09_resume_materials.md` + `08_job_mapping.md`。
- **面试前准备**：`10_interview_materials.md` + `05_decisions_and_tradeoffs.md` + `06_debugging_and_optimization.md`。
- **核实某个技术表述能不能写**：查 `evidence_index.md` 的可信度与矛盾表。
- **档案维护**：新事实先更新 `evidence_index.md`，再同步到对应章节。
