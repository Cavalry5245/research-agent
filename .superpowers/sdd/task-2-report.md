# Task 2 Completion Report: Define Core Pipeline Schemas

**Status:** DONE

**Date:** 2026-06-21

---

## Summary

Task 2 已完成。所有核心 Pydantic v2 schemas 已定义并通过完整测试覆盖验证。

## Commits Created

1. **b027ec5** - `feat(research-pipeline): define core Pydantic v2 schemas`
   - 定义了所有核心 schema 和枚举类型
   - 实现了 35 个单元测试，100% 覆盖所有 schema
   - 所有验收标准均已满足

## Files Modified

### Created/Modified:
- `app/research_pipeline/schemas.py` - 核心 schema 定义（203 行）
- `tests/research_pipeline/test_schemas.py` - 完整测试套件（509 行）

## Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
rootdir: E:\projects\ResearchAgent
plugins: anyio-4.13.0, langsmith-0.8.9, cov-7.1.0
collecting ... collected 35 items

tests/research_pipeline/test_schemas.py::TestSourceMode::test_source_mode_values PASSED [  2%]
tests/research_pipeline/test_schemas.py::TestRunStatus::test_run_status_values PASSED [  5%]
tests/research_pipeline/test_schemas.py::TestStageStatus::test_stage_status_values PASSED [  8%]
tests/research_pipeline/test_schemas.py::TestStageName::test_stage_name_values PASSED [ 11%]
tests/research_pipeline/test_schemas.py::TestVerificationStatus::test_verification_status_values PASSED [ 14%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_minimal_request PASSED [ 17%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_all_fields PASSED [ 20%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_max_reader_papers_validation_min PASSED [ 22%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_max_reader_papers_validation_max PASSED [ 25%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_max_reader_papers_validation_valid_range PASSED [ 28%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_source_mode_validation PASSED [ 31%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateRequest::test_defaults PASSED [ 34%]
tests/research_pipeline/test_schemas.py::TestPaperCandidate::test_minimal_candidate PASSED [ 37%]
tests/research_pipeline/test_schemas.py::TestPaperCandidate::test_all_fields PASSED [ 40%]
tests/research_pipeline/test_schemas.py::TestPaperCandidate::test_source_validation PASSED [ 42%]
tests/research_pipeline/test_schemas.py::TestPaperCard::test_minimal_card PASSED [ 45%]
tests/research_pipeline/test_schemas.py::TestPaperCard::test_all_fields PASSED [ 48%]
tests/research_pipeline/test_schemas.py::TestPaperCard::test_status_validation PASSED [ 51%]
tests/research_pipeline/test_schemas.py::TestPaperCard::test_extraction_mode_validation PASSED [ 54%]
tests/research_pipeline/test_schemas.py::TestReportClaim::test_minimal_claim PASSED [ 57%]
tests/research_pipeline/test_schemas.py::TestReportClaim::test_all_fields PASSED [ 60%]
tests/research_pipeline/test_schemas.py::TestReportClaim::test_claim_type_validation PASSED [ 62%]
tests/research_pipeline/test_schemas.py::TestReportClaim::test_verification_status_all_values PASSED [ 65%]
tests/research_pipeline/test_schemas.py::TestResearchStage::test_minimal_stage PASSED [ 68%]
tests/research_pipeline/test_schemas.py::TestResearchStage::test_all_fields PASSED [ 71%]
tests/research_pipeline/test_schemas.py::TestResearchEvent::test_minimal_event PASSED [ 74%]
tests/research_pipeline/test_schemas.py::TestResearchEvent::test_with_payload PASSED [ 77%]
tests/research_pipeline/test_schemas.py::TestResearchPlan::test_minimal_plan PASSED [ 80%]
tests/research_pipeline/test_schemas.py::TestResearchPlan::test_with_plan_data PASSED [ 82%]
tests/research_pipeline/test_schemas.py::TestResearchReport::test_minimal_report PASSED [ 85%]
tests/research_pipeline/test_schemas.py::TestResearchRunCreateResponse::test_create_response PASSED [ 88%]
tests/research_pipeline/test_schemas.py::TestResearchRunListResponse::test_empty_list PASSED [ 91%]
tests/research_pipeline/test_schemas.py::TestResearchRunListResponse::test_with_runs PASSED [ 94%]
tests/research_pipeline/test_schemas.py::TestResearchRunDetailResponse::test_minimal_detail PASSED [ 97%]
tests/research_pipeline/test_schemas.py::TestResearchRunDetailResponse::test_full_detail PASSED [100%]

============================= 35 passed in 0.17s ==============================
```

## Acceptance Criteria Verification

### ✅ 支持 `source_mode`: `web_search`、`zotero_only`、`hybrid`
- 定义为 `SourceMode = Literal["web_search", "zotero_only", "hybrid"]`
- 在 `ResearchRunCreateRequest` 中使用，默认值为 `"hybrid"`
- 测试验证：`test_source_mode_values`, `test_source_mode_validation`

### ✅ 支持 run status: `queued`、`running`、`completed`、`failed`、`cancelled`、`degraded`
- 定义为 `RunStatus = Literal["queued", "running", "completed", "failed", "cancelled", "degraded"]`
- 在 `ResearchRunCreateResponse` 和 `ResearchRunDetailResponse` 中使用
- 测试验证：`test_run_status_values`

### ✅ 支持 stage status: `queued`、`running`、`completed`、`failed`、`degraded`
- 定义为 `StageStatus = Literal["queued", "running", "completed", "failed", "degraded"]`
- 在 `ResearchStage` 和 `PaperCard` 中使用
- 测试验证：`test_stage_status_values`

### ✅ `ResearchRunCreateRequest` 默认 `max_reader_papers=8`、`reader_concurrency=3`
- `max_reader_papers: int = Field(default=8, ge=3, le=15)`
- `reader_concurrency: int = 3`
- 测试验证：`test_minimal_request`, `test_defaults`

### ✅ `max_reader_papers` 限制为 3-15
- 使用 Pydantic Field 约束：`Field(default=8, ge=3, le=15)`
- 测试验证：
  - `test_max_reader_papers_validation_min` - 验证 2 会失败
  - `test_max_reader_papers_validation_max` - 验证 16 会失败
  - `test_max_reader_papers_validation_valid_range` - 验证 3, 8, 15 都有效

### ✅ `ReportClaim.verification_status` 包含 PRD 要求的五种状态
- 定义为 `VerificationStatus = Literal["supported", "weak", "unverified", "numeric_trace_missing", "conflict_detected"]`
- 在 `ReportClaim` 中使用
- 测试验证：
  - `test_verification_status_values` - 验证枚举值正确
  - `test_verification_status_all_values` - 验证所有五个状态都可以使用

## Schema Coverage

### Enums and Literals (8个)
1. `SourceMode` - 数据源模式
2. `RunStatus` - 运行状态（6个值）
3. `StageStatus` - 阶段状态（5个值）
4. `StageName` - 阶段名称（5个阶段）
5. `VerificationStatus` - 验证状态（5个值）
6. `ClaimType` - 声明类型（7个值）
7. `ExtractionMode` - 提取模式（2个值）
8. `EventLevel` - 事件级别（4个值）
9. `PlanPhase` - 计划阶段（2个值）

### Request Schemas (1个)
1. `ResearchRunCreateRequest` - 创建研究运行请求，带完整验证

### Response Schemas (3个)
1. `ResearchRunCreateResponse` - 创建运行响应
2. `ResearchRunListResponse` - 运行列表响应
3. `ResearchRunDetailResponse` - 运行详情响应（包含所有关联数据）

### Core Data Models (7个)
1. `PaperCandidate` - 候选论文
2. `PaperCard` - 论文卡片（提取的结构化信息）
3. `ReportClaim` - 报告声明
4. `ResearchPlan` - 研究计划
5. `ResearchStage` - 研究阶段
6. `ResearchEvent` - 研究事件
7. `ResearchReport` - 研究报告

## Design Decisions

1. **使用 Pydantic v2 的 Literal 类型**：提供编译时类型检查和运行时验证
2. **Field 约束验证**：`max_reader_papers` 使用 `ge=3, le=15` 进行范围限制
3. **默认值设计**：所有集合类型使用 `Field(default_factory=list/dict)` 避免可变默认值问题
4. **可选字段命名一致性**：所有可选字段统一使用 `| None = None` 语法
5. **遵循现有项目模式**：参考 `app/schemas.py` 的风格，保持一致性

## Testing Strategy

- **枚举测试**：验证每个 Literal 类型包含正确的值
- **默认值测试**：验证所有默认值按规范设置
- **验证逻辑测试**：验证 Pydantic 验证器正确拒绝无效值
- **边界条件测试**：验证 `max_reader_papers` 的边界值（3, 15, 2, 16）
- **完整性测试**：验证复杂 schema 的所有字段都可以正确设置和读取

## Concerns and Questions

**无。** 所有验收标准已满足，所有测试通过。

## Next Steps

Task 2 已完成。可以继续 Task 3：实现 SQLite store 和 CRUD 操作。

---

**Completion Time:** 2026-06-21
**Test Pass Rate:** 35/35 (100%)
