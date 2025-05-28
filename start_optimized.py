#!/usr/bin/env python3
"""
TTS 优化版启动脚本
自动检测系统配置并启动服务
"""

import os
import sys
import subprocess
from config import (
    get_optimal_concurrent_tasks, 
    DEFAULT_HOST, 
    DEFAULT_PORT,
    ENABLE_DYNAMIC_CONCURRENCY
)

def check_dependencies():
    """检查依赖是否安装"""
    required_packages = [
        'flask',
        'flask_cors', 
        'edge_tts',
        'aiofiles',
        'psutil'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少以下依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装:")
        print("pip install -r requirements_optimized.txt")
        return False
    
    print("✅ 所有依赖已安装")
    return True

def get_system_info():
    """获取系统信息"""
    try:
        import psutil
        
        cpu_count = os.cpu_count()
        memory_gb = psutil.virtual_memory().total // (1024**3)
        
        print(f"🖥️  系统信息:")
        print(f"   CPU核心数: {cpu_count}")
        print(f"   内存大小: {memory_gb} GB")
        
        if ENABLE_DYNAMIC_CONCURRENCY:
            optimal_concurrent = get_optimal_concurrent_tasks()
            print(f"   推荐并发数: {optimal_concurrent}")
            return optimal_concurrent
        else:
            return None
            
    except ImportError:
        print("⚠️  无法获取系统信息，将使用默认配置")
        return None

def create_directories():
    """创建必要的目录"""
    directories = ['static', 'static/audio', 'templates']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 创建目录: {directory}")

def check_port_available(port):
    """检查端口是否可用"""
    import socket
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False

def main():
    """主函数"""
    print("🚀 启动 TTS 优化版服务")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 获取系统信息
    optimal_concurrent = get_system_info()
    
    # 创建必要目录
    create_directories()
    
    # 检查端口
    if not check_port_available(DEFAULT_PORT):
        print(f"⚠️  端口 {DEFAULT_PORT} 已被占用，尝试使用其他端口...")
        for port in range(DEFAULT_PORT + 1, DEFAULT_PORT + 10):
            if check_port_available(port):
                print(f"✅ 使用端口: {port}")
                DEFAULT_PORT = port
                break
        else:
            print("❌ 无法找到可用端口")
            sys.exit(1)
    
    print(f"\n🌐 服务配置:")
    print(f"   地址: http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    if optimal_concurrent:
        print(f"   并发数: {optimal_concurrent}")
    
    print(f"\n📖 使用指南:")
    print(f"   Web界面: http://localhost:{DEFAULT_PORT}")
    print(f"   API文档: 查看 OPTIMIZATION_GUIDE.md")
    print(f"   性能测试: python performance_test.py")
    
    print(f"\n🎯 API端点:")
    print(f"   串行处理: POST /api/batch_tts")
    print(f"   并发处理: POST /api/batch_tts_concurrent")
    print(f"   时间码处理: POST /api/batch_tts_with_timecodes")
    
    print("\n" + "=" * 50)
    print("正在启动服务...")
    
    # 启动应用
    try:
        if optimal_concurrent:
            # 动态设置并发数
            os.environ['MAX_CONCURRENT_TASKS'] = str(optimal_concurrent)
        
        # 导入并启动应用
        from app_optimized import app
        app.run(
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
            debug=True,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 