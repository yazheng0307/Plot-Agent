"""通用工具函数：配置加载、日志设置、文件 IO 等。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 缺失时降级为 no-op，不影响纯环境变量场景
    def load_dotenv(*_args, **_kwargs) -> bool:  # type: ignore[misc]
        return False


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

# 项目启动时一次性加载 .env（不覆盖已在系统中设置的同名环境变量）
load_dotenv(PROJECT_ROOT / ".env", override=False)


def load_yaml(filepath: str | Path) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> Dict[str, Any]:
    """加载 config.yaml；.env / 环境变量优先级高于 yaml。

    密钥推荐放在 ``.env`` 中（``OPENAI_API_KEY`` / ``GRSAI_API_KEY``），
    yaml 中的 ``api_key`` 字段可留空。
    """
    cfg = load_yaml(CONFIG_DIR / "config.yaml")
    cfg.setdefault("openai", {})
    cfg.setdefault("nano_banana", {})

    env_openai_key = os.environ.get("OPENAI_API_KEY")
    if env_openai_key:
        cfg["openai"]["api_key"] = env_openai_key

    env_openai_base = os.environ.get("OPENAI_BASE_URL")
    if env_openai_base:
        cfg["openai"]["base_url"] = env_openai_base

    env_nb_key = os.environ.get("GRSAI_API_KEY")
    if env_nb_key:
        cfg["nano_banana"]["api_key"] = env_nb_key

    env_nb_base = os.environ.get("GRSAI_BASE_URL")
    if env_nb_base:
        cfg["nano_banana"]["base_url"] = env_nb_base

    return cfg


def load_prompt_templates() -> Dict[str, str]:
    return load_yaml(CONFIG_DIR / "prompt_templates.yaml")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
