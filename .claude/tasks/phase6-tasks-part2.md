# Phase 6 任务清单 - Part 2: Demo 材料与最终验收

## 任务 6.4.3: 准备面试讲解脚本

- [ ] 3 分钟电梯演讲脚本
  - 验收标准：计时 3 分钟内，流畅自然
  - 涉及文件：`demos/interview_script_3min.md`（新建）
  - 内容要求：
    - 项目是什么（20s）：AI 论文研究助手，支持笔记生成、RAG 问答、多论文对比
    - 解决什么问题（30s）：提升论文阅读效率，自动化信息提取
    - 核心技术亮点（90s）：
      - Agent 系统（LangChain + LangGraph）
      - 高级 RAG（Rerank +19% hit@5）
      - 多 Agent 协作（Supervisor 模式）
    - 个人贡献（30s）：独立完成 15000+ 行代码、6 个 A/B 实验、30+ 页文档
  - 完成后必须记录结果：

- [ ] 10 分钟技术面试脚本
  - 验收标准：计时 10 分钟内，逻辑清晰
  - 涉及文件：`demos/interview_script_10min.md`（新建）
  - 内容要求：
    - 系统架构概览（2 分钟）
    - Agent 工作流设计（2 分钟）
    - RAG 技术栈详解（2 分钟）
    - 多 Agent 协作实现（2 分钟）
    - 数据分析与优化（1 分钟）
    - Q&A 准备（1 分钟）
  - 完成后必须记录结果：

- [ ] 30 分钟深度技术分享脚本
  - 验收标准：计时 30 分钟，包含代码演示
  - 涉及文件：`demos/interview_script_30min.md`（新建）
  - 章节时间分配：
    - 项目背景（2 分钟）
    - 技术架构全景（5 分钟）
    - Agent 系统详解（7 分钟）
    - RAG 技术与实验（7 分钟）
    - 工程化实践（4 分钟）
    - 代码演示（3 分钟）
    - Q&A（2 分钟）
  - 完成后必须记录结果：

## 任务 6.4.4: 准备常见问题回答

- [ ] 技术问题清单与标准答案（15-20 个）
  - 验收标准：每个问题有 2-3 分钟标准答案，格式：背景 → 方案 → 效果 → 反思
  - 涉及文件：`demos/interview_qa.md`（新建）
  - 问题分类：
    
    **Agent 相关（5 个）**：
    1. 为什么选择 LangGraph 而不是 AutoGen？
    2. Supervisor 模式 vs ReAct 模式的优劣？
    3. 如何保证 Agent 的可控性和稳定性？
    4. 记忆系统的设计思路？
    5. 如何调试和监控 Agent 执行？
    
    **RAG 相关（5 个）**：
    1. 为什么 Rerank 能提升检索效果？
    2. Hybrid Search 的 α 如何调优？
    3. 如何解决检索召回率低的问题？
    4. Query Rewrite 何时有效、何时无效？
    5. 如何评估 RAG 系统的质量？
    
    **工程化相关（5 个）**：
    1. 为什么不使用 Celery 而用 BackgroundTasks？
    2. 如何设计异步任务系统？
    3. 请求追踪的实现原理？
    4. 日志系统的设计考虑？
    5. 如何优化 API 响应时间？
    
    **综合问题（5 个）**：
    1. 遇到的最大挑战是什么？如何解决？
    2. 如果重新做会有什么改进？
    3. 如何保证代码质量？
    4. A/B 测试的设计原则？
    5. 项目的不足之处和未来规划？
  - 完成后必须记录结果：

---

## 任务 6.5: 最终验收与收尾（Day 10）

### 6.5.1 代码与文档检查清单

- [ ] 运行完整测试套件
  - 验收标准：520+ passed, 覆盖率 >80%
  - 需要运行的命令：
    ```bash
    pytest tests/ -v --cov=app --cov-report=term
    pytest tests/ -q  # 快速检查
    ```
  - 涉及文件：无
  - 完成后必须记录结果：

- [ ] 检查所有文档链接有效
  - 验收标准：无 404 链接
  - 需要运行的命令：
    ```bash
    # 如果安装了 markdown-link-check
    find docs -name "*.md" -exec markdown-link-check {} \;
    # 或手动检查
    ```
  - 涉及文件：所有 Markdown 文档
  - 完成后必须记录结果：

- [ ] 验证所有代码示例可运行
  - 验收标准：文档中的代码示例无语法错误
  - 需要运行的命令：无（手动抽查）
  - 涉及文件：所有文档中的代码块
  - 完成后必须记录结果：

- [ ] 生成最终代码统计报告
  - 验收标准：代码行数 > 12000，测试行数 > 5000，文档页数 > 30
  - 需要运行的命令：
    ```bash
    cloc app/ tests/ ui/ --by-file > code_stats.txt
    # 或
    find app tests ui -name "*.py" | xargs wc -l
    ```
  - 涉及文件：`code_stats.txt`（新建）
  - 完成后必须记录结果：

### 6.5.2 更新顶层文档

- [ ] 更新 README.md 为最终版本
  - 验收标准：包含项目徽章、Demo 链接、详细使用说明、文档导航
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：`README.md`
  - 更新内容：
    - 添加项目徽章（tests passing、coverage）
    - 添加 Demo 视频链接 / GIF 动图
    - 添加详细的安装与使用说明
    - 添加文档导航链接
  - 完成后必须记录结果：

- [ ] 生成 requirements.txt 最终版本
  - 验收标准：包含所有依赖，版本号明确
  - 需要运行的命令：
    ```bash
    # 选项 1：freeze 当前环境（可能包含不需要的包）
    pip freeze > requirements_freeze.txt
    # 选项 2：保持手动维护的 requirements.txt（推荐）
    # 验证依赖完整性
    pip install -r requirements.txt --dry-run
    ```
  - 涉及文件：`requirements.txt`
  - 完成后必须记录结果：

- [ ] 创建 .github/workflows/ci.yml（可选）
  - 验收标准：push 后自动运行测试（如果有 GitHub 仓库）
  - 需要运行的命令：无（手动编辑）
  - 涉及文件：`.github/workflows/ci.yml`（新建）
  - 内容示例：
    ```yaml
    name: CI
    on: [push, pull_request]
    jobs:
      test:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v2
          - uses: actions/setup-python@v2
            with:
              python-version: '3.11'
          - run: pip install -r requirements.txt
          - run: pytest tests/ -q
    ```
  - 完成后必须记录结果：

### 6.5.3 生成项目展示网站（可选）

- [ ] 使用 GitHub Pages 发布文档
  - 验收标准：公开可访问的文档站点
  - 工具：MkDocs 或 Docusaurus
  - 需要运行的命令：
    ```bash
    # 如果使用 MkDocs
    pip install mkdocs mkdocs-material
    mkdocs new .
    # 编辑 mkdocs.yml
    mkdocs build
    mkdocs gh-deploy
    ```
  - 涉及文件：`mkdocs.yml`, `docs/`
  - 完成后必须记录结果：

- [ ] 录制项目演示 GIF
  - 验收标准：< 5MB，嵌入 README.md，5-10 秒核心功能循环演示
  - 工具：LICEcap / ScreenToGif
  - 涉及文件：`demos/demo.gif`（新建）
  - 完成后必须记录结果：

### 6.5.4 最终提交

- [ ] 提交所有 Phase 6 更改
  - 验收标准：工作目录干净
  - 需要运行的命令：
    ```bash
    git status
    git add .
    git commit -m "feat(phase6): finalization - docs, quality, demo materials"
    git log --oneline -5
    ```
  - 涉及文件：所有修改文件
  - 完成后必须记录结果：

- [ ] 合并所有 Phase 分支到 main（如需要）
  - 验收标准：main 分支包含所有功能
  - 需要运行的命令：
    ```bash
    git checkout main
    git merge feature/phase1-agent-workflow
    git merge feature/phase2-analytics-evaluation
    git merge feature/phase3-production-readiness
    git merge feature/phase4-advanced-rag
    git merge feature/phase5-multi-agent-collaboration
    git merge feature/phase6-finalization
    # 或者使用 rebase/squash 策略
    ```
  - 涉及文件：无
  - 完成后必须记录结果：

- [ ] 打 tag 标记最终版本
  - 验收标准：tag 已创建
  - 需要运行的命令：
    ```bash
    git tag -a v1.0.0 -m "Release v1.0.0: Complete JD-aligned roadmap"
    git tag -l
    git push origin v1.0.0  # 如果有远程仓库
    ```
  - 涉及文件：无
  - 完成后必须记录结果：

---

## Phase 6 验收标准（Week 11-12 检查点）

### 文档完整性
- [ ] 30+ 页技术文档齐全
- [ ] 所有 API 端点有文档
- [ ] 用户手册、配置指南、FAQ 完成
- [ ] 项目总结与经验总结完成

### 代码质量
- [ ] black / isort / flake8 检查通过
- [ ] 核心模块 mypy 类型检查通过
- [ ] 平均代码复杂度 < B 级
- [ ] 无明显代码坏味道

### 测试覆盖率
- [ ] 总体覆盖率 > 80%
- [ ] 测试数量 > 520
- [ ] 测试通过率 100%
- [ ] 覆盖率报告已生成

### 展示材料
- [ ] 3 个 Demo 视频录制完成
- [ ] 3 套 PPT 制作完成
- [ ] 面试脚本（3 分钟 / 10 分钟 / 30 分钟）完成
- [ ] 常见问题标准答案完成

### 最终交付
- [ ] README.md 最终版本
- [ ] 代码统计报告
- [ ] 所有分支已合并
- [ ] 版本 tag 已打

---

## Phase 6 关键产出物清单

| 类别 | 产出物 | 数量/指标 |
|------|-------|----------|
| **文档** | 技术文档 | 30+ 页 |
| | API 文档 | 30+ 端点 |
| | 用户手册 | 1 份 |
| | 项目总结 | 2 份 |
| **代码** | 测试数量 | 520+ passed |
| | 测试覆盖率 | >80% |
| | 代码行数 | >12000 |
| **展示** | Demo 视频 | 3 个 |
| | PPT | 3 套（45 页） |
| | 面试脚本 | 3 个版本 |
| | 常见问题 | 20 个 |

---

## Phase 6 与 JD 对齐检查表

| JD 要求 | Phase 6 覆盖 | 验收标准 |
|---------|-------------|---------|
| 岗位职责 1（Prompt/调用链路/优化）| 文档完善 | RAG_TECHNIQUES.md 覆盖 |
| 岗位职责 2（Agent 开发）| Agent 系统文档 | AGENT_DESIGN.md 完整 |
| 岗位职责 3（数据分析）| 实验 PPT | 20 页数据分析展示 |
| 岗位职责 4（效果评估）| 实验报告 | EXPERIMENT_RESULTS.md |
| 岗位职责 6（文档编写）| 30+ 页文档 | 所有文档齐全 |
| 任职要求 7（文档能力）| 3 套 PPT + 脚本 | 清晰表达技术方案 |
| 加分项 6（自驱力）| 独立完成 Phase 6 | 自主规划与执行 |

---

## 任务执行建议

1. **Day 1-3 优先完成文档**：文档是最耗时但最重要的交付物
2. **Day 4-5 代码质量提升可并行**：使用自动化工具快速完成
3. **Day 6-7 测试覆盖率提升要聚焦**：优先补充覆盖率低的核心模块
4. **Day 8-10 Demo 材料需提前准备**：录屏前先写好脚本，避免临场发挥

## 常见问题

**Q: 如果时间不够，哪些任务可以降低优先级？**
A: 可选任务：GitHub Pages、项目演示 GIF、CI/CD 配置。核心任务：技术文档、3 个 Demo 视频、3 套 PPT 必须完成。

**Q: Demo 视频用什么工具录制？**
A: 推荐 OBS Studio（免费开源）或 QuickTime（macOS 自带）。

**Q: PPT 用什么风格？**
A: 技术风格，简洁清晰，避免花哨动画。推荐使用暗色主题 + 代码高亮。

**Q: 面试脚本需要背诵吗？**
A: 不需要背诵，理解核心逻辑即可。重点是能脱稿讲清楚技术实现和亮点。
