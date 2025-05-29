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
    print("🌐 支持跨域访问 (CORS)")
    print("🎵 允许任何域名播放音频")
    print("🎧 支持 MP3 和 WAV 格式输出")
    print("🔧 智能解决 MP3 爆音问题")
    print("=" * 40)
    
    # 检查依赖
    try:
        import aiofiles
        import psutil
        print("✅ 优化依赖已安装")
    except ImportError:
        print("⚠️  正在安装必要依赖...")
        os.system("pip install aiofiles psutil")
    
    # 检查pydub (用于WAV格式转换)
    try:
        import pydub
        print("✅ pydub已安装，支持WAV格式转换")
    except ImportError:
        print("⚠️  pydub未安装，将自动安装以支持WAV格式...")
        os.system("pip install pydub")
    
    # 设置并发数（可通过环境变量调整）
    concurrent_tasks = os.environ.get('MAX_CONCURRENT_TASKS', '10')
    print(f"📊 并发任务数: {concurrent_tasks}")
    print(f"💡 提示: 通过 'export MAX_CONCURRENT_TASKS=8' 可调整并发数")
    print()
    
    print("🌐 启动服务: http://localhost:5020")
    print("🔧 停止服务: 按 Ctrl+C")
    print()
    print("🎵 音频格式支持:")
    print("   • MP3 格式: 兼容性好，文件小")
    print("   • WAV 格式: 无损音质，解决爆音问题")
    print()
    print("📖 API 使用示例:")
    print("   # 生成WAV格式音频")
    print("   curl -X POST http://localhost:5020/api/tts \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"text\":\"你好世界\", \"audio_format\":\"wav\"}'")
    print()
    print("   # 批量生成WAV格式")
    print("   curl -X POST http://localhost:5020/api/batch_tts \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"items\":[{\"text\":\"第一段\"},{\"text\":\"第二段\"}], \"audio_format\":\"wav\"}'")
    print("=" * 40)
    
    # 启动服务
    os.system("python app_replacement.py")

if __name__ == "__main__":
    main() 