# Plot Agent

面向 **AIGC / 大模型面试宝典** 等中文技术书籍的 **自动配图工具**：读取问答 Markdown，用大模型分析知识点并生成 **中文绘画提示词**，再经 **Grsai Nano Banana** 出图，可选 **彩色 + 黑白** 双版本落盘，并提供 **Web 界面** 与 **命令行** 两种用法。

**LLM** 使用 OpenAI 兼容接口（官方 OpenAI、阿里云 DashScope、火山方舟等均可，在 `config.yaml` 中配置 `base_url` + `model`）。

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
| 生图与落盘 | Grsai 异步任务 + 轮询；图片下载到本地（含 CDN 失败重试与 urllib 回退） |
| 黑白版本 | 使用 OpenCV 生成 `*_bw.png`，与彩图同目录保存 |
| Web UI | FastAPI + 单页前端：配置、分析、编辑提示词、预览、历史记录 |
| CLI | 单条 / 批量 Markdown，支持断点续传 |
| 连通性测试 | `test_demo.py` 可单独测 LLM 与绘画链路 |

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

### 2. 配置密钥（勿提交仓库）

仓库已忽略 `config/config.yaml`。首次使用请复制示例并编辑：

**Windows**

```powershell
copy config\config.example.yaml config\config.yaml
```

**macOS / Linux**

```bash
cp config/config.example.yaml config/config.yaml
```

在 `config/config.yaml` 中填写 **OpenAI 兼容**的大模型密钥与 **Grsai** 绘画密钥。也可用环境变量覆盖（优先级更高）：

| 变量 | 含义 |
|------|------|
| `OPENAI_API_KEY` | 大模型 API Key |
| `OPENAI_BASE_URL` | 大模型 Base URL（如 DashScope 兼容地址） |
| `GRSAI_API_KEY` | Grsai 绘画 Key |
| `GRSAI_BASE_URL` | Grsai 节点，默认国内 `https://grsai.dakka.com.cn` |

PowerShell 示例：

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:GRSAI_API_KEY = "sk-..."
```

大模型与绘画 Key 需在各自平台申请，例如 [Grsai API Keys](https://grsai.ai/zh/dashboard/api-keys)。

### 3. 验证连通（可选）

```bash
python test_demo.py
```

分别检测 LLM 对话与 Nano Banana 全流程（提交任务 → 轮询 → 下载测试图）。

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

- **Web**：左侧贴入或上传问答 → **分析** → 中间栏可改提示词 → **生成图片** → 右侧预览彩图与黑白图、下载、查看历史。
- **CLI**：适合脚本化或整本书批量生成；进度写在 `output/.progress.json`。

---

## 项目结构

```
Plot_Agent/
├── config/
│   ├── config.example.yaml    # 配置模板（可提交）
│   ├── config.yaml            # 本地密钥（.gitignore，勿提交）
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
├── test_demo.py                # 连通性测试
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
    → Grsai 提交任务 → 轮询 → 下载彩图
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

绘画走 [Grsai](https://grsai.ai/) 统一 Nano Banana 接口（示例）：

- `POST /v1/draw/nano-banana`：创建任务  
- `POST /v1/draw/result`：查询进度与结果  

官方说明：<https://grsai.ai/zh/dashboard/documents/nano-banana>

支持模型示例：`nano-banana-pro`、`nano-banana-2`、`nano-banana`（以控制台为准）。

---

## 常见问题

**1. 任务显示成功，但服务端报「下载失败」或 `getaddrinfo failed`**

Grsai 返回的图片 URL 常指向海外 CDN。若本机 DNS 或网络无法解析该域名，下载会失败。可尝试：更换 DNS、切换网络、配置系统或 `HTTP_PROXY` / `HTTPS_PROXY`，或稍后重试。代码内已对下载做了多次重试与 `urllib` 回退。

**2. Python 3.8 下类型注解报错**

若使用3.8，请确保依赖版本与运行方式与当前仓库一致；服务端全局变量已避免使用 `X | Y` 运行时求值问题。

**3. 密钥泄露**

切勿将 `config/config.yaml` 推送到公开仓库；若已误传，请立即在对应平台轮换 Key。

---
