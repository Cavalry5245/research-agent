# RAG 父子文档架构评测报告

**评测时间**: 1781442079.7424955
**样本数量**: 15

## 总体指标

| 指标 | 得分 |
|------|------|
| child_hit@5 | 86.7% |
| parent_hit@5 | 86.7% |
| citation_accuracy | 86.7% |
| answer_pass_rate | 93.3% |
| abstain_accuracy | 100.0% |

## 按答案类型统计

| 类型 | 样本数 | child_hit@5 | parent_hit@5 | citation_acc | answer_pass |
|------|--------|-------------|--------------|--------------|-------------|
| abstract | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| cross_section | 3 | 100.0% | 100.0% | 100.0% | 100.0% |
| figure | 1 | 100.0% | 100.0% | 100.0% | 100.0% |
| method | 3 | 100.0% | 100.0% | 100.0% | 100.0% |
| out_of_scope | 2 | 0.0% | 0.0% | 0.0% | 50.0% |
| result | 3 | 100.0% | 100.0% | 100.0% | 100.0% |
| table | 1 | 100.0% | 100.0% | 100.0% | 100.0% |

## 失败归因统计

| 失败原因 | 数量 |
|---------|------|
| child_retrieval_miss | 2 |

## 失败样本详情

### qa_011
- **问题**: 该模型的训练时间是多少小时？
- **失败类别**: child_retrieval_miss
- **child_hit**: ❌
- **parent_hit**: ❌
- **citation_acc**: ❌
- **answer_pass**: ✅

### qa_012
- **问题**: 作者团队来自哪个机构？
- **失败类别**: child_retrieval_miss
- **child_hit**: ❌
- **parent_hit**: ❌
- **citation_acc**: ❌
- **answer_pass**: ❌
