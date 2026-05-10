#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动代码调试助手 - 基于 DeepSeek R1 (带系统监控与 CPU 限制)
使用方式: python main.py
"""

from agent import DebugAgent
import os
import sys

def main():
    print("\n" + "="*60)
    print("🤖 自动代码调试助手 (DeepSeek R1 驱动 + 系统保护)")
    print("="*60)

    task = input("📝 请输入程序功能描述: ").strip()
    if not task:
        print("❌ 任务描述不能为空")
        return

    output_dir = input("📁 输出目录 (默认 ./output): ").strip()
    if not output_dir:
        output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    lang = input("🔧 编程语言 (python/c/cpp/java, 默认 python): ").strip().lower()
    if not lang:
        lang = "python"
    if lang not in ["python", "c", "cpp", "java"]:
        print(f"不支持的语言: {lang}，将使用 python")
        lang = "python"

    expected = input("🎯 期望输出 (直接回车则只要求不报错): ").strip()

    model_path = input("🧠 DeepSeek R1 模型路径 (默认 ./DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf): ").strip()
    if not model_path:
        model_path = "./DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf"

    # CPU 限制选项
    cpu_threads = input("⚙️ 限制推理线程数 (默认自动: 物理核心数的一半，输入数字如2): ").strip()
    if cpu_threads.isdigit():
        cpu_threads = int(cpu_threads)
    else:
        cpu_threads = None  # 自动取一半

    agent = DebugAgent(
        task=task,
        output_dir=output_dir,
        language=lang,
        expected=expected,
        model_path=model_path,
        max_cpu_threads=cpu_threads
    )
    agent.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 用户中断，退出")
        sys.exit(0)