# Phase 6 快速执行指南

## 📅 时间规划（10 天）

```
Day 0-1:  文档基础（6.0, 6.1.1）
Day 2-3:  文档完善（6.1.2, 6.1.3）
Day 4:    代码格式化（6.2.1, 6.2.2）
Day 5:    代码优化（6.2.3）
Day 6:    测试分析与补充（6.3.1, 6.3.2）
Day 7:    测试报告（6.3.3）
Day 8:    视频录制（6.4.1）
Day 9:    PPT 制作（6.4.2）
Day 10:   脚本与收尾（6.4.3, 6.4.4, 6.5）
```

---

## ⚡ 快速开始

### 第一步：创建分支和安装工具

```bash
cd /home/chase/projects/ResearchAgent
conda activate research_agent

# 创建 Phase 6 分支
git checkout -b feature/phase6-finalization

# 安装代码质量工具
pip install black isort flake8 mypy pytest-cov radon

# 验证安装
python -c "import black, isort, pytest_cov, radon; print('✅ All tools installed')"

# 基线测试
pytest tests -q
```

**预期结果**：489 passed, 1 skipped

---

## 📋 每日执行清单

### Day 0-1: 文档基础

**目标**：完成核心技术文档查漏补缺

```bash
# 1. 审查 ARCHITECTURE.md，添加 Phase 6 总结章节
# 2. 创建 USAGE.md（快速开始、功能清单、使用示例、FAQ）
# 3. 创建 API_REFERENCE.md（30+ 端点说明）
# 4. 创建 CONFIGURATION.md（40+ 环境变量说明）
```

**验收**：4 个文档文件创建完成

---

### Day 2-3: 文档完善

**目标**：完成项目总结文档和格式统一

```bash
# 1. 创建 PROJECT_SUMMARY.md
# 2. 创建 LESSONS_LEARNED.md
# 3. 更新 CHANGELOG.md

# 4. 统一文档格式
find docs -name "*.md" | xargs sed -i 's/agent/Agent/g'  # 示例

# 5. 生成文档索引
# 编辑 docs/README.md

# 6. 拼写检查（如果有工具）
# aspell check docs/*.md
```

**验收**：7 个文档任务完成

---

### Day 4: 代码格式化

**目标**：运行自动化工具，修复格式问题

```bash
# 1. Black 格式化
black app/ tests/ ui/ --line-length 100
git diff --stat

# 2. isort 排序 import
isort app/ tests/ ui/ --profile black
git diff --stat

# 3. flake8 检查
flake8 app/ tests/ --max-line-length=100 --extend-ignore=E203,W503 --count

# 4. mypy 类型检查
mypy app/agents/ app/services/ --ignore-missing-imports --no-strict-optional

# 5. radon 复杂度检查
radon cc app/ -a -nb
radon cc app/ -s -n D  # 查看 D 级及以上的函数

# 提交格式化更改
git add app/ tests/ ui/
git commit -m "style: format code with black/isort, fix flake8 issues"
```

**验收**：flake8 0 个错误，mypy 核心模块通过

---

### Day 5: 代码优化

**目标**：补充类型注解和 docstring，重构复杂函数

```bash
# 1. 补充核心函数类型注解
# 编辑 app/services/paper_qa.py
# 编辑 app/services/note_generator.py
# 编辑 app/agents/paper_research_agent.py

# 2. 补充 docstring（Google 风格）
# 所有 public 函数添加文档字符串

# 3. 重构复杂函数
radon cc app/ -n C  # 查找需要重构的函数

# 4. 移除无用代码
# 删除注释代码、未使用 import、空文件

# 提交优化更改
git add app/
git commit -m "refactor: add type hints, docstrings, and simplify complex functions"
```

**验收**：核心模块 mypy strict 模式通过

---

### Day 6: 测试分析与补充

**目标**：生成覆盖率报告，补充缺失测试

```bash
# 1. 运行覆盖率测试
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
open htmlcov/index.html  # macOS
# xdg-open htmlcov/index.html  # Linux

# 2. 识别未覆盖模块
coverage report --skip-covered --sort=cover

# 3. 补充边界条件测试（10 个）
# 创建/扩展 tests/test_edge_cases.py

# 4. 补充异常处理测试（8 个）
# 创建/扩展 tests/test_error_handling.py

# 5. 补充集成测试（5 个）
# 扩展 tests/integration/

# 6. 补充性能测试（3 个）
# 创建 tests/test_performance.py

# 运行新测试
pytest tests/test_edge_cases.py tests/test_error_handling.py tests/test_performance.py -v
```

**验收**：新增 26+ 个测试

---

### Day 7: 测试报告

**目标**：生成最终覆盖率和测试报告

```bash
# 1. 运行完整测试套件
pytest tests/ --cov=app --cov-report=html --cov-report=xml --cov-report=term

# 2. 生成测试统计
pytest tests/ -v --tb=no | tee test_report.txt

# 3. 提交测试更改
git add tests/
git commit -m "test: increase coverage to 80%+, add 26 new tests"
```

**验收**：覆盖率 > 80%，测试数量 > 520

---

### Day 8: 视频录制

**目标**：录制 3 个 Demo 视频

**准备工作**：
1. 确保 FastAPI 和 Streamlit 可正常启动
2. 准备示例论文 PDF（5 篇）
3. 准备演示脚本
4. 安装录屏工具（OBS Studio / QuickTime）

**录制顺序**：

```bash
# 启动服务
uvicorn app.main:app --reload &
streamlit run ui/streamlit_app.py &

# 录制视频 1：快速功能演示（3 分钟）
# - 上传论文 → 生成笔记 → 问答 → 对比 → 导出

# 录制视频 2：Agent 系统深度演示（5 分钟）
# - Agent Tab → 工作流 → 多 Agent 协作 → 记忆 → 监控

# 录制视频 3：技术深度与数据分析（8-10 分钟）
# - RAG 技术栈 → A/B 实验 → Jupyter Notebook → 架构图 → 性能指标

# 停止服务
pkill -f uvicorn
pkill -f streamlit
```

**输出**：`demos/video1_quick_demo.mp4`, `video2_agent_demo.mp4`, `video3_technical_depth.mp4`

---

### Day 9: PPT 制作

**目标**：制作 3 套 PPT

**使用工具**：PowerPoint / Keynote / Google Slides

**制作顺序**：

1. **PPT 1: 项目概览（10-12 页）**
   - 封面 → 背景 → 功能 → 技术栈 → 演示 → 指标 → 收获 → Q&A

2. **PPT 2: 技术架构深度（15-18 页）**
   - 封面 → 架构图 → Agent 设计 → RAG 流程 → 多 Agent → 记忆 → 工程化 → 数据流 → 亮点 → 选型 → 优化 → 未来 → Q&A

3. **PPT 3: 实验与数据分析（18-20 页）**
   - 封面 → 评估体系 → 6 个 A/B 实验（各 2 页）→ 检索分析 → 失败分析 → 性能对比 → 推荐配置 → 方法论 → 经验 → 未来 → Q&A

**输出**：`demos/ppt1_project_overview.pptx`, `ppt2_technical_architecture.pptx`, `ppt3_experiments_analysis.pptx`

---

### Day 10: 脚本与收尾

**目标**：准备面试脚本和最终验收

```bash
# 1. 准备面试脚本（3 分钟 / 10 分钟 / 30 分钟）
# 创建 demos/interview_script_3min.md
# 创建 demos/interview_script_10min.md
# 创建 demos/interview_script_30min.md

# 2. 准备常见问题回答（15-20 个）
# 创建 demos/interview_qa.md

# 3. 运行完整测试
pytest tests/ -v --cov=app --cov-report=term

# 4. 生成代码统计
cloc app/ tests/ ui/ --by-file > code_stats.txt

# 5. 更新 README.md 最终版本
# 添加 Demo 视频链接、项目徽章、详细使用说明

# 6. 提交所有 Phase 6 更改
git add .
git commit -m "feat(phase6): finalization - docs, quality, demo materials"

# 7. 合并到 main（可选）
git checkout main
git merge feature/phase6-finalization

# 8. 打 tag
git tag -a v1.0.0 -m "Release v1.0.0: Complete JD-aligned roadmap"
```

**验收**：所有 Phase 6 验收标准达成

---

## 🎯 关键验收点

### 文档验收（Day 3）
- [ ] 30+ 页技术文档齐全
- [ ] 所有 API 端点有文档
- [ ] 格式统一，无拼写错误

### 代码验收（Day 5）
- [ ] black/isort/flake8 通过
- [ ] 核心模块 mypy 通过
- [ ] 平均复杂度 < B 级

### 测试验收（Day 7）
- [ ] 覆盖率 > 80%
- [ ] 测试数量 > 520
- [ ] 测试通过率 100%

### 展示验收（Day 10）
- [ ] 3 个 Demo 视频完成
- [ ] 3 套 PPT 完成（45 页）
- [ ] 面试脚本完成

---

## 💡 执行技巧

### 文档编写技巧
1. **复用现有内容**：从现有文档（AGENT_DESIGN.md、RAG_TECHNIQUES.md）中提取内容
2. **使用模板**：API 文档可从 OpenAPI schema 生成
3. **先框架后细节**：先列出章节大纲，再填充内容

### 代码质量技巧
1. **自动化优先**：能用工具自动修复的不手动改
2. **批量操作**：sed/awk 批量替换术语
3. **渐进式重构**：先修复简单问题，复杂函数单独处理

### 测试补充技巧
1. **看覆盖率报告**：优先补充覆盖率低的核心模块
2. **复用测试逻辑**：参数化测试覆盖多种边界条件
3. **Mock 外部依赖**：LLM/向量库失败测试用 Mock

### 视频录制技巧
1. **提前写脚本**：按脚本操作，避免临场忘词
2. **录制前测试**：确保所有功能正常
3. **分段录制**：每个场景单独录，后期剪辑拼接
4. **保持简洁**：3 分钟视频只展示核心流程

### PPT 制作技巧
1. **使用截图**：从 Streamlit/Jupyter 截图作为素材
2. **图表清晰**：A/B 实验结果用对比柱状图
3. **避免堆砌**：每页 1 个核心观点，不超过 7 行文字

---

## ⚠️ 常见问题

### Q: 文档太多写不完怎么办？
A: 优先完成核心 4 个：USAGE.md、API_REFERENCE.md、PROJECT_SUMMARY.md、LESSONS_LEARNED.md

### Q: 代码质量工具报错太多？
A: 先修复核心模块（agents/、services/），测试代码可适当放宽要求

### Q: 测试覆盖率上不去？
A: 聚焦核心业务逻辑，跳过配置类、常量类、简单 getter/setter

### Q: 视频录制卡顿？
A: 降低分辨率到 720p，或录制前关闭其他应用释放资源

### Q: PPT 没有设计经验？
A: 使用暗色主题模板，代码用 Monokai 配色，图表用 Matplotlib 默认颜色

### Q: 时间不够怎么办？
A: 砍掉可选任务（GitHub Pages、CI/CD、项目 GIF），聚焦核心交付物

---

## 📊 每日进度追踪

在 `.claude/tasks/current-tasks.md` 中勾选完成的任务，并记录：
- ✅ 完成时间
- ✅ 验收结果
- ✅ 遇到的问题和解决方案

---

## 🎉 完成 Phase 6 后

你将拥有：
- ✅ 30+ 页完整技术文档
- ✅ 80%+ 测试覆盖率
- ✅ 3 个 Demo 视频
- ✅ 3 套专业 PPT（45 页）
- ✅ 完整的面试准备材料
- ✅ 一个完全对齐 JD 要求的完整项目

**下一步**：准备简历，投递岗位，准备面试！🚀
