"""
Plot Agent 接口连通性测试脚本
测试1: 大模型 API (豆包/OpenAI 兼容接口)
测试2: Grsai Nano Banana 绘画 API
"""

import time
import yaml
import httpx
from openai import OpenAI


def load_cfg():
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# 测试1: 大模型对话
# ============================================================
def test_llm():
    print("=" * 50)
    print("测试1: 大模型 API 连通性")
    print("=" * 50)

    cfg = load_cfg()["openai"]
    print(f"  模型:     {cfg['model']}")
    print(f"  Base URL: {cfg['base_url']}")
    print()

    client = OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
    )

    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": "你是一个AI助手，请简短回答。"},
                {"role": "user", "content": "用一句话解释什么是Transformer架构"},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        content = response.choices[0].message.content
        print(f"  [成功] 大模型返回:\n  {content}")
        print()
        return True
    except Exception as e:
        print(f"  [失败] 错误: {e}")
        print()
        return False


# ============================================================
# 测试2: Grsai Nano Banana 绘画
# ============================================================
def test_draw():
    print("=" * 50)
    print("测试2: Grsai Nano Banana 绘画 API")
    print("=" * 50)

    cfg = load_cfg()["nano_banana"]
    print(f"  模型:     {cfg['model']}")
    print(f"  Base URL: {cfg['base_url']}")
    print(f"  尺寸:     {cfg.get('image_size', '2K')}")
    print(f"  比例:     {cfg.get('aspect_ratio', '4:3')}")
    print()

    base_url = cfg["base_url"].rstrip("/")
    headers = {
        "Authorization": "Bearer " + cfg["api_key"],
        "Content-Type": "application/json",
    }

    # 步骤1: 提交任务
    print("  [1/3] 提交绘画任务...")
    payload = {
        "model": cfg["model"],
        "prompt": "一幅扁平化技术插画，左侧是一个简单的Transformer方块标注LLM，只处理文字；右侧是多模态架构标注MLLM，包含图像编码器、音频编码器通过投影层连接到中心语言模型，箭头展示数据流向，现代简约风格，白色背景，蓝橙配色",
        "aspectRatio": cfg.get("aspect_ratio", "4:3"),
        "imageSize": cfg.get("image_size", "2K"),
        "urls": [],
        "webHook": "-1",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                base_url + "/v1/draw/nano-banana",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("id") or (data.get("data") or {}).get("id")
        if not task_id:
            print(f"  [失败] 未返回任务ID: {data}")
            return False
        print(f"  [成功] 任务ID: {task_id}")
    except Exception as e:
        print(f"  [失败] 提交任务出错: {e}")
        return False

    # 步骤2: 轮询结果
    print("  [2/3] 轮询等待结果...")
    poll_interval = cfg.get("poll_interval", 3)
    max_wait = cfg.get("max_poll_time", 120)
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    base_url + "/v1/draw/result",
                    json={"id": task_id},
                    headers=headers,
                )
                resp.raise_for_status()
                result = resp.json()

            inner = result.get("data") or result
            progress = inner.get("progress", 0)
            status = inner.get("status", "unknown")
            print(f"        进度: {progress}% | 状态: {status} | 耗时: {elapsed}s")

            if progress == 100 or status == "succeeded":
                results = inner.get("results", [])
                if results:
                    image_url = results[0].get("url", "")
                    print(f"  [成功] 图片URL: {image_url}")

                    # 步骤3: 下载图片
                    print("  [3/3] 下载图片...")
                    with httpx.Client(timeout=60, follow_redirects=True) as client:
                        img_resp = client.get(image_url)
                        img_resp.raise_for_status()
                        out_path = "output/images/test_demo.png"
                        with open(out_path, "wb") as f:
                            f.write(img_resp.content)
                        print(f"  [成功] 图片已保存: {out_path}")
                    return True
                else:
                    print("  [失败] 任务完成但无图片URL")
                    return False

            if status == "failed":
                reason = inner.get("failure_reason") or inner.get("error") or "未知"
                print(f"  [失败] 生成失败: {reason}")
                return False

        except Exception as e:
            print(f"        轮询异常: {e}")

    print(f"  [失败] 超时 ({max_wait}s)")
    return False


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print()
    print("Plot Agent - 接口连通性测试")
    print()

    llm_ok = test_llm()
    draw_ok = test_draw()

    print()
    print("=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"  大模型 API:  {'通过' if llm_ok else '失败'}")
    print(f"  绘画 API:    {'通过' if draw_ok else '失败'}")
    print()

    if llm_ok and draw_ok:
        print("全部通过! 可以正常使用 Plot Agent。")
    else:
        print("存在失败项，请检查 config/config.yaml 中的 API Key 和网络连接。")
    print()
