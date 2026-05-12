# EXECUTION_STATUS.md — ResearchAgent Upgrade Execution Status

## 当前执行环境
- OS/运行方式：WSL
- Python 环境：conda 环境（由用户说明；命令按已激活环境执行）
- 项目根目录：`/home/chase/projects/ResearchAgent`
- 推荐测试命令：`python -m pytest tests -q`

## 本轮进展（2026-05-12 14:41 CST)
- Phase 3 继续补 comparison report 对 semantic evidence mismatch 的可见性：本轮没有改 evaluator 打分逻辑，而是沿着上一轮新增的“section 对齐正确但 snippet 语义不支撑当前 aspect”回归，进一步把这类 failure case 在 comparison Markdown 报告中的展示锁定下来，避免离线报告只显示总体分数、却看不出问题究竟是 section 错位还是语义错配
- `tests/test_comparison_evaluator.py` 新增 `test_build_comparison_report_markdown_includes_semantic_evidence_mismatch_details`，构造一个 `dataset` 维度在 `section_alignment=1.0`、`paper_alignment` 全部正确、但 `evidence_quality_issues=['dataset']` 的 comparison report payload；断言 `build_comparison_report_markdown(...)` 渲染结果会明确输出 `Evidence quality issues: dataset`，同时保持 `Section alignment issues: 无`、`Paper alignment: paper_a=1.000, paper_b=1.000` 与 `Paper alignment issues: 无`，从而让报告读者能直接区分“结构对齐正常”与“证据语义不充分”
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'semantic_evidence_mismatch or includes_semantic_evidence_mismatch_details' -q` → `2 passed, 18 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `20 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `151 passed`

## 本轮进展（2026-05-12 14:06 CST)
- Phase 3 继续细化 comparison evaluator 的证据质量边界：本轮新增一个“section 对齐正确，但 evidence snippet 语义上仍然与 aspect 不匹配”的独立回归，确保 evaluator 会把这种情况归类到 `evidence_quality_issues`，而不会因为 section 命中就误判为高质量证据
- `tests/test_comparison_evaluator.py` 新增 `test_evaluate_comparison_dataset_flags_semantic_evidence_mismatch_separately_from_section_alignment`，构造 `dataset` aspect 的 evidence 全部落在 gold `Experiments` section 中、但 snippet 内容实际只描述 Transformer/CNN 方法的样本；断言结果保持 `section_alignment=1.0`、`section_alignment_issues=[]`，同时单独标记 `evidence_quality_issues=['dataset']` 与 `mean_evidence_quality=0.0`，从而把“结构对齐”和“语义支撑”两层失败继续拆开
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'semantic_evidence_mismatch or distinguishes_missing_evidence_from_section_mismatch' -q` → `2 passed, 18 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `20 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `151 passed`

## 本轮进展（2026-05-12 13:34 CST)
- Phase 3 继续补 `evaluate_comparison.py --generate-live-compare` 的 compare helper 失败契约：本轮新增真实 CLI 子进程回归，验证当 `--compare-batch-script` 指向的 helper 子进程自行非零退出时，主脚本会在失败前透传 helper 的 stdout/stderr，并在错误信息中明确包含 helper exit code，而不会静默吞掉 compare 生成阶段的上下文
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_helper_failure_surfaces_stdout_stderr_and_exit_code`，复用仓库中与真实 parsed metadata 对齐的 comparison seed 样本，临时写出一个会打印 `helper stdout before failure` / `helper stderr before failure` 并以 `SystemExit(7)` 退出的 helper script；随后通过 `sys.executable app/evaluation/scripts/evaluate_comparison.py --generate-live-compare --compare-batch-script ...` 直接跑真实 CLI 子进程，断言 stderr 中同时保留 helper stderr、`compare batch helper failed with exit code 7` 与 `STDOUT/STDERR` 摘要，stdout 保留 helper stdout，且 compare payload / report / markdown 产物都不会被错误生成
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'helper_failure or success_subprocess_with_injection_seam or compare_stage_invalid_json or partial_batch_payload' -q` → `4 passed, 15 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `19 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `149 passed, 1 skipped`

## 本轮进展（2026-05-12 12:52 CST)
- Phase 3 继续把 comparison evaluator 的 `--generate-live-compare` CLI 回归从“metadata 前置失败”推进到“真实 compare-stage 输出损坏”边界：本轮复用了已与仓库真实 parsed metadata 对齐的 comparison seed 样本，并通过新增的 `--compare-batch-script` 注入 seam，让 CLI 子进程实际读取一份故意写坏的 compare batch 文件，从而真实验证主脚本在 compare-stage invalid JSON 时的报错路径，而不再把这类测试误落到 `paper_a_parsed.json` 缺失的前置失败上
- `tests/test_comparison_evaluator.py` 中的 `test_cli_generate_live_compare_surfaces_compare_stage_invalid_json_clearly` 已改为：临时写出一个外部 helper script，它仅向 `--compare-output` 写入非法 JSON，并打印 `wrote invalid compare payload`；随后通过 `sys.executable app/evaluation/scripts/evaluate_comparison.py --generate-live-compare --compare-batch-script ...` 直接跑真实 CLI 子进程，断言 stderr 含 `CompareBatchRunResult` 的 `Invalid JSON` 校验失败，同时 stdout 保留 helper 输出，且不会误报 `论文解析结果不存在` 或 `结构化对比结果解析失败`
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'success_subprocess_with_injection_seam or compare_stage_invalid_json or partial_batch_payload' -q` → `3 passed, 15 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `18 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `149 passed`

## 本轮进展（2026-05-12 12:07 CST)
- Phase 3 继续把 comparison evaluator 的 `--generate-live-compare` 验证往更真实的 CLI 子进程成功路径推进：本轮为 `evaluate_comparison.py` 增加一个显式的 `--compare-batch-script` 注入 seam，使测试可以在真实脚本入口、真实子进程边界上提供受控 compare-batch JSON，而不依赖外部 LLM 或错误地假设 parent pytest 的 monkeypatch 能传进 CLI 子进程
- `app/evaluation/scripts/evaluate_comparison.py` 现支持可选 `--compare-batch-script`；启用后会用当前解释器在仓库根目录下执行该 helper script，由它写出 `CompareBatchRunResult` 到 `--compare-output`，主脚本随后继续复用现有的 `inject_live_compare_predictions(...) -> evaluate_comparison_dataset(...) -> Markdown/JSON report` 闭环。这样既保留了默认真实 compare service 路径，也为后续 CLI 级成功/失败回归提供了稳定注入点
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_success_subprocess_with_injection_seam`，复用仓库中与真实 parsed metadata 对齐的 comparison seed 样本，临时写出 stub compare helper script，再通过 `sys.executable app/evaluation/scripts/evaluate_comparison.py --generate-live-compare --compare-batch-script ...` 直接跑子进程；断言成功态 stdout 仍稳定输出 comparison JSON 报告路径、Markdown 报告路径、live compare payload 路径与 `sample_count`，且最终 evaluator 明确标记 `comparison_source=predicted_comparison`、`uses_structured_summaries=True`
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'success_subprocess_with_injection_seam or compare_stage_invalid_json or partial_batch_payload' -q` → `3 passed, 15 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `18 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `148 passed, 1 skipped`

## 本轮进展（2026-05-12 11:35 CST)
- Phase 3 继续补 comparison evaluator 在 live compare 注入边界上的回归覆盖：本轮新增针对 `inject_live_compare_predictions(...)` 的“数据集样本多于 live compare payload 样本时必须显式失败”回归，防止后续脚本或批处理改动再次引入部分 payload 被静默接受、导致 comparison evaluator 混用真实预测与残余 stub 的风险
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_rejects_partial_batch_payload_clearly`，构造一个两条 comparison dataset + 单条 persisted compare payload 的不一致场景，并断言注入阶段抛出 `Dataset contains sample_ids missing from live compare payload`，且错误信息明确列出缺失样本 `cmp-live-partial-002`；这一步把先前实现过的双向一致性保护继续固定为独立回归，避免未来在 CLI/批量流程重构时被意外弱化
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'partial_batch_payload or compare_stage_invalid_json or generate_live_compare_cli_output_lines' -q` → `3 passed, 15 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `18 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `148 passed, 1 skipped`

## 本轮进展（2026-05-12 10:49 CST)
- Phase 3 继续补 comparison evaluator 对 `--generate-live-compare` CLI 前置失败边界的回归覆盖：本轮新增针对 live compare 子命令在 fixture-only 数据集下的脚本级失败断言，明确当 comparison dataset 的 `paper_ids` 无法在 metadata 目录中找到对应 `*_parsed.json` 时，CLI 必须非零退出并清晰暴露缺失 parsed metadata 文件，而不能把这类前置条件失败误记成 compare-stage JSON 解析错误
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_surfaces_compare_stage_invalid_json_clearly`（名称沿用，但实际锁定的是 metadata prerequisite failure contract），通过 `sys.executable` 直接运行 `app/evaluation/scripts/evaluate_comparison.py --generate-live-compare`，断言 stderr 包含 `论文解析结果不存在` 与 `paper_a_parsed.json`，同时明确不应出现 `结构化对比结果解析失败`；保留现有 `test_generate_live_compare_cli_output_lines`，一起覆盖成功态 stdout 交付契约与失败态 stderr 前置边界
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'compare_stage_invalid_json or generate_live_compare_cli_output_lines' -q` → `2 passed, 15 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `17 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `147 passed, 1 skipped`

## 本轮进展（2026-05-12 09:54 CST)
- Phase 3 继续补强 comparison evaluator 的 CLI/脚本输出契约：本轮新增针对 `evaluate_comparison.py` 成功路径输出行的回归，锁定 live compare 模式下最终应打印 comparison report 路径、Markdown 路径、compare payload 路径与 summary JSON，避免后续脚本重构时静默破坏 cron/CLI 消费方对标准输出的依赖
- `tests/test_comparison_evaluator.py` 新增 `test_generate_live_compare_cli_output_lines`，用受控 `CompareBatchRunResult` 直驱 `live compare payload -> dataset 注入 -> evaluator -> Markdown/JSON report` 流程，并断言成功态下的标准输出文本包含 `Generated comparison evaluation report`、`Generated comparison evaluation markdown`、`Generated live comparison payloads` 与 `sample_count` 摘要；这样在不依赖真实外部 LLM 的前提下，把成功交付时的“产物路径 + 汇总输出”也纳入回归面
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `16 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `147 passed`；附加脚本验证普通 comparison report CLI 仍可成功生成 `app/evaluation/reports/comparison_eval_seed_report.json/.md`

## 本轮进展（2026-05-12 09:05 CST)
- Phase 3 继续把 comparison evaluator 向真实 live compare 成功链路推进：本轮新增“真实 parsed metadata 已对齐时，live compare payload 生成 → dataset 注入 → evaluator/report 消费”的集成回归，但用测试内 stub compare 输出固定住后置契约，避免把外部 LLM/网络波动混入 CLI 成功路径验证
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_with_real_metadata_and_stubbed_llm_generates_live_report`：它复用仓库自带 `comparison_eval_seed.jsonl` 中与 `app/storage/metadata/*_parsed.json` 对齐的真实样本，通过 patch `compare_papers_batch` 内部依赖生成受控 `structured_summaries + comparison`，随后串行验证 `generate_live_compare_predictions(...)`、`inject_live_compare_predictions(...)`、`evaluate_comparison_dataset(...)` 与 Markdown 报告构建；最终断言 `comparison_source=predicted_comparison`、`uses_structured_summaries=True`，并确认 compare batch JSON 中保留 `structured_summaries` 的关键字段
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -k 'stubbed_llm or real_metadata_generates_reports' -q` → `2 passed, 13 deselected`，完整 comparison evaluator 测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `15 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `145 passed, 1 skipped`；附加脚本验证普通 comparison report CLI 仍可成功生成 `app/evaluation/reports/comparison_eval_seed_report.json/.md`

## 本轮进展（2026-05-12 08:28 CST)
- Phase 3 继续把 comparison evaluator 的 CLI 验证边界从“fixture-only 缺 metadata 时明确失败”向前推进到“当 comparison seed dataset 与真实 parsed metadata 已对齐时，离线 comparison report CLI 可以直接成功产出 JSON/Markdown 报告”这一更真实的成功路径
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_with_real_metadata_generates_reports`：测试会从仓库自带 `app/evaluation/datasets/comparison_eval_seed.jsonl` 中筛选出 `paper_ids` 全部在 `app/storage/metadata/*_parsed.json` 中存在的样本，复制到临时数据集后用 `sys.executable` 直接运行 `app/evaluation/scripts/evaluate_comparison.py`，断言 comparison report JSON / Markdown 成功生成，且在未显式开启 `--generate-live-compare` 时继续走 deterministic stub 路径、不会错误依赖 compare batch 产物
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `14 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `144 passed, 1 skipped`；附加脚本验证 `/home/chase/miniconda3/envs/research_agent/bin/python app/evaluation/scripts/evaluate_comparison.py --dataset app/evaluation/datasets/comparison_eval_seed.jsonl --output app/evaluation/reports/comparison_eval_seed_report.json --markdown-output app/evaluation/reports/comparison_eval_seed_report.md` 成功生成 comparison 报告产物

## 本轮进展（2026-05-12 07:55 CST)
- Phase 3 继续补强 live compare CLI 路径的边界说明：本轮没有伪造 metadata fixture 去强行打通 `--generate-live-compare` 成功链路，而是先把该 CLI 在 fixture-only comparison dataset 下的真实失败模式用回归测试固定下来，避免后续把“缺少 parsed metadata 文件导致的前置失败”误报成 compare/evaluator 主流程异常
- `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_reports_missing_metadata_fixture_clearly`，直接用 `sys.executable` 调起 `app/evaluation/scripts/evaluate_comparison.py --generate-live-compare`，断言当数据集只包含 `paper_a` / `paper_b` 这类临时 fixture ID、而 `app/storage/metadata/` 下不存在对应 `*_parsed.json` 时，CLI 会以非零退出并在 stderr 中明确暴露 `论文解析结果不存在` 与缺失文件名 `paper_a_parsed.json`
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `13 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `143 passed, 1 skipped`

## 本轮进展（2026-05-12 07:17 CST）
- Phase 3 继续补强 live compare batch → dataset 注入闭环的完整性校验：本轮针对 `inject_live_compare_predictions(...)` 新增“数据集存在 sample，但 live compare payload 未覆盖该 sample 时必须显式失败”的回归，避免评测脚本在只注入部分预测结果时静默继续，导致后续 report 混入半真半 stub 的 comparison 来源
- `app/evaluation/scripts/evaluate_comparison.py` 现会在写回 dataset 前同时做双向一致性检查：既拒绝 compare batch 中出现数据集不存在的 `sample_id`，也拒绝数据集中存在但 batch payload 缺失的 `sample_id`；只有 dataset 与 live compare payload 一一对应时，才允许把 `predicted_comparison` 注入 `metadata`
- 定向测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` → `13 passed`，全量测试 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests -q` → `143 passed, 1 skipped`

## 本轮进展（2026-05-12 06:37 CST）
- Phase 3 继续补强 live compare → evaluator/report 闭环的可验证性：本轮没有直接跑真实 metadata + LLM 的 CLI 子进程链路，而是优先补齐针对已落盘 live compare payload 的回归，确保一旦 batch compare 结果生成并注入数据集，evaluator 会稳定识别 `predicted_comparison` 来源与 `structured_summaries` 透传状态
- `tests/test_comparison_evaluator.py` 新增两类回归：其一强化 `generate_live_compare_predictions(...)` 的持久化断言，要求写出的 compare batch JSON 保留 `structured_summaries.paper_a.dataset` 等关键字段；其二新增“live compare payload 注入 dataset 后，评测结果必须标记 `comparison_source=predicted_comparison` 且 `uses_structured_summaries=True`”的闭环测试，避免 live payload 已存在时 evaluator 仍误退回 deterministic stub
- 定向测试 `tests/test_comparison_evaluator.py -q` → `12 passed`，全量测试 `tests -q` → `142 passed, 1 skipped`

## 本轮进展（2026-05-12 05:57 CST）
- Phase 3 继续补强 structured comparison evaluator 的报告可解释性：本轮把 paper-level section 对齐结果真正展示到 comparison Markdown 报告中，避免 `paper_alignment` / `paper_alignment_issues` 只存在于 JSON 结构里、人工查看报告时看不到具体哪篇论文错位
- `tests/test_comparison_evaluator.py` 新增 Markdown 回归，要求 failure case 报告明确输出 `paper_a=1.000, paper_b=0.000` 这类 per-paper 对齐分数，以及 `dataset: paper_b` 形式的具体错位论文列表；随后在 `app/evaluation/reporting.py` 的 `build_comparison_report_markdown(...)` 中补齐 `Paper alignment` 与 `Paper alignment issues` 渲染逻辑
- 定向测试 `tests/test_comparison_evaluator.py -q` → `11 passed`，全量测试 `tests -q` → `141 passed, 1 skipped`

## 本轮进展（2026-05-12 05:10 CST）
- Phase 3 继续细化 structured comparison evaluator 的 section 对齐粒度：本轮把 `section_alignment` 从“一个 aspect 只看是否整体命中任一 supporting section”升级为“按论文粒度累计的平均对齐率”，从而能区分“整个 aspect 全部错位”和“仅部分论文证据错位”这两类失败
- `app/evaluation/scripts/evaluate_comparison.py` 新增 `_aspect_paper_alignment(...)`，按 `paper_id` 逐篇检查 evidence section 是否命中该论文在 dataset 中标注的 `supporting_sections`；评测结果新增 `paper_alignment` 与 `paper_alignment_issues`，保留原有 `section_alignment_issues` 的同时，额外暴露“哪个 aspect 错、且具体错了哪篇论文”
- `tests/test_comparison_evaluator.py` 新增 partial alignment 回归，验证同一 comparison aspect 中一篇论文对齐、一篇论文错位时，最终 `section_alignment=0.5`、`paper_alignment={paper_a:1.0,paper_b:0.0}`，而不是被错误压成全对或全错；定向测试 `tests/test_comparison_evaluator.py -q` → `11 passed`，全量测试 `tests -q` → `141 passed, 1 skipped`

## 本轮进展（2026-05-12 04:30 CST）
- Phase 3 继续细化 structured comparison evaluator 的 aspect-level evidence 质量判定：本轮新增 `section_alignment` 指标与 `section_alignment_issues` 字段，用于区分“证据缺失”与“证据非空但 section 未对齐 supporting_sections”两类问题，避免把所有低质量证据都混为 evidence 缺失
- `app/evaluation/scripts/evaluate_comparison.py` 现会对每个 comparison aspect 检查 evidence 所在 section 是否命中该样本 gold `supporting_sections`，并在汇总结果中输出 `section_alignment` / `mean_section_alignment`；`app/evaluation/reporting.py` 的 comparison Markdown 报告同步展示该指标与 section 对齐问题样本
- `tests/test_comparison_evaluator.py` 新增“evidence 非空但 section 错位”回归，验证 evaluator 会保留 `evidence_completeness=1.0`，同时单独标记 `section_alignment_issues`；定向测试 `tests/test_comparison_evaluator.py -q` → `10 passed`，全量测试 `tests -q` → `140 passed, 1 skipped`

## 本轮进展（2026-05-12 03:58 CST）
- Phase 3 继续补强“真实 compare 生成 → dataset 注入 → evaluator/report 落盘”闭环的安全边界：本轮在 live compare payload 注入阶段新增 sample_id 一致性校验，避免 compare batch 结果与 comparison seed dataset 错位时静默写入、导致 evaluator 使用了不匹配或缺失的预测结果
- `app/evaluation/scripts/evaluate_comparison.py` 的 `inject_live_compare_predictions(...)` 现在会先收集 dataset 中全部 `sample_id`，再比对 `CompareBatchRunResult.results[*].sample_id`；若 live compare 输出含有数据集中不存在的 sample，会直接抛出 `ValueError`，阻止静默落盘错误
- `tests/test_comparison_evaluator.py` 新增未知 `sample_id` 回归，验证注入函数在 batch payload 与 dataset 不一致时会明确失败；定向测试 `tests/test_comparison_evaluator.py -q` → `9 passed`，全量测试 `tests -q` → `139 passed, 1 skipped`

## 本轮进展（2026-05-12 03:19 CST）
- Phase 3 继续推进“真实 compare 生成 → evaluator 消费 → report 落盘”闭环：本轮把 live compare batch 输出真正回写进 comparison seed dataset 的 `metadata.predicted_comparison`，让 `evaluate_comparison.py --generate-live-compare` 不再只生成旁路 JSON，而会把真实 compare payload 注入数据集后再走既有 evaluator/report 流程
- `app/evaluation/scripts/evaluate_comparison.py` 新增 `inject_live_compare_predictions(...)`，会读取 `comparison_eval_seed_predictions.json` 中的 `CompareBatchRunResult`，按 `sample_id` 把 `PaperComparisonResult`（含 `structured_summaries`）回填到 dataset 行的 `metadata.predicted_comparison`，随后复用现有 `evaluate_comparison_dataset(...)` 输出正式 report
- `tests/test_comparison_evaluator.py` 新增 dataset metadata 回写回归，验证 live compare batch payload 会正确注入 JSONL 数据集并持久化到磁盘；定向测试 `tests/test_comparison_evaluator.py -q` → `8 passed`，全量测试 `tests -q` → `139 passed`

## 本轮进展（2026-05-12 02:38 CST）
- Phase 3 继续向“真实 compare 生成 → evaluator 消费 → report 落盘”闭环推进：本轮新增 comparison batch 运行结果 schema、批量 compare 服务封装，以及 live compare payload 持久化入口，先把真实 compare 输出的落盘结构固定下来，供下一步真正批量跑 compare service 时直接复用
- `app/schemas.py` 新增 `CompareBatchSampleResult` / `CompareBatchRunResult`；`app/services/paper_compare.py` 新增 `compare_papers_batch(...)` 与 `save_compare_batch_result(...)`，可以按 comparison seed dataset 逐条运行 compare service，并把每个 sample 的 `PaperComparisonResult`（含 `structured_summaries`）统一落成 JSON
- `app/evaluation/scripts/evaluate_comparison.py` 新增 `generate_live_compare_predictions(...)` 与 CLI 参数骨架（`--generate-live-compare` / `--compare-output` / `--metadata-dir`），先把 live compare 产物写入路径与接口固定下来；`tests/test_comparison_evaluator.py` 补充 batch compare 与 live payload 持久化回归，验证 evaluator 旁路的 compare-batch 层已可稳定输出结构化 payload

## 本轮进展（2026-05-12 01:58 CST）
- Phase 3 / comparison evaluator 已从“只会读 deterministic stub”推进到“优先读取真实 compare payload”：`evaluate_comparison.py` 现在会优先消费 `ComparisonEvalSample.metadata.predicted_comparison` 中的结构化对比结果，并显式记录本次评测来自真实 compare 输出还是 deterministic stub
- 评测结果新增 evidence quality 维度：除了 completeness / evidence completeness / paper balance 外，本轮还增加了 `mean_evidence_quality`、`evidence_quality_issues`、`comparison_source`、`uses_structured_summaries`，用于区分“有证据”与“证据存在但与当前 aspect 不对齐”这两类问题
- `tests/test_comparison_evaluator.py` 新增回归：验证 evaluator 会读取 live compare payload、识别 `structured_summaries` 已透传、并对 dataset 维度的错配证据打标；同时更新 comparison markdown report，使失败案例展示 evidence quality、compare 来源和是否使用 structured summaries

## 本轮进展（2026-05-12 01:23 CST）
- Phase 3 / comparison evaluator 继续向真实 compare pipeline 靠拢：`PaperComparisonResult` 现在会保留 `structured_summaries`，让 comparison 评测和后续报告层能直接消费 compare 阶段前的 per-paper 结构化抽取结果，而不必只依赖 deterministic stub 或外部 metadata 注入
- `app/schemas.py` 为 `PaperComparisonResult` 新增 `structured_summaries` 字段；`app/services/paper_compare.py` 在 compare 归一化阶段把 `extract_paper_summaries(...)` 的输出挂回 comparison 结果，形成“抽取结果 + 对比结果”同响应携带的最小闭环
- `tests/test_paper_compare.py` 新增两类回归：其一验证 compare 第二阶段返回非法 JSON 时抛出 `结构化对比结果解析失败`，避免两阶段 pipeline 把 compare-stage 错误误记为 extraction-stage；其二验证 compare 返回对象中会透传 `structured_summaries`，为下一步把 evaluator 接到真实 compare 输出打基础

## 本轮进展（2026-05-12 00:40 CST）
- Phase 3 / Task 3.4 已完成最小 structured comparison evaluation 骨架：新增 comparison evaluator 脚本、Markdown/JSON 报告与定向测试，开始为多论文结构化对比建立 completeness / evidence completeness / paper balance 的离线评测闭环
- `app/evaluation/scripts/evaluate_comparison.py` 新增 deterministic comparison stub 评测流程：支持从 `ComparisonEvalSample.metadata.predicted_comparison` 读取预测结果，或基于 supporting sections 生成离线 stub，对 expected aspects 覆盖率、证据完整度与 paper coverage balance 做聚合统计
- `app/evaluation/reporting.py` 新增 `build_comparison_report_payload(...)` 与 `build_comparison_report_markdown(...)`，可把评测结果整理为 `comparison_eval_seed_report.md`，沉淀 failure-case 与下一步建议
- `app/evaluation/metrics.py` / `app/evaluation/__init__.py` 新增 `load_comparison_samples(...)`，复用 comparison seed dataset 读取逻辑；`tests/test_comparison_evaluator.py` 覆盖完整通过、缺失 aspect/evidence、Markdown 渲染与 CLI 脚本产物生成场景

## 本轮进展（2026-05-12 00:05 CST）
- Phase 3 / Task 3.3 已完成最小 evidence-aware 对齐：当 compare 阶段某个 aspect 未返回 evidence 时，服务侧会基于 per-paper structured summary 的同维度字段与证据自动回填，避免结构化对比存在但 aspect-level evidence 为空
- `app/services/paper_compare.py` 新增 aspect→summary 字段映射与 `_infer_aspect_evidence(...)` 回填逻辑，当前已覆盖 research_problem / method / backbone / dataset / metrics / strengths / limitations / scenarios 八个核心维度
- `tests/test_paper_compare.py` 新增缺失 aspect evidence 的失败基线与回填断言，验证 compare 结果会为 method 维度补齐来自 `PaperStructuredSummary.evidence` 的证据，并同步出现在 Markdown 的“证据摘录”部分

## 本轮进展（2026-05-11 23:32 CST）
- Phase 3 / Task 3.2 已完成最小 per-paper structured extraction 升级：先对每篇论文做结构化字段抽取，再把抽取结果作为 compare prompt 的输入，避免继续直接从原始多论文长文本一次性生成对比
- `app/schemas.py` 新增 `PaperStructuredSummary`，统一承载 research_problem / method / backbone / dataset / metrics / strengths / limitations / scenarios 与 evidence 字段
- `app/prompts/compare_prompt.py` 新增 `EXTRACTION_PROMPT` 与 `build_extraction_prompt(...)`，把“单篇抽取”和“跨论文对比”拆成两阶段 prompt
- `app/services/paper_compare.py` 新增 `extract_paper_summaries(...)`、结构化摘要归一化逻辑与 compare 前 structured summaries 注入，完成 Task 3.2 的最小闭环
- `tests/test_paper_compare.py` 新增单篇结构化抽取、compare 前置 structured extraction 以及 prompt 输入断言，验证两阶段 comparison pipeline 基线

## 本轮进展（2026-05-11 22:52 CST）
- Phase 3 / Task 3.1 已完成最小结构化 comparison schema 升级，`/papers/compare` 不再只返回自由文本 Markdown，而是同时返回结构化 comparison JSON 与 Markdown 双形态
- `app/schemas.py` 新增 `PaperEvidence`、`CompareAspect`、`PaperComparisonResult`，为 research_problem / method / dataset / strengths 等维度的结构化输出打基础
- `app/services/paper_compare.py` 改为要求 LLM 返回结构化 JSON，服务侧负责解析、归一化、补齐 per-paper 缺省值并渲染统一 Markdown 对比报告
- `tests/test_paper_compare.py` 新增结构化 comparison、接口响应与非法 JSON 失败场景测试，验证 Task 3.1 基线闭环

## 阶段总览

| Phase | 名称 | 状态 | 说明 |
|---|---|---|---|
| Phase 0 | 执行前检查与基线冻结 | completed | 已完成现状扫描、前置条件检查与初始状态文档 |
| Phase 1 | P0 评估体系 | completed | 已完成 evaluation schema、seed dataset、retrieval/QA benchmark、baseline report 与文档同步 |
| Phase 2 | P1 检索质量升级 | in_progress | Task 2.1 / 2.2 / 2.3 / 2.4 / 2.5 已完成；下一步可继续把 comparison report 从 deterministic stub 接到真实 vector store / reranker 链路 |
| Phase 3 | P1 多论文结构化 Synthesis 升级 | in_progress | Task 3.1 / 3.2 / 3.3 / 3.4 已完成；下一步可把 comparison evaluator 从 deterministic stub 接到真实 compare pipeline 输出，并继续细化 aspect-level evidence 质量判定 |
| Phase 4 | P2 工程化升级 | pending | 以 job / observability / storage abstraction 为主 |
| Phase 5 | P3 交付增强 | pending | Docker / CI / README / Resume assets |

---

## Phase 0 任务清单

| Task | 状态 | 结果摘要 |
|---|---|---|
| 0.1 项目现状扫描 | completed | 已完成代码、文档、测试、storage、endpoint 基线扫描 |
| 0.2 人工前置条件检查 | completed | 已确认 `.env` 存在且关键字段完整；已有 PDF 与 parsed metadata；已形成阻塞分类 |
| 0.3 建立执行状态文档 | completed | 当前文件已创建 |

---

## Phase 1 任务清单

| Task | 状态 | 结果摘要 |
|---|---|---|
| 1.1 evaluation 目录结构与 schema | completed | 已新增 `app/evaluation/` 模块、基础 schema 与测试 |
| 1.2 最小 benchmark seed dataset | completed | 已基于现有 parsed metadata 生成 QA / comparison seed dataset |
| 1.3 retrieval evaluation 指标 | completed | 已实现 Hit@k / Recall@k / MRR、评估脚本与 seed baseline report JSON |
| 1.4 baseline report | completed | 已生成 `app/evaluation/reports/baseline_report.md` 并沉淀当前离线 baseline |
| 1.5 answer / citation evaluation 骨架 | completed | 已实现 rule-based judge、QA scaffold 与 `qa_eval_seed_report.json` |
| 1.6 文档同步 | completed | 已同步 README、DEVELOPMENT_LOG 与 EXECUTION_STATUS，明确 benchmark 叙事边界 |

---

## Phase 3 任务清单

| Task | 状态 | 结果摘要 |
|---|---|---|
| 3.1 comparison schema | completed | 已新增结构化 comparison schema、服务侧 JSON 解析/Markdown 渲染，以及 `/papers/compare` 结构化响应 |
| 3.2 per-paper structured extraction | completed | 已拆出单篇结构化抽取阶段，compare prompt 改为消费 `PaperStructuredSummary` 聚合结果 |
| 3.3 evidence-aware 对齐 | completed | 已在 compare aspect 缺失证据时，从 per-paper structured summary 的同维度证据自动回填，保证 method 等核心维度具备最小 evidence grounding |
| 3.4 comparison evaluation 骨架 | completed | 已新增 `evaluate_comparison.py`、comparison JSON/Markdown 报告与 completeness / evidence completeness / paper balance 指标闭环 |

---

## 当前基线事实

### 代码与接口
- FastAPI 入口文件：`app/main.py`
- Schema 文件：`app/schemas.py`
- Service 模块目录：`app/services/`
- Prompt 模块目录：`app/prompts/`
- 当前 API endpoint 数量：13

当前 endpoint 列表：
- `GET /health`
- `GET /papers`
- `POST /papers/upload`
- `POST /papers/{paper_id}/parse`
- `POST /papers/{paper_id}/note`
- `GET /papers/{paper_id}/note`
- `GET /papers/{paper_id}/download`
- `POST /papers/{paper_id}/index`
- `GET /papers/{paper_id}/index-status`
- `GET /library/index-status`
- `DELETE /papers/{paper_id}`
- `POST /papers/compare`
- `POST /qa`

### 测试现状
- `tests/` 下当前识别到测试文件：14 个
- 已识别测试文件：
  - `tests/test_chunker.py`
  - `tests/test_embedding_client.py`
  - `tests/test_evaluation_metrics.py`
  - `tests/test_evaluation_schemas.py`
  - `tests/test_llm_client.py`
  - `tests/test_note_generator.py`
  - `tests/test_paper_manager.py`
  - `tests/test_paper_qa.py`
  - `tests/test_paper_qa_closed_client.py`
  - `tests/test_paper_status.py`
  - `tests/test_pdf_parser.py`
  - `tests/test_retrieval.py`
  - `tests/test_seed_dataset_builder.py`
  - `tests/test_streamlit_upload_flow.py`

### 测试验证结果
执行命令：
```bash
python -m pytest tests -q
```

结果：
- 95 passed
- 当前 evaluation 相关定向测试：42 passed
- seed dataset 构建脚本可成功生成：
  - `app/evaluation/datasets/qa_eval_seed.jsonl`
  - `app/evaluation/datasets/comparison_eval_seed.jsonl`
- retrieval baseline 评估脚本可成功生成：
  - `app/evaluation/reports/retrieval_eval_seed_report.json`
- QA scaffold 评估脚本可成功生成：
  - `app/evaluation/reports/qa_eval_seed_report.json`
- baseline Markdown 报告已存在：
  - `app/evaluation/reports/baseline_report.md`

结论：
- 当前项目全量测试通过
- Phase 1 的 1.1 ~ 1.6 已形成可运行 benchmark 骨架与对外叙事材料

### 文档现状
- 已存在：
  - `README.md`
  - `docs/DEVELOPMENT_LOG.md`
  - `docs/RUN_GUIDE.md`
  - `docs/ARCHITECTURE.md`
  - `docs/USAGE.md`
  - `docs/MVP_REQUIREMENTS.md`
  - `docs/HERMES_EXECUTION_PLAN.md`
  - `docs/HUMAN_INPUT_TODO.md`

### 依赖与环境文件
- 已存在：`requirements.txt`
- 未发现：`environment.yml`
- 未发现：`conda.yml`
- 未发现：`pyproject.toml`

说明：
- 当前仓库依赖说明主要依赖 `requirements.txt`
- 虽然实际运行使用 conda 环境，但仓库内暂无 conda 环境锁定文件

### Storage 现状
- `app/storage/papers/`：存在，当前有多份 PDF 样本
- `app/storage/metadata/`：存在，当前有多个 `*_parsed.json`
- `app/storage/notes/`：存在，当前仅 `.gitkeep`
- `app/storage/vector_db/`：存在，当前有 `vector_store.json`

结论：
- 已具备生成 seed dataset 的基础样本
- 已具备 retrieval baseline 评估的最小数据基础

---

## 人工前置条件分类

### 可立即执行
- Phase 0 全部
- Phase 1.1：evaluation schema
- Phase 1.2：seed dataset builder
- Phase 1.3：retrieval evaluation metrics
- Phase 1.4：baseline report
- Phase 1.5：answer / citation evaluation 骨架（先 rule-based / placeholder）

### 需人工确认但可先降级推进
- benchmark 样本是否只使用现有论文，还是后续补充更有代表性的样本
- 是否允许小幅新增依赖（如 `rank-bm25`、reranker 相关包等）
- 是否优先尝试真实 `.env` 模型链路，失败后允许降级到 mock / offline
- 是否允许本地模型 / Ollama 作为兜底方案
- Phase 5 是否只生成交付文件，还是要求真实 Docker / GitHub / 部署验证

### 当前阻塞项
- 无阻塞 Phase 1 后续推进的硬性条件
- 当前需要注意的非阻塞质量问题：
  - `app/evaluation/scripts/evaluate_retrieval.py` 当前已支持 dense / dense_rerank / hybrid / hybrid_rerank 四种 deterministic 对比模式，并可输出 `retrieval_compare_report.json` 与 `retrieval_upgrade_report.md`；但这些结果仍是离线 stub，不代表真实 vector store / reranker 效果
  - `app/evaluation/scripts/evaluate_qa.py` 当前使用 seed expected answer 与 rule-based judge 做离线验证；因此 QA/citation 分数仅证明 scaffold 可运行，不代表真实 LLM 回答质量
  - 当前 comparison report 已可用于沉淀 before/after 叙事；下一步应把 evaluator 接到真实检索链路，并扩充 hard negative / true miss case
- 无新增硬阻塞；已确认 `research_agent` conda 环境（`/home/chase/miniconda3/envs/research_agent/bin/python`）可运行 pytest

---

## 最近验证记录
- `.env` 存在且关键字段完整（仅检查存在与是否非空，未泄露敏感值）
- 当前 endpoint 数量：13
- 当前识别测试文件：14
- 当前存储样本：已有 PDF、parsed metadata、vector store 文件
- 当前全量测试结果：95 passed
- 当前 evaluation 定向验证：42 passed
- 已生成 seed dataset：
  - `app/evaluation/datasets/qa_eval_seed.jsonl`
  - `app/evaluation/datasets/comparison_eval_seed.jsonl`
- 已生成 retrieval baseline report：
  - `app/evaluation/reports/retrieval_eval_seed_report.json`
- 已生成 QA scaffold report：
  - `app/evaluation/reports/qa_eval_seed_report.json`
- 已存在 baseline Markdown 报告：
  - `app/evaluation/reports/baseline_report.md`
- 2026-05-11：已在 `/home/chase/miniconda3/envs/research_agent/bin/python` 下完成 Task 2.1 / 2.2 定向验证：`tests/test_reranker.py tests/test_paper_qa.py` → 10 passed
- 2026-05-11：修复评测脚本测试对 `python` 可执行文件的硬编码，改为使用 `sys.executable` 调用脚本；定向回归 `tests/test_seed_dataset_builder.py tests/test_evaluation_metrics.py tests/test_evaluation_reporting.py tests/test_evaluation_judges.py tests/test_qa_evaluator.py` → 25 passed
- 2026-05-11：全量测试 `tests -q` → 115 passed
- 2026-05-11：Phase 2 / Task 2.3 最小 hybrid retrieval baseline 完成；定向测试 `tests/test_reranker.py tests/test_paper_qa.py tests/test_retrieval.py -q` → 23 passed
- 2026-05-11：Phase 2 / Task 2.5 最小 retrieval evaluator 升级完成；新增 `--mode compare`、`retrieval_compare_report.json`、`retrieval_upgrade_report.md`，定向测试 `tests/test_evaluation_metrics.py tests/test_evaluation_reporting.py -q` → 14 passed；全量测试 `tests -q` → 122 passed
- 2026-05-11：Phase 3 / Task 3.2 最小 per-paper structured extraction 完成；定向测试 `tests/test_paper_compare.py -q` → 6 passed；全量测试 `tests -q` → 128 passed
- 2026-05-12：Phase 3 / Task 3.4 最小 structured comparison evaluator 完成；定向测试 `tests/test_comparison_evaluator.py -q` → 4 passed；脚本生成 `app/evaluation/reports/comparison_eval_seed_report.json` 与 `app/evaluation/reports/comparison_eval_seed_report.md`；全量测试 `tests -q` → 132 passed, 1 skipped

---

## 建议的下一步
1. 把 `evaluate_comparison.py` 接到真实 compare service 的批量输出流程，而不只是读取 dataset metadata 中预埋的 `predicted_comparison`，形成“真实 compare 生成 → evaluator 消费 → report 落盘”的闭环
2. 继续细化 aspect-level evidence quality 规则：除当前的非空/错配外，再区分 section 对齐、paper 覆盖不均衡和 evidence 片段过泛等问题
3. 若继续深挖 Phase 2，可再把 retrieval compare evaluator 从 deterministic stub 接到真实 vector store / reranker 输出
