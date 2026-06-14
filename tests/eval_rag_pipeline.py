"""
RAG 评测脚本 - 父子文档架构评测

评测指标:
1. child_hit@k - 子块检索命中率
2. parent_hit@k - 父文档检索命中率
3. citation_page_accuracy - 引用页码准确性
4. answer_pass_rate - 答案正确率（LLM judge）
5. abstain_accuracy - 拒答准确性

使用方法:
    python tests/eval_rag_pipeline.py

依赖:
    - 需要有索引的论文数据
    - 需要配置 LLM API
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_eval_dataset(dataset_path: str) -> dict:
    """加载评测数据集"""
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_page_range(page_range: str | None) -> tuple[int, int] | None:
    """解析页码范围"""
    if not page_range:
        return None
    try:
        if '-' in page_range:
            start, end = page_range.split('-')
            return int(start), int(end)
        else:
            page = int(page_range)
            return page, page
    except (ValueError, IndexError):
        return None


def compute_child_hit_at_k(
    retrieved_chunks: list[dict],
    gold_parent_id: str | None,
    k: int
) -> bool:
    """
    检查 top-k 子块是否命中 gold parent。

    Args:
        retrieved_chunks: 检索到的子块列表
        gold_parent_id: 正确答案所在的父文档 ID
        k: top-k

    Returns:
        是否命中
    """
    if not gold_parent_id:
        return False

    parent_ids = [
        chunk.get('parent_id')
        for chunk in retrieved_chunks[:k]
        if chunk.get('parent_id')
    ]
    return gold_parent_id in parent_ids


def compute_parent_hit_at_k(
    retrieved_chunks: list[dict],
    gold_parent_id: str | None,
    k: int
) -> bool:
    """
    检查回填的父文档是否命中 gold parent。

    这与 child_hit@k 的区别在于：
    - child_hit@k: 子块的 parent_id 是否包含 gold
    - parent_hit@k: 实际回填的父文档是否包含 gold

    在当前实现中，两者应该相同（因为有 parent_id 就一定会回填）
    """
    return compute_child_hit_at_k(retrieved_chunks, gold_parent_id, k)


def compute_citation_accuracy(
    sources: list[dict],
    gold_page_range: str | None
) -> bool:
    """
    检查引用的页码范围是否覆盖 gold page。

    Args:
        sources: QA 返回的 sources 列表
        gold_page_range: 正确答案的页码范围

    Returns:
        是否准确
    """
    if not gold_page_range:
        return False

    gold_range = parse_page_range(gold_page_range)
    if not gold_range:
        return False

    gold_start, gold_end = gold_range

    for source in sources:
        page_range = source.get('page_range')
        if not page_range:
            continue

        source_range = parse_page_range(str(page_range))
        if not source_range:
            continue

        src_start, src_end = source_range

        # 检查是否有交集
        if (src_start <= gold_start <= src_end) or (src_start <= gold_end <= src_end):
            return True
        if (gold_start <= src_start <= gold_end) or (gold_start <= src_end <= gold_end):
            return True

    return False


def evaluate_answer_quality(
    question: str,
    answer: str,
    expected_answer: str,
    answer_type: str,
    llm_client=None
) -> bool:
    """
    使用 LLM judge 评估答案质量。

    当前实现：简单的关键词匹配（占位符）
    TODO: 实现真正的 LLM judge

    Args:
        question: 问题
        answer: 生成的答案
        expected_answer: 期望答案
        answer_type: 答案类型
        llm_client: LLM 客户端（可选）

    Returns:
        是否通过
    """
    # 简单实现：检查答案是否包含期望答案中的关键词
    # 实际应该使用 LLM judge
    if not answer or len(answer.strip()) < 10:
        return False

    # 对于 out_of_scope，检查是否正确拒答
    if answer_type == 'out_of_scope':
        abstain_keywords = ['未明确说明', '未提及', '没有说明', '未在论文', '不在论文']
        return any(kw in answer for kw in abstain_keywords)

    # 其他类型：简单关键词匹配（占位符）
    # TODO: 实现 LLM-based semantic similarity
    answer_lower = answer.lower()
    expected_lower = expected_answer.lower()

    # 提取期望答案中的关键词（简单分词）
    keywords = [
        word for word in expected_lower.split()
        if len(word) > 2 and word not in ['的', '了', '是', '在', '和', '与']
    ]

    if not keywords:
        return True  # 没有关键词则认为通过

    # 检查至少 30% 的关键词出现在答案中
    matched = sum(1 for kw in keywords if kw in answer_lower)
    return matched / len(keywords) >= 0.3


def compute_abstain_accuracy(answer: str, answer_type: str) -> bool:
    """
    检查超范围问题是否正确拒答。

    Args:
        answer: 生成的答案
        answer_type: 答案类型

    Returns:
        是否准确
    """
    if answer_type != 'out_of_scope':
        return True  # 非超范围问题不需要拒答

    # 检查答案是否包含拒答关键词
    abstain_keywords = [
        '无法判断', '未明确说明', '不在论文', '没有提及',
        '未提及', '未在论文', '论文未', '未说明'
    ]
    return any(kw in answer for kw in abstain_keywords)


def categorize_failure(
    sample: dict,
    child_hit: bool,
    parent_hit: bool,
    citation_acc: bool,
    answer_pass: bool
) -> str:
    """
    归类失败原因。

    Returns:
        失败原因类别
    """
    if not child_hit:
        return "child_retrieval_miss"
    if not parent_hit:
        return "parent_retrieval_miss"
    if not citation_acc:
        return "citation_miss"
    if not answer_pass:
        return "answer_miss"
    return "success"


def run_evaluation(
    dataset: dict,
    vector_store=None,
    parent_store=None,
    embedding_client=None,
    llm_client=None,
    top_k: int = 5
) -> dict:
    """
    运行完整评测（占位符实现）。

    注意：此函数需要真实的 vector_store 和 paper_qa 才能工作。
    当前返回模拟结果用于演示报告格式。

    Args:
        dataset: 评测数据集
        vector_store: 向量存储
        parent_store: 父文档存储
        embedding_client: Embedding 客户端
        llm_client: LLM 客户端
        top_k: top-k 检索

    Returns:
        评测结果字典
    """
    samples = dataset['samples']
    results = {
        'total': len(samples),
        'metrics': {
            'child_hit@5': 0.0,
            'parent_hit@5': 0.0,
            'citation_accuracy': 0.0,
            'answer_pass_rate': 0.0,
            'abstain_accuracy': 0.0,
        },
        'by_answer_type': defaultdict(lambda: {
            'count': 0,
            'child_hit@5': 0,
            'parent_hit@5': 0,
            'citation_accuracy': 0,
            'answer_pass_rate': 0,
        }),
        'failures': [],
        'failure_categories': defaultdict(int),
    }

    logger.info(f"Starting evaluation on {len(samples)} samples")

    # 模拟评测结果（实际需要运行 RAG 系统）
    # TODO: 集成真实的 paper_qa.answer_question

    for sample in samples:
        sample_id = sample['sample_id']
        answer_type = sample['answer_type']

        # 模拟检索和 QA（占位符）
        # 实际应该调用：
        # result = answer_question(
        #     question=sample['question'],
        #     vector_store=vector_store,
        #     embedding_client=embedding_client,
        #     llm_client=llm_client,
        #     paper_id=sample['paper_id'],
        #     top_k=top_k,
        #     parent_store=parent_store
        # )

        # 模拟结果
        simulated_retrieved_chunks = [
            {'parent_id': sample.get('gold_parent_id'), 'page_range': sample.get('gold_page_range')}
        ]
        simulated_answer = sample['expected_answer']
        simulated_sources = [
            {'page_range': sample.get('gold_page_range')}
        ]

        # 计算指标
        child_hit = compute_child_hit_at_k(
            simulated_retrieved_chunks,
            sample.get('gold_parent_id'),
            top_k
        )
        parent_hit = compute_parent_hit_at_k(
            simulated_retrieved_chunks,
            sample.get('gold_parent_id'),
            top_k
        )
        citation_acc = compute_citation_accuracy(
            simulated_sources,
            sample.get('gold_page_range')
        )
        answer_pass = evaluate_answer_quality(
            sample['question'],
            simulated_answer,
            sample['expected_answer'],
            answer_type,
            llm_client
        )
        abstain_acc = compute_abstain_accuracy(simulated_answer, answer_type)

        # 更新总体指标
        if child_hit:
            results['metrics']['child_hit@5'] += 1
        if parent_hit:
            results['metrics']['parent_hit@5'] += 1
        if citation_acc:
            results['metrics']['citation_accuracy'] += 1
        if answer_pass:
            results['metrics']['answer_pass_rate'] += 1
        if abstain_acc:
            results['metrics']['abstain_accuracy'] += 1

        # 更新按类型统计
        type_stats = results['by_answer_type'][answer_type]
        type_stats['count'] += 1
        if child_hit:
            type_stats['child_hit@5'] += 1
        if parent_hit:
            type_stats['parent_hit@5'] += 1
        if citation_acc:
            type_stats['citation_accuracy'] += 1
        if answer_pass:
            type_stats['answer_pass_rate'] += 1

        # 失败归因
        if not (child_hit and parent_hit and citation_acc and answer_pass):
            failure_cat = categorize_failure(
                sample, child_hit, parent_hit, citation_acc, answer_pass
            )
            results['failure_categories'][failure_cat] += 1
            results['failures'].append({
                'sample_id': sample_id,
                'question': sample['question'],
                'category': failure_cat,
                'child_hit': child_hit,
                'parent_hit': parent_hit,
                'citation_acc': citation_acc,
                'answer_pass': answer_pass,
            })

    # 计算百分比
    total = results['total']
    for key in results['metrics']:
        results['metrics'][key] = (results['metrics'][key] / total) * 100

    for answer_type, stats in results['by_answer_type'].items():
        count = stats['count']
        for key in ['child_hit@5', 'parent_hit@5', 'citation_accuracy', 'answer_pass_rate']:
            stats[key] = (stats[key] / count) * 100 if count > 0 else 0.0

    return results


def generate_report(eval_results: dict) -> str:
    """
    生成 Markdown 格式的评测报告。

    Args:
        eval_results: 评测结果

    Returns:
        Markdown 格式报告
    """
    lines = []
    lines.append("# RAG 父子文档架构评测报告")
    lines.append("")
    lines.append(f"**评测时间**: {Path(__file__).stat().st_mtime}")
    lines.append(f"**样本数量**: {eval_results['total']}")
    lines.append("")

    # 总体指标
    lines.append("## 总体指标")
    lines.append("")
    lines.append("| 指标 | 得分 |")
    lines.append("|------|------|")

    metrics = eval_results['metrics']
    lines.append(f"| child_hit@5 | {metrics['child_hit@5']:.1f}% |")
    lines.append(f"| parent_hit@5 | {metrics['parent_hit@5']:.1f}% |")
    lines.append(f"| citation_accuracy | {metrics['citation_accuracy']:.1f}% |")
    lines.append(f"| answer_pass_rate | {metrics['answer_pass_rate']:.1f}% |")
    lines.append(f"| abstain_accuracy | {metrics['abstain_accuracy']:.1f}% |")
    lines.append("")

    # 按类型统计
    lines.append("## 按答案类型统计")
    lines.append("")
    lines.append("| 类型 | 样本数 | child_hit@5 | parent_hit@5 | citation_acc | answer_pass |")
    lines.append("|------|--------|-------------|--------------|--------------|-------------|")

    for answer_type, stats in sorted(eval_results['by_answer_type'].items()):
        lines.append(
            f"| {answer_type} | {stats['count']} | "
            f"{stats['child_hit@5']:.1f}% | "
            f"{stats['parent_hit@5']:.1f}% | "
            f"{stats['citation_accuracy']:.1f}% | "
            f"{stats['answer_pass_rate']:.1f}% |"
        )
    lines.append("")

    # 失败归因
    if eval_results['failure_categories']:
        lines.append("## 失败归因统计")
        lines.append("")
        lines.append("| 失败原因 | 数量 |")
        lines.append("|---------|------|")

        for category, count in sorted(
            eval_results['failure_categories'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"| {category} | {count} |")
        lines.append("")

    # 失败样本详情
    if eval_results['failures']:
        lines.append("## 失败样本详情")
        lines.append("")

        for failure in eval_results['failures'][:10]:  # 最多显示 10 个
            lines.append(f"### {failure['sample_id']}")
            lines.append(f"- **问题**: {failure['question']}")
            lines.append(f"- **失败类别**: {failure['category']}")
            lines.append(f"- **child_hit**: {'✅' if failure['child_hit'] else '❌'}")
            lines.append(f"- **parent_hit**: {'✅' if failure['parent_hit'] else '❌'}")
            lines.append(f"- **citation_acc**: {'✅' if failure['citation_acc'] else '❌'}")
            lines.append(f"- **answer_pass**: {'✅' if failure['answer_pass'] else '❌'}")
            lines.append("")

    return "\n".join(lines)


def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 加载数据集
    dataset_path = 'tests/data/qa_eval_dataset.json'
    if not Path(dataset_path).exists():
        logger.error(f"Dataset not found: {dataset_path}")
        return

    dataset = load_eval_dataset(dataset_path)
    logger.info(f"Loaded dataset: {dataset['dataset_name']} v{dataset['version']}")
    logger.info(f"Total samples: {len(dataset['samples'])}")

    # TODO: 初始化真实的服务
    # from app.services.vector_store import VectorStore
    # from app.services.parent_doc_store import ParentDocumentStore
    # from app.services.embedding_client import EmbeddingClient
    # from app.services.llm_client import LLMClient
    #
    # vector_store = VectorStore()
    # parent_store = ParentDocumentStore()
    # embedding_client = EmbeddingClient()
    # llm_client = LLMClient()

    logger.warning("Running with simulated results (TODO: integrate real RAG system)")

    # 运行评测
    results = run_evaluation(
        dataset=dataset,
        vector_store=None,  # TODO: 传入真实对象
        parent_store=None,
        embedding_client=None,
        llm_client=None,
        top_k=5
    )

    # 生成报告
    report = generate_report(results)

    # 保存报告
    output_path = 'tests/eval_results.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"Report saved to: {output_path}")

    # 打印报告
    print("\n" + "="*80)
    print(report)
    print("="*80)


if __name__ == '__main__':
    main()
