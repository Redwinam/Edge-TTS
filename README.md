# TTS 服务项目

🎵 智能语音合成服务，支持 Azure TTS 和 Edge TTS

## 🚀 快速开始

**推荐使用重构版 v3.0：**

```bash
# 安装依赖
pip install -r requirements_new.txt

# 启动服务
python start_new.py
```

详细文档请查看：[README_NEW.md](README_NEW.md)

## 📁 项目结构

### 新版本文件（推荐使用）

- `app.py` - 重构版主应用
- `start_new.py` - 新版启动脚本
- `requirements_new.txt` - 新版依赖
- `README_NEW.md` - 详细使用文档
- `config/` - 配置模块
- `engines/` - TTS 引擎模块
- `services/` - 服务层
- `utils/` - 工具模块

### 实用工具

- `install_ffmpeg.py` - FFmpeg 安装助手（可选，用于音频处理加速）

### 遗留文件（保持兼容性）

- `requirements.txt` - 原版依赖
- `templates/` - 前端模板
- `static/` - 静态文件

## ✨ 主要特性

- 🔵 **Azure TTS 支持** - 默认使用 Azure 认知服务
- 🟢 **Edge TTS 备选** - 自动故障转移
- 🏗️ **模块化设计** - 清晰的架构分离
- ⚡ **智能并发** - 自动选择最优处理模式
- 💾 **智能缓存** - 基于内容的缓存系统
- 🎵 **多格式支持** - MP3 和 WAV 格式
- 🌐 **完整 API** - 兼容原有 API 接口

## 🔧 配置

设置 Azure TTS（推荐）：

```bash
export AZURE_SPEECH_KEY="your_azure_key"
export AZURE_SPEECH_REGION="eastasia"
```

## 📖 文档

- [完整使用文档](README_NEW.md)
- [API 接口说明](README_NEW.md#api-接口)
- [故障排除指南](README_NEW.md#故障排除)

## 🆕 更新日志

**v3.0 (重构版)**

- ✅ 完全重构，模块化设计
- ✅ Azure TTS 作为默认引擎
- ✅ 自动故障转移
- ✅ 智能缓存和并发处理
- ✅ 目录自动创建
- ✅ 清理旧文件，项目结构更简洁

## �� 许可证

MIT License
