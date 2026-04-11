"""Pipeline 编排：串联解析 -> 分析 -> 提示词生成 -> 图片生成的完整流程。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .analyzer import ContentAnalyzer
from .image_generator import ImageGenerator, ImageResult
from .parser import QAItem, parse_markdown, parse_markdown_file
from .prompt_generator import PromptGenerator
from .utils import ensure_dir, load_config

logger = logging.getLogger(__name__)


def _sanitize_filename(text: str, max_len: int = 40) -> str:
    """将标题文本转为安全的文件名片段。"""
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", text)
    cleaned = re.sub(r'_+', '_', cleaned).strip("_")
    return cleaned[:max_len]


class PipelineResult:
    """单条问答的处理结果。"""

    def __init__(
        self,
        item: QAItem,
        analysis: Dict[str, Any],
        prompt: str,
        image_result: ImageResult,
    ):
        self.item = item
        self.analysis = analysis
        self.prompt = prompt
        self.image_result = image_result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.item.index,
            "title": self.item.title,
            "difficulty": self.item.difficulty,
            "frequency": self.item.frequency,
            "analysis": self.analysis,
            "image_prompt": self.prompt,
            "image": asdict(self.image_result),
        }


class Pipeline:
    """Plot Agent 主流程编排。"""

    def __init__(
        self,
        output_dir: str | Path | None = None,
        openai_client: OpenAI | None = None,
        model: str | None = None,
    ):
        cfg = load_config()
        self._output_dir = Path(
            output_dir or cfg.get("output", {}).get("dir", "./output")
        )
        self._save_prompts = cfg.get("output", {}).get("save_prompts", True)
        self._prompts_dir = ensure_dir(self._output_dir / "prompts")

        self._analyzer = ContentAnalyzer(client=openai_client, model=model)
        self._prompt_gen = PromptGenerator(client=openai_client, model=model)
        self._image_gen = ImageGenerator()

        self._progress_file = self._output_dir / ".progress.json"

    def _load_progress(self) -> set[int]:
        """加载已处理的问答索引（断点续传）。"""
        if self._progress_file.exists():
            try:
                data = json.loads(self._progress_file.read_text(encoding="utf-8"))
                return set(data.get("completed_indices", []))
            except Exception:
                return set()
        return set()

    def _save_progress(self, completed: set[int]) -> None:
        self._progress_file.write_text(
            json.dumps({"completed_indices": sorted(completed)}, indent=2),
            encoding="utf-8",
        )

    def process_single(self, text: str) -> PipelineResult:
        """处理单条问答文本。"""
        items = parse_markdown(text)
        if not items:
            item = QAItem(index=0, title="自定义问答", content=text)
        else:
            item = items[0]

        return self._process_item(item)

    def process_batch(
        self,
        filepath: str | Path,
        resume: bool = True,
    ) -> List[PipelineResult]:
        """批量处理 Markdown 文件中的所有问答。"""
        items = parse_markdown_file(filepath)
        logger.info("解析到 %d 条问答", len(items))

        completed_indices = self._load_progress() if resume else set()
        if completed_indices:
            logger.info("断点续传：跳过已完成的 %d 条", len(completed_indices))

        results: List[PipelineResult] = []
        for i, item in enumerate(items, 1):
            if item.index in completed_indices:
                logger.info("[%d/%d] 跳过已完成: [%d] %s",
                            i, len(items), item.index, item.title)
                continue

            logger.info("[%d/%d] 处理: [%d] %s",
                        i, len(items), item.index, item.title)
            try:
                result = self._process_item(item)
                results.append(result)
                completed_indices.add(item.index)
                self._save_progress(completed_indices)
            except Exception as e:
                logger.error("处理失败 [%d] %s: %s", item.index, item.title, e)

        self._save_report(results)
        return results

    # ------ Web API 使用的两步式方法 ------

    def analyze_item(self, text: str) -> Dict[str, Any]:
        """步骤1：解析问答文本 -> 概念分析 -> 生成提示词（不生图）。

        供 Web 前端调用，返回的 prompt 可被用户编辑后再提交生图。
        """
        items = parse_markdown(text)
        if not items:
            item = QAItem(index=0, title="自定义问答", content=text)
        else:
            item = items[0]

        analysis = self._analyzer.analyze(item)
        prompt = self._prompt_gen.generate(item, analysis)

        return {
            "item": {
                "index": item.index,
                "title": item.title,
                "difficulty": item.difficulty,
                "frequency": item.frequency,
                "content": item.content,
            },
            "analysis": analysis,
            "prompt": prompt,
        }

    def generate_image(
        self,
        prompt: str,
        title: str = "自定义问答",
        index: int = 0,
        analysis: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """步骤2：用(可能已编辑的)提示词生成图片。"""
        filename = f"{index:02d}_{_sanitize_filename(title)}"
        image_result = self._image_gen.generate(prompt=prompt, filename=filename)

        item = QAItem(index=index, title=title)
        if self._save_prompts:
            self._save_prompt_record(
                item, analysis or {}, prompt, image_result
            )

        return {
            "task_id": image_result.task_id,
            "status": image_result.status,
            "image_url": image_result.image_url,
            "local_path": image_result.local_path,
            "bw_local_path": image_result.bw_local_path,
            "error": image_result.error,
        }

    # ------ CLI 使用的一步式方法 ------

    def _process_item(self, item: QAItem) -> PipelineResult:
        """处理单条 QAItem 的完整流程。"""
        analysis = self._analyzer.analyze(item)
        prompt = self._prompt_gen.generate(item, analysis)

        filename = f"{item.index:02d}_{_sanitize_filename(item.title)}"
        image_result = self._image_gen.generate(prompt=prompt, filename=filename)

        if self._save_prompts:
            self._save_prompt_record(item, analysis, prompt, image_result)

        result = PipelineResult(item, analysis, prompt, image_result)
        self._log_result(result)
        return result

    def _save_prompt_record(
        self,
        item: QAItem,
        analysis: Dict[str, Any],
        prompt: str,
        image_result: ImageResult,
    ) -> None:
        """将提示词和分析结果保存为 JSON 文件。"""
        record = {
            "index": item.index,
            "title": item.title,
            "analysis": analysis,
            "image_prompt": prompt,
            "image_task_id": image_result.task_id,
            "image_status": image_result.status,
            "image_url": image_result.image_url,
            "local_path": image_result.local_path,
            "bw_local_path": image_result.bw_local_path,
        }
        outfile = self._prompts_dir / f"{item.index:02d}.json"
        outfile.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("提示词记录已保存: %s", outfile)

    def _save_report(self, results: List[PipelineResult]) -> None:
        """生成批量处理的汇总报告。"""
        if not results:
            return

        report = {
            "total": len(results),
            "succeeded": sum(
                1 for r in results if r.image_result.status == "completed"
            ),
            "failed": sum(
                1 for r in results if r.image_result.status == "failed"
            ),
            "items": [r.to_dict() for r in results],
        }

        report_file = self._output_dir / "report.json"
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("汇总报告已保存: %s", report_file)

    @staticmethod
    def _log_result(result: PipelineResult) -> None:
        status = result.image_result.status
        if status == "completed":
            logger.info(
                "✓ [%d] %s -> %s",
                result.item.index,
                result.item.title,
                result.image_result.local_path,
            )
        else:
            logger.warning(
                "✗ [%d] %s -> %s: %s",
                result.item.index,
                result.item.title,
                status,
                result.image_result.error or "未知",
            )
