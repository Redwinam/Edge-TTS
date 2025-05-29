# TTS 服务 - 重构版 v3.0

🎵 支持 Azure TTS 和 Edge TTS 的智能语音合成服务，采用模块化架构设计，默认使用 Azure TTS。

## ✨ 主要特性

- 🔵 **Azure TTS 支持**: 默认使用 Azure 认知服务语音合成
- 🟢 **Edge TTS 备选**: 保留 Edge TTS 作为备用引擎
- 🏗️ **模块化设计**: 清晰的架构分离，易于维护和扩展
- ⚡ **智能并发**: 自动选择最优处理模式
- 🎯 **自动故障转移**: 引擎失败时自动切换
- 💾 **智能缓存**: 基于内容的缓存系统
- 🎵 **多格式支持**: MP3 和 WAV 格式输出
- 🌐 **完整 API**: 完全兼容原有 API 接口

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_new.txt
```

### 2. 配置 Azure TTS

```bash
# 设置Azure语音服务密钥和区域
export AZURE_SPEECH_KEY="your_azure_speech_key"
export AZURE_SPEECH_REGION="eastasia"
```

### 3. 启动服务

```bash
python start_new.py
```

服务将在 `http://localhost:5020` 启动。

## 📁 项目结构

```
├── app.py                 # 主应用文件
├── start_new.py          # 启动脚本
├── requirements_new.txt  # 依赖列表
├── config/               # 配置模块
│   ├── __init__.py
│   └── settings.py       # 配置文件
├── engines/              # TTS引擎模块
│   ├── __init__.py
│   ├── base.py          # 抽象基类
│   ├── azure_tts.py     # Azure TTS引擎
│   └── edge_tts.py      # Edge TTS引擎
├── services/             # 服务层
│   └── tts_service.py   # TTS服务核心逻辑
├── utils/                # 工具模块
│   ├── __init__.py
│   ├── cache.py         # 缓存管理
│   ├── audio.py         # 音频处理
│   └── decorators.py    # 装饰器工具
└── templates/            # 前端模板
    └── index.html       # Web界面
```

## ⚙️ 配置选项

通过环境变量自定义配置：

| 环境变量               | 默认值     | 说明                       |
| ---------------------- | ---------- | -------------------------- |
| `TTS_ENGINE`           | `azure`    | 默认 TTS 引擎 (azure/edge) |
| `MAX_CONCURRENT_TASKS` | `10`       | 最大并发任务数             |
| `AZURE_SPEECH_KEY`     | -          | Azure 语音服务密钥         |
| `AZURE_SPEECH_REGION`  | `eastasia` | Azure 服务区域             |

## 🔌 API 接口

### 单个 TTS 合成

```bash
curl -X POST http://localhost:5020/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好世界",
    "voice": "zh-CN-XiaoxiaoNeural",
    "audio_format": "wav"
  }'
```

### 批量 TTS 合成

```bash
curl -X POST http://localhost:5020/api/batch_tts \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"text": "第一段文本"},
      {"text": "第二段文本"}
    ],
    "audio_format": "wav",
    "output_name": "batch_output.wav"
  }'
```

### 引擎管理

```bash
# 获取当前引擎信息
curl http://localhost:5020/api/engine/info

# 切换引擎
curl -X POST http://localhost:5020/api/engine/switch \
  -H "Content-Type: application/json" \
  -d '{"engine": "edge"}'
```

## 🔵 Azure TTS 配置

1. 在 Azure 门户创建语音服务资源
2. 获取密钥和区域信息
3. 设置环境变量或修改配置文件

```python
# config/settings.py 中的Azure配置
AZURE_CONFIG = {
    'speech_key': 'your_key_here',
    'speech_region': 'eastasia'
}
```

## 🎯 故障转移

系统支持自动故障转移：

1. **Azure TTS 失败** → 自动切换到 Edge TTS
2. **网络问题** → 重试机制
3. **服务不可用** → 降级处理

## 💾 缓存机制

- **基于内容缓存**: 相同参数的请求直接返回缓存
- **智能清理**: 自动清理旧缓存文件
- **格式感知**: 支持 MP3 和 WAV 格式分别缓存

## 🔧 性能优化

- **并发处理**: 智能选择串行/并发模式
- **异步操作**: 全异步音频生成
- **FFmpeg 加速**: 支持 FFmpeg 超高性能音频合并
- **内存优化**: 流式处理大文件

## 🧹 清理旧文件

为了保持项目整洁，以下是清理建议：

### 可以删除的旧文件

```bash
# 旧版本文件
rm app_replacement.py
rm start.py
rm app_optimized.py
rm start_optimized.py
rm config.py
rm performance_test.py
rm test_replacement.py

# 旧配置文件
rm requirements_optimized.txt
rm OPTIMIZATION_GUIDE.md
rm README_REPLACEMENT.md
```

### 保留的重要文件

- `templates/index.html` - 前端界面
- `static/` - 静态文件目录
- `.gitignore` - Git 忽略规则
- `README.md` - 项目说明

## 🆕 新功能

- **引擎切换 API**: 运行时动态切换 TTS 引擎
- **健康检查**: `/health` 端点监控服务状态
- **格式转换**: 自动 MP3/WAV 格式转换
- **错误恢复**: 增强的错误处理和重试机制

## 📝 开发说明

### 添加新的 TTS 引擎

1. 继承 `TTSEngine` 基类
2. 实现必要的抽象方法
3. 在 `TTSService` 中注册引擎

```python
# 示例：添加新引擎
class NewTTSEngine(TTSEngine):
    async def get_voices(self):
        # 实现获取语音列表
        pass

    async def synthesize_to_file(self, text, output_path, voice, **kwargs):
        # 实现语音合成
        pass
```

### 扩展 API 功能

所有 API 路由在 `app.py` 中定义，服务逻辑在 `services/tts_service.py` 中实现。

## 🐛 故障排除

### 常见问题

1. **Azure TTS 连接失败**

   - 检查密钥和区域配置
   - 确认网络连接
   - 验证 Azure 服务状态

2. **音频合并失败**

   - 安装 FFmpeg 以获得最佳性能
   - 确保有足够的磁盘空间
   - 检查临时文件权限

3. **依赖安装问题**
   - 使用 Python 3.8+版本
   - 更新 pip: `pip install --upgrade pip`
   - 使用虚拟环境避免冲突

## 📄 许可证

MIT License - 详见 LICENSE 文件。

## �� 贡献

欢迎提交问题和拉取请求！
