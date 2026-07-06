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


def build_query_rewrite_prompt(
    question: str, conversation_summary: str = "", recent_turns: str = ""
) -> str:
    summary = conversation_summary or "(empty)"
    turns = recent_turns or "(empty)"
    return f"""Rewrite the current user question into a standalone retrieval query for paper search.

Rules:
1. Do not answer the question. Only rewrite it.
2. Preserve original technical terms where possible.
3. Use the conversation memory only to resolve references, ellipses, and user intent.
4. Return one concise retrieval query.
5. Keep the user's language: a Chinese question must yield a Chinese retrieval query; do not translate.

=== CONVERSATION SUMMARY ===
{summary}

=== RECENT TURNS ===
{turns}

=== CURRENT QUESTION ===
{question}

Standalone retrieval query:
"""


def build_contextual_qa_prompt(
    question: str,
    rewritten_question: str,
    context: str,
    conversation_summary: str = "",
    recent_turns: str = "",
) -> str:
    summary = conversation_summary or "(empty)"
    turns = recent_turns or "(empty)"
    return f"""You are a rigorous research paper QA assistant.

Evidence rules:
1. Only retrieved paper fragments/context can be used as evidence and factual basis.
2. Conversation memory/history is only for understanding the user's intent and is not factual support.
3. Do not fabricate answers from outside the retrieved paper context.
4. If the retrieved context is insufficient, explicitly say "根据当前论文片段无法判断".
5. Keep the answer clear and useful for researchers.
6. Be specific about methods, experiments, and metrics when the retrieved context supports it.
7. List the supporting fragment identifiers after the answer.

=== CONVERSATION SUMMARY ===
{summary}

=== RECENT TURNS ===
{turns}

=== ORIGINAL USER QUESTION ===
{question}

=== REWRITTEN RETRIEVAL QUESTION ===
{rewritten_question}

=== RETRIEVED PAPER CONTEXT ===
{context}
"""


def build_summary_update_prompt(existing_summary: str, recent_turns: str) -> str:
    summary = existing_summary or "(empty)"
    turns = recent_turns or "(empty)"
    return f"""Update a concise conversation summary for future query rewriting in a paper QA workflow.

Guidelines:
1. Keep durable memory focused on user intent, preferences, workflow needs, unresolved references, and recurring terminology.
2. Do not store paper factual claims as long-term or durable memory unless they are explicitly user preferences or workflow needs.
3. This project requires source-grounded QA, so paper facts should come from retrieved context in each answer, not from memory.
4. Produce a concise summary suitable for future query rewriting.

=== EXISTING SUMMARY ===
{summary}

=== RECENT QA TURNS ===
{turns}

Updated concise summary:
"""
