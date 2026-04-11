# Plot Agent -- AIGC 面试宝典自动配图工具

基于 GPT-4o + Nano Banana (Grsai API) 的智能配图 Agent，自动为 AIGC/大模型面试问答内容生成技术插图。

## 功能特性

- **智能分析**：GPT-4o 自动理解问答核心概念，推荐最佳插图类型（对比图/架构图/流程图/概念图/隐喻图）
- **专业提示词**：生成适合技术书籍印刷风格的中文绘画提示词
- **自动生图**：通过 Grsai 代理调用 Nano Banana API 生成高质量插图并下载到本地
- **Web 界面**：提供可视化操作页面，支持参数配置、提示词编辑、图片预览
- **批量处理**：支持整个 Markdown 文件批量处理，自动拆分所有问答
- **断点续传**：中断后可从上次处理位置继续，不重复生成

## 快速开始

### 1. 安装依赖

```bash
cd Plot_Agent
pip install -r requirements.txt
```

### 2. 配置 API 密钥

从仓库克隆后，**不要**提交真实的 `config/config.yaml`（已在 `.gitignore` 中忽略）。请执行：

```bash
copy config\config.example.yaml config\config.yaml   # Windows
# 或: cp config/config.example.yaml config/config.yaml # macOS/Linux
```

再编辑 `config/config.yaml`，填入你的 API 密钥：

```yaml
openai:
  api_key: "sk-your-openai-key"
  base_url: "https://api.openai.com/v1"  # 可替换为代理地址

nano_banana:
  api_key: "your-grsai-api-key"
  base_url: "https://grsai.dakka.com.cn"  # 国内直连；海外用 https://api.grsai.com
  model: "nano-banana-pro"                # 可选: nano-banana-pro / nano-banana-2 / nano-banana
```

或通过环境变量设置（优先级更高）：

```bash
export OPENAI_API_KEY="sk-your-openai-key"
export GRSAI_API_KEY="your-grsai-api-key"
# 可选
export OPENAI_BASE_URL="https://your-proxy.com/v1"
export GRSAI_BASE_URL="https://grsai.dakka.com.cn"
```

API Key 获取：前往 [Grsai 控制台](https://grsai.ai/zh/dashboard/api-keys) 创建。

### 3. 运行

**Web 模式（推荐）** -- 启动可视化界面：

```bash
python server.py
# 浏览器打开 http://localhost:8000
```

Web 界面支持：参数在线配置、问答内容粘贴/文件上传、AI 生成的提示词可编辑后再生图、图片预览与下载、历史记录查看。

**单条模式** -- 处理一条问答：

```bash
python main.py single -i "## 1.介绍一下多模态与语言大模型的区别\n\n..."
```

也可以从文件读取内容（文件路径前加 `@`）：

```bash
python main.py single -i @question.txt
```

**批量模式** -- 处理整个 Markdown 文件：

```bash
python main.py batch -i ../01-AI多模态理论基础.md
```

**常用参数**：

```bash
python main.py batch -i input.md -o ./output -v
```

| 参数 | 说明 |
|------|------|
| `-i, --input` | 输入内容/文件路径 |
| `-o, --output` | 输出目录（默认 `./output`） |
| `-v, --verbose` | 开启详细日志 |
| `--no-resume` | 批量模式不使用断点续传 |

## 项目结构

```
Plot_Agent/
├── config/
│   ├── config.yaml            # API 密钥和运行参数
│   └── prompt_templates.yaml  # LLM 系统提示词模板
├── src/
│   ├── __init__.py
│   ├── parser.py              # Markdown 内容解析
│   ├── analyzer.py            # GPT-4o 概念分析
│   ├── prompt_generator.py    # 绘画提示词生成
│   ├── image_generator.py     # Grsai Nano Banana API 调用
│   ├── pipeline.py            # 流程编排 + 断点续传
│   └── utils.py               # 配置加载、日志等工具
├── output/
│   ├── images/                # 生成的插图
│   └── prompts/               # 提示词记录 (JSON)
├── web/
│   └── index.html             # Web 前端单页面
├── main.py                    # CLI 入口
├── server.py                  # Web 服务入口 (FastAPI)
├── requirements.txt
└── Readme.md
```

## 处理流程

```
输入 Markdown ──→ 解析拆分 ──→ GPT-4o 概念分析 ──→ GPT-4o 中文提示词生成
                                                          │
                  保存图片 ←── 轮询等待 ←── Grsai Nano Banana API
                       │
                  输出报告 + JSON 记录
```

## 输出说明

每条问答处理后会在 `output/` 目录生成：

- `images/01_题目名.png` -- 生成的插图
- `prompts/01.json` -- 提示词记录，包含概念分析、中文提示词、图片信息
- `report.json` -- 批量处理汇总报告
- `.progress.json` -- 断点续传进度文件

## 自定义提示词模板

编辑 `config/prompt_templates.yaml` 可以调整：

- `analyzer_system_prompt`：控制概念分析的输出格式和分析维度
- `prompt_generator_system_prompt`：控制绘画提示词的风格、构图、配色等要求

## Grsai API 说明

本项目使用 [Grsai](https://grsai.ai/) 作为 Nano Banana 的 API 代理，支持国内直连。

- 提交任务：`POST /v1/draw/nano-banana`
- 查询结果：`POST /v1/draw/result`
- 支持模型：`nano-banana-pro`、`nano-banana-2`、`nano-banana`
- API 文档：https://grsai.ai/zh/dashboard/documents/nano-banana
