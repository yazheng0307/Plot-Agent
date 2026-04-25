"""ImageGenerator 单独演示脚本。

用法:
    # 1) 直接用脚本里的默认 prompt
    python image_demo.py

    # 2) 命令行传入 prompt
    python image_demo.py -p "一幅扁平化技术插画，展示 Transformer 架构……"

    # 3) 从文件读 prompt
    python image_demo.py -f prompt.txt

    # 4) 指定输出文件名 / 比例 / 分辨率
    python image_demo.py -p "..." -n my_image --aspect 16:9 --size 2K
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.image_generator import ImageGenerator
from src.utils import setup_logging


DEFAULT_PROMPT = (
    "根据下面内容生成一幅适合放在专业书籍中的中文插图：\n"
    "一幅扁平化技术插画，左侧是单模态大模型 LLM，仅有一个文字输入箭头进入 Transformer 方块；"
    "右侧是多模态大模型 MLLM，包含图像编码器、音频编码器，通过投影层连接到中心的语言模型，"
    "箭头展示数据流向。中间用 VS 分隔。现代简约信息图风格，白色背景，蓝橙配色，"
    "标签使用中文（专有名词保留英文），构图比例 16:9，不出现真实人物面孔。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ImageGenerator 独立 Demo：输入提示词 -> 输出绘图结果",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument("-p", "--prompt", help="绘画提示词文本")
    g.add_argument("-f", "--prompt-file", help="从文件读取绘画提示词")

    parser.add_argument(
        "-n", "--name", default="demo",
        help="输出文件名（不含扩展名），默认 demo",
    )
    parser.add_argument("--aspect", help="比例，如 1:1 / 16:9 / 9:16 / 4:3 / 3:4")
    parser.add_argument("--size", help="分辨率，如 1K / 2K / 4K")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    return parser.parse_args()


def resolve_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt
    return DEFAULT_PROMPT


def main() -> int:
    args = parse_args()
    setup_logging("DEBUG" if args.verbose else "INFO")

    prompt = resolve_prompt(args)

    print("=" * 60)
    print("ImageGenerator Demo")
    print("=" * 60)
    print(f"提示词:\n{prompt}\n")

    gen = ImageGenerator()
    result = gen.generate(
        prompt=prompt,
        filename=args.name,
        image_size=args.size,
        aspect_ratio=args.aspect,
    )

    print()
    print("-" * 60)
    print(f"任务 ID    : {result.task_id}")
    print(f"状态       : {result.status}")
    print(f"远程 URL   : {result.image_url or '-'}")
    print(f"本地彩图   : {result.local_path or '-'}")
    print(f"本地黑白图 : {result.bw_local_path or '-'}")
    if result.error:
        print(f"错误       : {result.error}")
    print("-" * 60)

    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
