"""图片生成器：通过 Grsai 代理调用 Nano Banana API 生成图片并下载到本地。

API 文档: https://grsai.ai/zh/dashboard/documents/nano-banana
提交任务: POST /v1/draw/nano-banana
查询结果: POST /v1/draw/result
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import httpx
import numpy as np

from .utils import load_config, ensure_dir

logger = logging.getLogger(__name__)


@dataclass
class ImageResult:
    """图片生成结果。"""
    task_id: str
    status: str  # "pending" | "processing" | "completed" | "failed"
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    bw_local_path: Optional[str] = None
    error: Optional[str] = None


class ImageGenerator:
    """通过 Grsai API 代理调用 Nano Banana 生成图片。"""

    def __init__(self):
        cfg = load_config()
        nb_cfg = cfg["nano_banana"]

        self._api_key = nb_cfg["api_key"]
        self._base_url = nb_cfg["base_url"].rstrip("/")
        self._model = nb_cfg.get("model", "nano-banana-pro")
        self._image_size = nb_cfg.get("image_size", "2K")
        self._aspect_ratio = nb_cfg.get("aspect_ratio", "4:3")
        self._poll_interval = nb_cfg.get("poll_interval", 3)
        self._max_poll_time = nb_cfg.get("max_poll_time", 120)

        output_cfg = cfg.get("output", {})
        self._output_dir = ensure_dir(
            Path(output_cfg.get("dir", "./output")) / "images"
        )

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        prompt: str,
        filename: str = "image",
        image_size: str | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        """提交图片生成任务、轮询等待完成、下载图片。"""
        task_id = self._submit_task(prompt, image_size, aspect_ratio)
        if not task_id:
            return ImageResult(task_id="", status="failed", error="提交任务失败")

        logger.info("图片生成任务已提交: %s", task_id)

        result = self._poll_until_done(task_id)
        if result.status == "completed" and result.image_url:
            local = self._download_image(result.image_url, filename)
            result.local_path = str(local)
            try:
                bw = self._convert_to_grayscale(local)
                result.bw_local_path = str(bw)
            except Exception as e:
                logger.warning("黑白图转换失败（彩图已保存）: %s", e)

        return result

    def _submit_task(
        self,
        prompt: str,
        image_size: str | None = None,
        aspect_ratio: str | None = None,
    ) -> str | None:
        """向 Grsai 提交 Nano Banana 生成任务，返回任务 ID。"""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "aspectRatio": aspect_ratio or self._aspect_ratio,
            "imageSize": image_size or self._image_size,
            "urls": [],
            "webHook": "-1",
        }

        url = f"{self._base_url}/v1/draw/nano-banana"
        logger.debug("POST %s | model=%s", url, self._model)

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()

            task_id = data.get("id") or (data.get("data") or {}).get("id")
            if task_id:
                return task_id
            else:
                logger.error("API 未返回任务 ID: %s", data)
                return None
        except httpx.HTTPStatusError as e:
            logger.error("HTTP 错误 %d: %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.error("请求异常: %s", e)
            return None

    def _poll_until_done(self, task_id: str) -> ImageResult:
        """轮询任务状态直到完成或超时。

        Grsai 结果查询接口: POST /v1/draw/result
        返回字段: progress (0-100), status, results[].url, failure_reason
        """
        url = f"{self._base_url}/v1/draw/result"
        payload = {"id": task_id}
        elapsed = 0

        while elapsed < self._max_poll_time:
            time.sleep(self._poll_interval)
            elapsed += self._poll_interval

            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.post(url, json=payload, headers=self._headers)
                    resp.raise_for_status()
                    data = resp.json()

                inner = data.get("data") or data
                progress = inner.get("progress", 0)
                status = inner.get("status", "unknown")
                logger.info(
                    "任务 %s 进度: %s%% 状态: %s (%.0fs)",
                    task_id, progress, status, elapsed,
                )

                if progress == 100 or status == "succeeded":
                    results = inner.get("results", [])
                    if results:
                        image_url = results[0].get("url", "")
                        return ImageResult(
                            task_id=task_id,
                            status="completed",
                            image_url=image_url,
                        )
                    return ImageResult(
                        task_id=task_id,
                        status="failed",
                        error="任务完成但未返回图片 URL",
                    )

                if status == "failed":
                    reason = inner.get("failure_reason") or inner.get("error") or "未知错误"
                    return ImageResult(
                        task_id=task_id,
                        status="failed",
                        error=reason,
                    )

            except Exception as e:
                logger.warning("轮询异常 (%.0fs): %s", elapsed, e)

        return ImageResult(
            task_id=task_id,
            status="failed",
            error=f"轮询超时 ({self._max_poll_time}s)",
        )

    def _fetch_url_bytes(self, url: str) -> bytes:
        """从 CDN 拉取图片字节。Grsai 返回的 URL 常指向海外 CDN，国内偶发 DNS 失败(11001)，故做多重试 + urllib 回退。"""
        last_err: Optional[Exception] = None
        delays = (1.0, 3.0, 5.0)
        for attempt, delay in enumerate(delays, start=1):
            try:
                with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": "PlotAgent/1.0"})
                    resp.raise_for_status()
                    return resp.content
            except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
                last_err = e
                errno = getattr(e, "errno", None)
                if errno == 11001 or isinstance(e, httpx.ConnectError):
                    logger.warning(
                        "CDN 下载失败 (httpx 第 %d/%d 次): %s",
                        attempt, len(delays), e,
                    )
                else:
                    logger.warning("CDN 下载失败 (httpx 第 %d/%d 次): %s", attempt, len(delays), e)
                if attempt < len(delays):
                    time.sleep(delay)

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 PlotAgent/1.0"},
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            logger.warning("CDN 下载 urllib 回退也失败: %s", e)

        hint = (
            "无法从 Grsai 返回的图片地址下载文件（常见原因：DNS 无法解析海外域名、公司网络拦截、需代理）。"
            "任务在 Grsai 侧已成功，可稍后重试、换手机热点、或设置系统/HTTP 代理后重试。"
        )
        raise RuntimeError(f"{hint} 最后错误: {last_err}") from last_err

    def _download_image(self, url: str, filename: str) -> Path:
        """下载图片到本地输出目录。"""
        ext = self._guess_extension(url)
        filepath = self._output_dir / f"{filename}{ext}"

        counter = 1
        while filepath.exists():
            filepath = self._output_dir / f"{filename}_{counter}{ext}"
            counter += 1

        logger.info("下载图片: %s -> %s", url, filepath)
        data = self._fetch_url_bytes(url)
        filepath.write_bytes(data)

        return filepath

    @staticmethod
    def _convert_to_grayscale(color_path: Path) -> Path:
        """将彩色图片转换为黑白图片并保存。"""
        bw_path = color_path.parent / (color_path.stem + "_bw" + color_path.suffix)
        img = cv2.imdecode(
            np.frombuffer(color_path.read_bytes(), np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img is None:
            raise ValueError(f"无法解码图片文件: {color_path}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imencode(color_path.suffix, gray)[1].tofile(str(bw_path))
        logger.info("黑白图已保存: %s", bw_path)
        return bw_path

    @staticmethod
    def _guess_extension(url: str) -> str:
        lower = url.lower().split("?")[0]
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            if lower.endswith(ext):
                return ext
        return ".png"
