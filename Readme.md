# Plot Agent

面向 **AIGC / 大模型面试宝典** 等中文技术书籍的 **自动配图工具**：读取问答 Markdown，用大模型分析知识点并生成 **中文绘画提示词**，再经 **Nano Banana** 或 **GPT Image** 系列模型出图，可选 **彩色 + 黑白** 双版本结果，并提供 **Web 界面** 与 **命令行** 两种用法。

**LLM** 使用 OpenAI 兼容接口（官方 OpenAI、阿里云 DashScope、火山方舟等均可，在 `config.yaml` 中配置 `base_url` + `model`）。

**绘图模型** 通过 [Grsai](https://grsai.ai/) 统一代理，支持两族模型：

- `nano-banana-pro` / `nano-banana-2` / `nano-banana`（默认 `nano-banana-pro`）
- `gpt-image-2` / `gpt-image-1.5` / `gpt-image-1`

可在 `config.yaml` 设默认值，也能在 Web 设置面板里随时切换。

---

## 目录

- [功能概览](#功能概览)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [使用方式](#使用方式)
- [项目结构](#项目结构)
- [处理流程](#处理流程)
- [输出与配置](#输出与配置)
- [接口与文档](#接口与文档)
- [常见问题](#常见问题)

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 概念分析 | 提取核心概念、关系，并推荐插图类型（对比 / 架构 / 流程 / 概念图 / 隐喻） |
| 中文提示词 | 面向印刷的中文绘画描述，可在 Web 中修改后再生图 |
| 多模型出图 | 同时支持 Grsai 上的 `nano-banana*` 与 `gpt-image*` 两族模型，按模型名自动切换端点与请求字段 |
| 生图与落盘 | Grsai 异步任务 + 轮询；图片下载到本地（含 CDN 失败重试与 urllib 回退） |
| 黑白版本 | 使用 OpenCV 生成 `*_bw.png`，与彩图同目录保存 |
| Web UI | FastAPI + 单页前端：配置、分析、编辑提示词、预览、历史记录、模型切换 |
| CLI | 单条 / 批量 Markdown，支持断点续传 |
| 连通性测试 | `test_demo.py` 测 LLM + 绘画整链路；`image_demo.py` 单测出图模块 |

---

## 环境要求

- **Python 3.8+**（建议 3.10+）
- 可访问互联网的机器（LLM API + Grsai；下载 CDN 图片时若 DNS 异常见 [常见问题](#常见问题)）

---

## 快速开始

### 1. 克隆与依赖

```bash
git clone <你的仓库地址>
cd Plot_Agent
pip install -r requirements.txt
```

### 2. 配置密钥（推荐放在 `.env`）

密钥统一放在项目根目录的 `.env` 文件中，启动时由 `python-dotenv` 自动加载（已写在 `src/utils.py` 里），**无需手动 `export` / `set`**。

**Windows**

```powershell
copy .env.example .env
notepad .env
```

**macOS / Linux**

```bash
cp .env.example .env
vim .env
```

`.env` 关键字段：

| 变量 | 含义 |
|------|------|
| `OPENAI_API_KEY` | 大模型 API Key |
| `OPENAI_BASE_URL` | 大模型 Base URL（如 DashScope 兼容地址） |
| `GRSAI_API_KEY` | Grsai 绘画 Key |
| `GRSAI_BASE_URL` | Grsai 节点，默认国内 `https://grsai.dakka.com.cn` |

`.env` 已被 `.gitignore` 忽略，不会进版本库。其它非密钥参数（模型名、图片比例、轮询时间等）继续放 `config/config.yaml`。

**优先级**：系统环境变量 > `.env` > `config.yaml`。所以你也可以临时在终端里覆盖：

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:GRSAI_API_KEY = "sk-..."
```

大模型与绘画 Key 需在各自平台申请，例如 [Grsai API Keys](https://grsai.ai/zh/dashboard/api-keys)。

### 3. 验证连通（可选）

```bash
# 同时测 LLM 与绘画链路
python test_demo.py

# 只测出图模块（直接传提示词 -> 出图 -> 落盘彩色 + 黑白）
python image_demo.py -p "一幅扁平化的 Transformer 架构图，白底蓝橙配色"
```

### 4. 启动

**Web（推荐）**

```bash
python server.py
```

浏览器访问：<http://127.0.0.1:8000>

**命令行**

```bash
# 单条（可 @ 文件）
python main.py single -i "问答 Markdown文本"
python main.py single -i @question.md

# 批量
python main.py batch -i ./chapters/01.md -o ./output -v

# 批量从头跑、不用断点续传
python main.py batch -i ./chapters/01.md --no-resume
```

| CLI 参数 | 说明 |
|----------|------|
| `-i, --input` | 内容或 Markdown 路径 |
| `-o, --output` | 输出目录，默认 `./output` |
| `-v, --verbose` | 详细日志 |
| `--no-resume` | 批量模式忽略 `.progress.json` |

---

## 使用方式

- **Web**：左侧贴入或上传问答 → **分析** → 中间栏可改提示词 → **生成图片** → 右侧预览彩图与黑白图、下载、查看历史。右上角齿轮可切换 `nano-banana*` / `gpt-image*` 模型与图片比例 / 尺寸。
- **CLI**：适合脚本化或整本书批量生成；进度写在 `output/.progress.json`。
- **`image_demo.py`**：只跑出图模块，最适合调 prompt 或对比模型效果。

```bash
# 用 config.yaml 默认模型（nano-banana-pro）
python image_demo.py -p "一幅扁平化的 Transformer 架构图"

# 从文件读 prompt + 自定义文件名 + 自定义比例
python image_demo.py -f my_prompt.txt -n transformer_arch --aspect 16:9
```

---

## 项目结构

```
Plot_Agent/
├── .env.example                # 环境变量模板（可提交）
├── .env                        # 本地密钥（.gitignore，勿提交）
├── config/
│   ├── config.yaml            # 模型 / 比例 / 输出等非敏感配置
│   └── prompt_templates.yaml  # 分析 / 提示词系统模板
├── src/
│   ├── parser.py               # Markdown 解析
│   ├── analyzer.py             # 概念分析（LLM）
│   ├── prompt_generator.py     # 绘画提示词（LLM）
│   ├── image_generator.py      # Grsai 调用 + 下载 + 黑白转换
│   ├── pipeline.py             # 编排、断点续传
│   └── utils.py
├── web/
│   └── index.html              # Web 前端
├── output/                     # 默认输出（建议 .gitignore）
│   ├── images/
│   └── prompts/
├── main.py                     # CLI
├── server.py                   # FastAPI 服务
├── test_demo.py                # 连通性测试（LLM + 绘画）
├── image_demo.py               # 出图模块单独 Demo
├── requirements.txt
└── Readme.md
```

---

## 处理流程

```
问答 Markdown
 → 解析（按 h2 / ## 题号拆分）
    → LLM 概念分析（JSON：概念、关系、插图类型）
    → LLM 生成中文绘画提示词
    → Grsai 提交任务（按模型自动路由 nano-banana / gpt-image 端点）
    → 轮询 /v1/draw/result → 下载彩图
    → OpenCV 转灰度保存 *_bw.png
    → 写入 prompts/*.json（可选 report.json）
```

Web 模式下「分析」与「生图」分离，便于人工改提示词后再出图。

---

## 输出与配置

**`output/images/`**

- `NN_题目标题.png`：彩色原图  
- `NN_题目标题_bw.png`：黑白版（转换失败时可能仅有彩图）

**`output/prompts/NN.json`**

记录题号、分析结果、`image_prompt`、远程 `image_url`、本地路径等。

**`output/report.json`**：仅批量 CLI 汇总。

**自定义画风与结构**：编辑 `config/prompt_templates.yaml` 中的 `analyzer_system_prompt` 与 `prompt_generator_system_prompt`。

---

## 接口与文档

绘画走 [Grsai](https://grsai.ai/) 代理，按模型族走不同提交端点，**轮询接口共用**：

| 模型族 | 提交端点 | payload 关键字段 |
|--------|----------|-----------------|
| `nano-banana*` | `POST /v1/draw/nano-banana` | `model / prompt / aspectRatio / imageSize / urls / webHook` |
| `gpt-image*`   | `POST /v1/draw/completions` | `model / prompt / aspectRatio / urls / webHook / shutProgress` |
| 查询结果（共用） | `POST /v1/draw/result` | `id` → `progress / status / results[].url` |

`webHook="-1"` 表示走轮询模式（接口立即返回任务 id，再用 `/v1/draw/result` 拉结果）。

官方说明：

- Nano Banana：<https://grsai.ai/zh/dashboard/documents/nano-banana>
- GPT Image：<https://grsai.ai/zh/dashboard/documents/gpt-image>

支持模型（以 Grsai 控制台为准）：

- Nano Banana：`nano-banana-pro` / `nano-banana-2` / `nano-banana`
- GPT Image：`gpt-image-2` / `gpt-image-1.5` / `gpt-image-1`

**关于参数差异**：

- `imageSize`（`1K / 2K / 4K`）只对 nano-banana 系列生效，gpt-image 系列**会被忽略**。
- `aspectRatio` 两族都支持；gpt-image 可选项更多（含 `21:9 / 9:21 / 5:4` 等长宽比）。

代码内的 `ImageGenerator.generate()` 还提供 `model=` 形参，可以**单次覆盖** `config.yaml` 的默认模型，例如：

```python
from src.image_generator import ImageGenerator

gen = ImageGenerator()
result = gen.generate(
    prompt="一幅扁平化的多模态架构图，白底蓝橙配色",
    filename="demo_gpt2",
    model="gpt-image-2",
    aspect_ratio="16:9",
)
```

---

## 常见问题

**1. 任务显示成功，但服务端报「下载失败」或 `getaddrinfo failed`**

Grsai 返回的图片 URL 常指向海外 CDN。若本机 DNS 或网络无法解析该域名，下载会失败。可尝试：更换 DNS、切换网络、配置系统或 `HTTP_PROXY` / `HTTPS_PROXY`，或稍后重试。代码内已对下载做了多次重试与 `urllib` 回退。

**2. Python 3.8 下类型注解报错**

若使用3.8，请确保依赖版本与运行方式与当前仓库一致；服务端全局变量已避免使用 `X | Y` 运行时求值问题。

**3. 密钥泄露**

密钥统一放 `.env`（已在 `.gitignore` 中）。若不小心把含密钥的 `config.yaml` 或 `.env` 推到公开仓库，请立即在对应平台轮换 Key 并 `git rm --cached` 移除。

---
