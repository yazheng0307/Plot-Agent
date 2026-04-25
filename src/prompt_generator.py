"""提示词生成器：调用 GPT-4o 将概念分析结果转化为中文绘画提示词。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from openai import OpenAI

from .parser import QAItem
from .utils import load_config, load_prompt_templates

logger = logging.getLogger(__name__)


class PromptGenerator:
    """基于概念分析结果，生成 Nano Banana Pro 的中文绘画提示词。"""

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
        self._system_prompt = templates["prompt_generator_system_prompt"]

    def generate(self, item: QAItem, analysis: Dict[str, Any]) -> str:
        """根据问答内容和分析结果，生成一条中文绘画提示词。"""
        logger.info("生成提示词: [%d] %s", item.index, item.title)

        user_content = (
            f"## 原始问答内容\n{item.full_text}\n\n"
            f"## 概念分析结果\n```json\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n```"
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.7,
        )

        prompt = response.choices[0].message.content.strip()
        prompt = prompt.strip('"').strip("'")
        # 增加：根据下面内容生成一幅适合放在专业书籍中的中文插图：
        prompt = f"根据下面内容生成一幅适合放在专业书籍中的中文插图,扁平化技术插画，现代简约信息图表风格，白色背景，高对比度适合书籍印刷。线条简洁清晰，具有矢量插图质感，中文字体使用宋体，英文字体使用Times New Roman，字号大小为小四号：\n{prompt}"
        logger.debug("生成的绘画提示词: %s", prompt)
        return prompt
