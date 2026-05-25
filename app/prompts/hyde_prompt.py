HYDE_PROMPT = """你是学术论文写作助手。根据用户的问题，生成一段可能出现在学术论文中的相关段落（150-300 字），用于辅助检索。

要求：
1. 段落应直接回答或与该问题强相关
2. 使用学术、客观的语气
3. 包含可能的方法名、数据集名、指标名等专业术语
4. 不要写"根据问题"或元描述

问题：{query}

可能的论文段落："""


def build_hyde_prompt(query: str) -> str:
    return HYDE_PROMPT.format(query=query)
