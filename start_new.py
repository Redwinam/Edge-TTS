#!/usr/bin/env python3
"""
TTS服务启动脚本 - 重构版
支持Azure TTS和Edge TTS
"""

import os
import sys
import subprocess

def check_dependencies():
    """检查依赖"""
    print("🔍 检查依赖...")
    
    # 基础依赖
    basic_deps = ['flask', 'flask-cors', 'aiohttp', 'aiofiles']
    missing_deps = []
    
    for dep in basic_deps:
        try:
            __import__(dep.replace('-', '_'))
            print(f"✅ {dep}")
        except ImportError:
            missing_deps.append(dep)
            print(f"❌ {dep}")
    
    # Edge TTS依赖
    try:
        import edge_tts
        print("✅ edge-tts")
    except ImportError:
        missing_deps.append('edge-tts')
        print("❌ edge-tts")
    
    # 可选依赖
    try:
        import pydub
        print("✅ pydub (音频处理)")
    except ImportError:
        print("⚠️  pydub未安装，建议安装以获得更好的音频处理功能")
        print("   安装命令: pip install pydub")
    
    # 安装缺失的依赖
    if missing_deps:
        print(f"\n🔧 安装缺失的依赖: {', '.join(missing_deps)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_deps)
            print("✅ 依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ 依赖安装失败: {e}")
            print("请手动安装：pip install " + " ".join(missing_deps))
            return False
    
    return True

def check_azure_config():
    """检查Azure配置"""
    print("\n🔵 检查Azure TTS配置...")
    
    # 检查环境变量
    azure_key = os.environ.get('AZURE_SPEECH_KEY')
    azure_region = os.environ.get('AZURE_SPEECH_REGION')
    
    if azure_key and azure_region:
        print("✅ 发现Azure TTS环境变量配置")
        print(f"   区域: {azure_region}")
        print(f"   密钥: {azure_key[:8]}...")
        return True
    else:
        print("⚠️  未发现Azure TTS环境变量配置")
        print("   将使用配置文件中的默认值")
        print("   如需使用自定义配置，请设置以下环境变量：")
        print("   export AZURE_SPEECH_KEY='your_key'")
        print("   export AZURE_SPEECH_REGION='your_region'")
        return False

def check_ffmpeg():
    """检查FFmpeg"""
    print("\n🔧 检查FFmpeg...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg已安装，将使用超高性能音频合并")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  FFmpeg未安装，将使用pydub合并")
        print("   安装FFmpeg可大幅提升音频合并性能：")
        print("   🍎 macOS: brew install ffmpeg")
        print("   🐧 Ubuntu: sudo apt install ffmpeg")  
        print("   🪟 Windows: https://ffmpeg.org/download.html")
        return False

def show_config_info():
    """显示配置信息"""
    print("\n⚙️  配置选项:")
    print("   🔧 通过环境变量自定义配置：")
    print("   • TTS_ENGINE=azure|edge          (默认引擎)")
    print("   • MAX_CONCURRENT_TASKS=10        (并发任务数)")
    print("   • AZURE_SPEECH_KEY=your_key      (Azure密钥)")
    print("   • AZURE_SPEECH_REGION=eastasia   (Azure区域)")
    print()
    print("   📊 当前配置:")
    print(f"   • 默认引擎: {os.environ.get('TTS_ENGINE', 'azure')}")
    print(f"   • 并发任务: {os.environ.get('MAX_CONCURRENT_TASKS', '10')}")
    print(f"   • Azure区域: {os.environ.get('AZURE_SPEECH_REGION', 'eastasia')}")

def start_server():
    """启动TTS服务器"""
    try:
        # 导入Flask应用
        import app
        from config import FLASK_CONFIG
        
        print("\n" + "=" * 60)
        print("🎵 TTS 智能服务 v3.0 (重构版)")
        print("=" * 60)
        print("✨ 特性:")
        print("   🔵 默认使用Azure TTS")
        print("   🟢 保留Edge TTS作为备选")
        print("   📱 完全兼容原有API")
        print("   ⚡ 智能并发处理")
        print("   🎯 自动故障转移")
        print("   💾 智能缓存系统")
        print("   🏗️  模块化架构设计")
        print("   🌐 支持跨域访问 (CORS)")
        print("   🎵 支持MP3和WAV格式")
        print()
        
        # 显示当前引擎信息
        engine_info = app.tts_service.get_current_engine_info()
        print(f"🎯 当前引擎: {engine_info.get('name', 'unknown')}")
        print(f"📊 可用引擎: {', '.join(engine_info.get('available_engines', []))}")
        print()
        
        print(f"🌐 服务地址: http://localhost:{FLASK_CONFIG['port']}")
        print(f"🎧 音频URL: http://localhost:{FLASK_CONFIG['port']}/static/audio/<filename>")
        print("🛑 停止服务: 按 Ctrl+C")
        print("=" * 60)
        
        # 启动Flask应用
        app.app.run(
            debug=FLASK_CONFIG['debug'], 
            host=FLASK_CONFIG['host'], 
            port=FLASK_CONFIG['port']
        )
        
    except ImportError as e:
        print(f"❌ 启动失败: {e}")
        print("请确保所有模块文件都在正确位置")
        return 1
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
        return 0
    except Exception as e:
        print(f"❌ 服务运行异常: {e}")
        return 1

def main():
    print("🚀 TTS服务启动中...")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请解决后重试")
        return 1
    
    # 检查Azure配置
    check_azure_config()
    
    # 检查FFmpeg
    check_ffmpeg()
    
    # 显示配置信息
    show_config_info()
    
    print("\n" + "=" * 50)
    print("🎵 启动TTS服务...")
    print("🌐 默认地址: http://localhost:5020")
    print("🛑 停止服务: 按 Ctrl+C")
    print("=" * 50)
    
    # 启动服务器
    return start_server()

if __name__ == "__main__":
    sys.exit(main()) 