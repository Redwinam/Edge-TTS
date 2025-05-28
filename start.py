#!/usr/bin/env python3
"""
快速启动 TTS 优化版服务
"""

import os
import sys

def main():
    print("🚀 启动 TTS 优化版服务")
    print("=" * 40)
    print("📍 完全兼容原有 API")
    print("⚡ 智能并发处理")
    print("🎯 自动性能优化")
    print("=" * 40)
    
    # 检查依赖
    try:
        import aiofiles
        import psutil
        print("✅ 优化依赖已安装")
    except ImportError:
        print("⚠️  正在安装必要依赖...")
        os.system("pip install aiofiles psutil")
    
    # 设置并发数（可通过环境变量调整）
    concurrent_tasks = os.environ.get('MAX_CONCURRENT_TASKS', '10')
    print(f"📊 并发任务数: {concurrent_tasks}")
    print(f"💡 提示: 通过 'export MAX_CONCURRENT_TASKS=8' 可调整并发数")
    print()
    
    print("🌐 启动服务: http://localhost:5020")
    print("🔧 停止服务: 按 Ctrl+C")
    print("=" * 40)
    
    # 启动服务
    os.system("python app_replacement.py")

if __name__ == "__main__":
    main() 