"""内容分析器：调用 GPT-4o 分析问答的核心概念并推荐插图类型。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from openai import OpenAI

from .parser import QAItem
from .utils import load_config, load_prompt_templates

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """使用 LLM 分析面试问答内容，提取核心概念并推荐插图类型。"""

    def __init__(self, client: OpenAI | None = None, model: str | None = None):
        cfg = load_config()
        openai_cfg = cfg["openai"]

        if client is None:
            self._client = OpenAI(
                api_key=openai_cfg["api_key"],
                base_url=openai_cfg.get("base_url"),
            )
        else:
            self._client = client

        self._model = model or openai_cfg.get("model", "gpt-4o")
        templates = load_prompt_templates()
        self._system_prompt = templates["analyzer_system_prompt"]

    def analyze(self, item: QAItem) -> Dict[str, Any]:
        """分析单条问答，返回结构化的分析结果 dict。

        返回示例:
            {
                "core_concepts": ["LLM", "MLLM", "模态"],
                "concept_relations": "对比",
                "illustration_type": "comparison",
                "visual_elements": ["左侧文本单模态", "右侧多模态架构"],
                "scene_description": "..."
            }
        """
        logger.info("分析问答: [%d] %s", item.index, item.title)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": item.full_text},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        logger.debug("LLM 分析原始输出: %s", raw)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM 输出非法 JSON，尝试修复…")
            result = self._fallback_parse(raw)

        return result

    @staticmethod
    def _fallback_parse(raw: str) -> Dict[str, Any]:
        """当 LLM 输出非标准 JSON 时的回退解析。"""
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        return {
            "core_concepts": [],
            "concept_relations": "unknown",
            "illustration_type": "concept_map",
            "visual_elements": [],
            "scene_description": raw[:200],
        }
