# TTS 智能语音合成服务

🎵 支持 Azure TTS 和 Edge TTS 的智能语音合成服务，采用模块化架构设计

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python start_new.py
```

服务将在 `http://localhost:5020` 启动

## 📁 项目结构

```
├── app.py                 # 主应用文件
├── start_new.py          # 启动脚本
├── requirements.txt      # 依赖列表
├── config/               # 配置模块
├── engines/              # TTS引擎模块
├── services/             # 服务层
├── utils/                # 工具模块
├── templates/            # 前端模板
└── static/audio/         # 音频输出目录
```

## ✨ 主要特性

- 🔵 **Azure TTS 支持** - 默认使用 Azure 认知服务
- 🟢 **Edge TTS 备选** - 自动故障转移
- 🏗️ **模块化设计** - 清晰的架构分离
- ⚡ **智能并发** - 自动选择最优处理模式
- 💾 **智能缓存** - 基于内容的缓存系统
- 🔄 **内容去重** - 自动检测并去除重复内容，提升效率
- 🎵 **多格式支持** - MP3 和 WAV 格式
- 🌐 **完整 API** - 兼容原有 API 接口

## 🔧 配置

设置 Azure TTS（推荐）：

```bash
export AZURE_SPEECH_KEY="your_azure_key"
export AZURE_SPEECH_REGION="eastasia"
```

## 🔌 API 接口

### 单个 TTS 合成

```bash
curl -X POST http://localhost:5020/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "你好世界", "voice": "zh-CN-XiaoxiaoNeural"}'
```

### 批量 TTS 合成

```bash
curl -X POST http://localhost:5020/api/batch_tts \
  -H "Content-Type: application/json" \
  -d '{"items": [{"text": "第一段"}, {"text": "第二段"}]}'
```

### 获取可用语音

```bash
curl http://localhost:5020/api/voices
```

## 🚀 高级功能

- **智能并发处理** - 自动选择最优处理模式
- **自动故障转移** - Azure TTS 失败时切换到 Edge TTS
- **智能缓存系统** - 基于内容的缓存机制
- **FFmpeg 优化** - 支持超高性能音频合并
- **多格式支持** - MP3 和 WAV 格式输出
- **实时引擎切换** - 运行时动态切换 TTS 引擎

## �� 许可证

MIT License
