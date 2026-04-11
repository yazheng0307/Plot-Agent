"""Plot Agent Web 服务 -- FastAPI 后端。"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.pipeline import Pipeline
from src.utils import load_config, ensure_dir, setup_logging, CONFIG_DIR, PROJECT_ROOT

setup_logging("INFO")

app = FastAPI(title="Plot Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = ensure_dir(PROJECT_ROOT / "output")
IMAGES_DIR = ensure_dir(OUTPUT_DIR / "images")
PROMPTS_DIR = ensure_dir(OUTPUT_DIR / "prompts")

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


def _to_local_url(path_str: str) -> Optional[str]:
    """将 local_path（绝对或相对路径）转为可访问的 /output/... URL。"""
    p = Path(path_str)
    if p.is_absolute():
        try:
            rel = p.relative_to(PROJECT_ROOT).as_posix()
            return "/" + rel
        except ValueError:
            return None
    return "/" + p.as_posix()


_pipeline = None  # type: Optional[Pipeline]


def _get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


def _reset_pipeline() -> None:
    global _pipeline
    _pipeline = None


# ---- Pydantic Models ----

class ConfigUpdate(BaseModel):
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    nano_model: Optional[str] = None
    nano_base_url: Optional[str] = None
    image_size: Optional[str] = None
    aspect_ratio: Optional[str] = None


class AnalyzeRequest(BaseModel):
    text: str


class GenerateRequest(BaseModel):
    prompt: str
    title: str = "自定义问答"
    index: int = 0
    analysis: Optional[Dict[str, Any]] = None


# ---- API Routes ----

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = PROJECT_ROOT / "web" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


@app.get("/api/config")
async def get_config():
    cfg = load_config()
    return {
        "openai": {
            "api_key_masked": _mask_key(cfg["openai"].get("api_key", "")),
            "model": cfg["openai"].get("model", "gpt-4o"),
            "base_url": cfg["openai"].get("base_url", ""),
        },
        "nano_banana": {
            "api_key_masked": _mask_key(cfg["nano_banana"].get("api_key", "")),
            "model": cfg["nano_banana"].get("model", "nano-banana-pro"),
            "base_url": cfg["nano_banana"].get("base_url", ""),
            "image_size": cfg["nano_banana"].get("image_size", "2K"),
            "aspect_ratio": cfg["nano_banana"].get("aspect_ratio", "4:3"),
        },
    }


@app.put("/api/config")
async def update_config(update: ConfigUpdate):
    """更新运行时配置（写入 config.yaml 的非敏感字段）。"""
    import yaml

    config_path = CONFIG_DIR / "config.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    if update.openai_model:
        cfg["openai"]["model"] = update.openai_model
    if update.openai_base_url:
        cfg["openai"]["base_url"] = update.openai_base_url
    if update.nano_model:
        cfg["nano_banana"]["model"] = update.nano_model
    if update.nano_base_url:
        cfg["nano_banana"]["base_url"] = update.nano_base_url
    if update.image_size:
        cfg["nano_banana"]["image_size"] = update.image_size
    if update.aspect_ratio:
        cfg["nano_banana"]["aspect_ratio"] = update.aspect_ratio

    config_path.write_text(
        yaml.dump(cfg, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    _reset_pipeline()
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.text.strip():
        raise HTTPException(400, "问答内容不能为空")
    try:
        pipe = _get_pipeline()
        result = pipe.analyze_item(req.text)
        return result
    except Exception as e:
        raise HTTPException(500, f"分析失败: {e}")


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "提示词不能为空")
    try:
        pipe = _get_pipeline()
        result = pipe.generate_image(
            prompt=req.prompt,
            title=req.title,
            index=req.index,
            analysis=req.analysis,
        )
        if result.get("local_path"):
            result["local_url"] = _to_local_url(result["local_path"])
        if result.get("bw_local_path"):
            result["bw_local_url"] = _to_local_url(result["bw_local_path"])
        return result
    except Exception as e:
        raise HTTPException(500, f"生成失败: {e}")


@app.get("/api/history")
async def list_history():
    records = []
    for f in sorted(PROMPTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            thumb = _to_local_url(data["local_path"]) if data.get("local_path") else None
            bw_thumb = _to_local_url(data["bw_local_path"]) if data.get("bw_local_path") else None
            records.append({
                "id": f.stem,
                "index": data.get("index", 0),
                "title": data.get("title", ""),
                "image_prompt": data.get("image_prompt", ""),
                "image_status": data.get("image_status", ""),
                "thumbnail": thumb,
                "bw_thumbnail": bw_thumb,
            })
        except Exception:
            continue
    return {"records": records}


@app.get("/api/history/{record_id}")
async def get_history(record_id: str):
    fpath = PROMPTS_DIR / f"{record_id}.json"
    if not fpath.exists():
        raise HTTPException(404, "记录不存在")
    data = json.loads(fpath.read_text(encoding="utf-8"))
    if data.get("local_path"):
        data["local_url"] = _to_local_url(data["local_path"])
    if data.get("bw_local_path"):
        data["bw_local_url"] = _to_local_url(data["bw_local_path"])
    return data


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
