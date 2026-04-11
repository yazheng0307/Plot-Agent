"""Plot Agent CLI 入口 -- AIGC 面试宝典自动配图工具。"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.pipeline import Pipeline
from src.utils import setup_logging

console = Console()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="开启详细日志")
def cli(verbose: bool):
    """Plot Agent -- AIGC 面试宝典自动配图工具"""
    setup_logging("DEBUG" if verbose else "INFO")


@cli.command()
@click.option("--input", "-i", "input_text", required=True, help="问答内容文本(直接粘贴或用@file.txt读取)")
@click.option("--output", "-o", "output_dir", default="./output", help="输出目录")
def single(input_text: str, output_dir: str):
    """单条模式：处理一条问答并生成配图"""
    console.print(Panel("Plot Agent - 单条模式", style="bold blue"))

    if input_text.startswith("@") and Path(input_text[1:]).is_file():
        input_text = Path(input_text[1:]).read_text(encoding="utf-8")

    pipe = Pipeline(output_dir=output_dir)
    result = pipe.process_single(input_text)

    _display_result(result)


@cli.command()
@click.option("--input", "-i", "input_file", required=True, type=click.Path(exists=True), help="Markdown 文件路径")
@click.option("--output", "-o", "output_dir", default="./output", help="输出目录")
@click.option("--no-resume", is_flag=True, help="不使用断点续传，从头开始处理")
def batch(input_file: str, output_dir: str, no_resume: bool):
    """批量模式：处理整个 Markdown 文件中的所有问答"""
    console.print(Panel("Plot Agent - 批量模式", style="bold blue"))
    console.print(f"输入文件: [cyan]{input_file}[/cyan]")

    pipe = Pipeline(output_dir=output_dir)
    results = pipe.process_batch(input_file, resume=not no_resume)

    _display_summary(results)


def _display_result(result):
    """在终端展示单条处理结果。"""
    console.print()
    console.print(f"[bold]题目:[/bold] {result.item.title}")
    console.print(f"[bold]插图类型:[/bold] {result.analysis.get('illustration_type', 'N/A')}")
    console.print()
    console.print(Panel(result.prompt, title="生成的绘画提示词", border_style="green"))
    console.print()

    img = result.image_result
    if img.status == "completed":
        console.print(f"[green]图片已生成:[/green] {img.local_path}")
    else:
        console.print(f"[red]图片生成失败:[/red] {img.error}")


def _display_summary(results):
    """在终端展示批量处理汇总。"""
    if not results:
        console.print("[yellow]没有需要处理的问答。[/yellow]")
        return

    table = Table(title="处理结果汇总")
    table.add_column("题号", style="cyan", justify="right")
    table.add_column("题目", style="white")
    table.add_column("插图类型", style="magenta")
    table.add_column("状态", justify="center")
    table.add_column("图片路径", style="dim")

    succeeded = 0
    for r in results:
        status = r.image_result.status
        if status == "completed":
            status_text = "[green]成功[/green]"
            succeeded += 1
        else:
            status_text = f"[red]失败: {r.image_result.error or '未知'}[/red]"

        table.add_row(
            str(r.item.index),
            r.item.title[:30],
            r.analysis.get("illustration_type", "N/A"),
            status_text,
            r.image_result.local_path or "-",
        )

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"总计: {len(results)} 条 | "
        f"[green]成功: {succeeded}[/green] | "
        f"[red]失败: {len(results) - succeeded}[/red]"
    )


if __name__ == "__main__":
    cli()
