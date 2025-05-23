# Edge TTS 网页应用

这是一个基于 Flask 的网页应用，使用 Microsoft Edge TTS 服务来生成语音。

## 功能特点

- 文本转语音（TTS）
- 支持多种中文语音
- 可调节语速、音量和音调
- 在线播放生成的音频
- 下载生成的音频文件
- 历史记录管理（使用浏览器本地存储）

## 安装步骤

1. 克隆代码库：

```bash
git clone https://github.com/yourusername/edge-tts-web.git
cd edge-tts-web
```

2. 创建并激活虚拟环境（可选但推荐）：

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

## 运行应用

```bash
python app.py
```

应用将在 http://127.0.0.1:5000 运行。

## 使用方法

1. 在文本框中输入要转换为语音的文本
2. 选择语音（默认为中文小晓）
3. 调整语速、音量和音调（可选）
4. 点击"生成语音"按钮
5. 使用播放器控件收听生成的语音
6. 点击"下载音频"按钮保存音频文件
7. 点击"保存到历史"将此次生成的语音保存到历史记录中

## 注意事项

- 生成的音频文件存储在 `static/audio` 目录中
- 历史记录使用浏览器的本地存储，清除浏览器缓存会导致历史记录丢失
- 应用依赖于微软的在线 TTS 服务，需要网络连接

## 技术栈

- 后端：Flask, edge-tts
- 前端：HTML, CSS, JavaScript
- 样式：Bootstrap 5

## 许可证

本项目使用 MIT 许可证。
