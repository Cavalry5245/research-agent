QUERY_REWRITE_PROMPT = """你是检索查询优化助手。将用户的问题改写为更适合学术论文检索的查询。

要求：
1. 保留原查询中的关键词和领域术语
2. 把口语化、模糊或过于简短的查询展开为更具体的表达
3. 不要新增原查询没有暗示的领域
4. 输出仅一行改写后的查询，不要解释

原始查询：{query}

改写后的查询："""


def build_query_rewrite_prompt(query: str) -> str:
    return QUERY_REWRITE_PROMPT.format(query=query)
