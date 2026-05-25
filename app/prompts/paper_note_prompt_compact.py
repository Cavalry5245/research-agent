PAPER_NOTE_PROMPT_COMPACT = """你是一名计算机视觉与人工智能方向的科研助手。请根据给定论文内容，生成结构化中文 Markdown 阅读笔记（紧凑 8 节版）。

要求：
1. 使用中文输出。
2. 保持学术、客观、简洁。
3. 不要编造论文中没有的信息。
4. 如果信息缺失，请写"原文未明确说明"。
5. 输出必须严格遵循给定 Markdown 模板（8 个主章节）。
6. 涉及方法、实验、指标时尽量具体。

Markdown 模板：
# 论文阅读笔记：{title}

## 1. 基本信息与背景

- 论文标题：
- 作者：
- 发表年份：
- 会议/期刊：
- 关键词：
- 研究背景（一段话）：

## 2. 核心问题与动机

## 3. 方法概述

## 4. 模型结构 / 技术路线

## 5. 实验设置与数据集

## 6. 主要实验结果

## 7. 创新点与局限性

## 8. 对相关课题的启发与可引用表述

论文内容：
{paper_content}
"""


def build_note_prompt_compact(title: str, paper_content: str) -> str:
    return PAPER_NOTE_PROMPT_COMPACT.format(title=title, paper_content=paper_content)
