#!/usr/bin/env python3
"""
FFmpeg安装助手 - 为TTS服务安装高性能音频处理工具
专为MacBook M3 Max等高性能设备优化
"""

import subprocess
import sys
import platform
import os

def check_ffmpeg():
    """检查ffmpeg是否已安装"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_ffmpeg_macos():
    """在macOS上安装ffmpeg"""
    print("🍎 在macOS上安装FFmpeg...")
    
    # 检查是否安装了Homebrew
    try:
        subprocess.run(['brew', '--version'], capture_output=True, check=True)
        print("✅ 检测到Homebrew")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ 未检测到Homebrew，正在安装...")
        # 安装Homebrew
        install_homebrew_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        os.system(install_homebrew_cmd)
    
    print("📦 正在安装FFmpeg...")
    try:
        result = subprocess.run(['brew', 'install', 'ffmpeg'], check=True)
        print("✅ FFmpeg安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg安装失败: {e}")
        return False

def install_ffmpeg_linux():
    """在Linux上安装ffmpeg"""
    print("🐧 在Linux上安装FFmpeg...")
    
    # 检测Linux发行版
    try:
        # Ubuntu/Debian
        subprocess.run(['apt', '--version'], capture_output=True, check=True)
        print("📦 使用apt安装FFmpeg...")
        result = subprocess.run(['sudo', 'apt', 'update'], check=True)
        result = subprocess.run(['sudo', 'apt', 'install', '-y', 'ffmpeg'], check=True)
        print("✅ FFmpeg安装成功！")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # CentOS/RHEL/Fedora
        subprocess.run(['yum', '--version'], capture_output=True, check=True)
        print("📦 使用yum安装FFmpeg...")
        result = subprocess.run(['sudo', 'yum', 'install', '-y', 'ffmpeg'], check=True)
        print("✅ FFmpeg安装成功！")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # Fedora (dnf)
        subprocess.run(['dnf', '--version'], capture_output=True, check=True)
        print("📦 使用dnf安装FFmpeg...")
        result = subprocess.run(['sudo', 'dnf', 'install', '-y', 'ffmpeg'], check=True)
        print("✅ FFmpeg安装成功！")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    print("❌ 无法自动检测包管理器，请手动安装FFmpeg")
    return False

def install_ffmpeg_windows():
    """Windows安装提示"""
    print("🪟 Windows FFmpeg安装指南:")
    print("1. 访问 https://ffmpeg.org/download.html")
    print("2. 下载Windows版本")
    print("3. 解压到目录，如 C:\\ffmpeg")
    print("4. 添加 C:\\ffmpeg\\bin 到系统PATH环境变量")
    print("5. 重启命令行或IDE")
    print("\n💡 或者使用Chocolatey安装:")
    print("   choco install ffmpeg")
    print("\n💡 或者使用winget安装:")
    print("   winget install ffmpeg")

def main():
    print("=" * 60)
    print("🚀 FFmpeg安装助手 - TTS服务性能优化工具")
    print("=" * 60)
    
    # 检查当前状态
    if check_ffmpeg():
        print("✅ FFmpeg已安装！")
        
        # 显示版本信息
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            version_line = result.stdout.split('\n')[0]
            print(f"📋 {version_line}")
        except:
            pass
        
        print("🚀 您的TTS服务将使用超高性能音频合并模式！")
        return
    
    print("⚠️  FFmpeg未安装")
    print("💡 安装FFmpeg可以大幅提升音频合并性能，特别是处理大量文件时")
    print(f"📊 在MacBook M3 Max上，FFmpeg可将240个文件的合并时间从数十秒减少到几秒")
    print()
    
    # 根据操作系统提供安装选项
    system = platform.system().lower()
    
    if system == 'darwin':  # macOS
        print("🍎 检测到macOS系统")
        user_input = input("是否要自动安装FFmpeg? (y/n): ").lower().strip()
        if user_input in ['y', 'yes', '是']:
            if install_ffmpeg_macos():
                print("\n🎉 安装完成！现在可以享受超高性能音频合并了！")
            else:
                print("\n❌ 安装失败，请查看错误信息或手动安装")
        else:
            print("📋 手动安装命令: brew install ffmpeg")
            
    elif system == 'linux':
        print("🐧 检测到Linux系统")
        user_input = input("是否要自动安装FFmpeg? (y/n): ").lower().strip()
        if user_input in ['y', 'yes', '是']:
            if install_ffmpeg_linux():
                print("\n🎉 安装完成！现在可以享受超高性能音频合并了！")
            else:
                print("\n❌ 安装失败，请查看错误信息或手动安装")
        else:
            print("📋 手动安装命令:")
            print("   Ubuntu/Debian: sudo apt install ffmpeg")
            print("   CentOS/RHEL: sudo yum install ffmpeg")
            print("   Fedora: sudo dnf install ffmpeg")
            
    elif system == 'windows':
        print("🪟 检测到Windows系统")
        install_ffmpeg_windows()
    
    else:
        print(f"❓ 未知操作系统: {system}")
        print("请访问 https://ffmpeg.org/download.html 下载适合的版本")
    
    print("\n" + "=" * 60)
    print("📝 安装完成后，重启TTS服务即可自动启用FFmpeg优化模式")
    print("🚀 预期性能提升：3-10倍音频合并速度，特别是大文件批量处理")
    print("=" * 60)

if __name__ == '__main__':
    main() 