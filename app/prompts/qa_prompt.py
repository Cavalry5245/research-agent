QA_PROMPT = """你是一个严谨的科研论文问答助手。请只根据给定上下文回答用户问题。

要求：
1. 不要使用上下文之外的知识编造答案。
2. 如果上下文不足，请明确说明"根据当前论文片段无法判断"。
3. 回答应结构清晰，适合科研人员阅读。
4. 涉及方法、实验、指标时要尽量具体。
5. 回答后列出依据片段编号。

用户问题：
{question}

检索到的论文片段：
{context}
"""


def build_qa_prompt(question: str, context: str) -> str:
    return QA_PROMPT.format(question=question, context=context)


CONTEXTUAL_QA_PROMPT = """你是一个严谨的科研论文问答助手。请只根据本轮检索到的论文证据回答用户问题。

会话摘要：
{conversation_summary}

最近对话：
{recent_turns}

用户原始问题：
{question}

用于检索的改写问题：
{rewritten_question}

本轮检索到的论文证据：
{context}

要求：
1. 会话摘要和最近对话只用于理解指代和任务上下文，不能作为论文事实依据。
2. 答案必须来自本轮检索到的论文证据。
3. 如果证据不足，明确说明"根据当前论文片段无法判断"。
4. 如果历史和本轮证据冲突，以本轮证据为准。
5. 回答后列出依据片段编号或来源信息。
"""


def build_contextual_qa_prompt(
    question: str,
    rewritten_question: str,
    context: str,
    conversation_summary: str = "",
    recent_turns: str = "",
) -> str:
    return CONTEXTUAL_QA_PROMPT.format(
        question=question,
        rewritten_question=rewritten_question,
        context=context,
        conversation_summary=conversation_summary or "无",
        recent_turns=recent_turns or "无",
    )


QUERY_REWRITE_PROMPT = """你要把科研论文 QA 对话中的当前问题改写成独立、适合检索的查询。

会话摘要：
{conversation_summary}

最近对话：
{recent_turns}

当前论文范围：
{paper_id}

上一轮改写问题：
{previous_rewritten_question}

当前问题：
{question}

要求：
1. 只补全指代、省略和上下文对象。
2. 不要引入历史中没有出现的新事实。
3. 不要回答问题。
4. 如果当前问题已经独立，保持原意并轻微规范化。
5. 保持用户语言，中文问题输出中文。
6. 只输出改写后的检索问题，不要输出解释。
"""


def build_query_rewrite_prompt(
    question: str,
    conversation_summary: str = "",
    recent_turns: str = "",
    paper_id: str | None = None,
    previous_rewritten_question: str = "",
) -> str:
    return QUERY_REWRITE_PROMPT.format(
        question=question,
        conversation_summary=conversation_summary or "无",
        recent_turns=recent_turns or "无",
        paper_id=paper_id or "全库",
        previous_rewritten_question=previous_rewritten_question or "无",
    )


SUMMARY_UPDATE_PROMPT = """你要更新科研 QA thread 的会话状态摘要。

旧会话状态摘要：
{previous_summary}

最近对话：
{recent_turns}

本轮改写问题：
{rewritten_question}

本轮来源提示：
{source_notes}

要求：
1. 输出一段简洁的会话状态摘要，说明当前讨论主题、被反复指代的对象、用户关注维度和后续追问需要的上下文。
2. 不要把 assistant answer 改写成无来源的长期事实。
3. 不要把无法由来源提示支持的内容写成确定结论。
4. 摘要只服务本会话后续追问，不替代论文检索。
"""


def build_summary_update_prompt(
    previous_summary: str = "",
    recent_turns: str = "",
    rewritten_question: str = "",
    source_notes: str = "",
) -> str:
    return SUMMARY_UPDATE_PROMPT.format(
        previous_summary=previous_summary or "无",
        recent_turns=recent_turns or "无",
        rewritten_question=rewritten_question or "无",
        source_notes=source_notes or "无",
    )
