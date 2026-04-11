"""Markdown 问答内容解析器，将面试题 Markdown 拆分为结构化的 QAItem 列表。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class QAItem:
    """一条面试问答的结构化表示。"""
    index: int
    title: str
    difficulty: str = ""
    frequency: str = ""
    content: str = ""
    key_points: list = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """返回完整的问答文本（标题 + 正文），用于送入 LLM 分析。"""
        return f"## {self.title}\n\n{self.content}"


_H2_HTML_RE = re.compile(
    r'<h2[^>]*id="[^"]*"[^>]*>\s*(\d+)\.(.*?)</h2>',
    re.IGNORECASE,
)
_H2_MD_RE = re.compile(r'^##\s+(\d+)\.\s*(.+)', re.MULTILINE)
_DIFFICULTY_RE = re.compile(r'【难易度】\s*(.+)')
_FREQUENCY_RE = re.compile(r'【考察频率】\s*(.+)')


def _extract_meta(block: str) -> tuple[str, str]:
    """从问答块中提取难易度和考察频率。"""
    diff_m = _DIFFICULTY_RE.search(block)
    freq_m = _FREQUENCY_RE.search(block)
    return (
        diff_m.group(1).strip() if diff_m else "",
        freq_m.group(1).strip() if freq_m else "",
    )


def _split_by_h2(text: str) -> List[tuple[int, str, str]]:
    """按 h2 标题拆分文本，返回 (题号, 题目, 正文块) 列表。

    同时支持 HTML 格式 <h2> 和 Markdown 格式 ## 的标题。
    """
    markers: list[tuple[int, int, str]] = []  # (start_pos, index, title)

    for m in _H2_HTML_RE.finditer(text):
        markers.append((m.start(), int(m.group(1)), m.group(2).strip()))

    for m in _H2_MD_RE.finditer(text):
        markers.append((m.start(), int(m.group(1)), m.group(2).strip()))

    markers.sort(key=lambda x: x[0])

    if not markers:
        return []

    results = []
    for i, (pos, idx, title) in enumerate(markers):
        header_end = text.index('\n', pos) + 1 if '\n' in text[pos:] else len(text)
        next_pos = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        body = text[header_end:next_pos].strip()
        results.append((idx, title, body))

    return results


def parse_markdown(text: str) -> List[QAItem]:
    """解析 Markdown 文本，返回 QAItem 列表。"""
    items = []
    for idx, title, body in _split_by_h2(text):
        difficulty, frequency = _extract_meta(body)
        items.append(QAItem(
            index=idx,
            title=title,
            difficulty=difficulty,
            frequency=frequency,
            content=body,
        ))
    return items


def parse_markdown_file(filepath: str | Path) -> List[QAItem]:
    """解析 Markdown 文件，返回 QAItem 列表。"""
    path = Path(filepath)
    text = path.read_text(encoding="utf-8")
    return parse_markdown(text)
