#!/usr/bin/env python3
"""
TTS服务配置文件
支持Azure TTS和Edge TTS
"""
import os
from typing import Dict, Any

# ===== Azure TTS配置 =====
AZURE_CONFIG = {
    'speech_key': os.environ.get('AZURE_SPEECH_KEY'),
    'speech_region': os.environ.get('AZURE_SPEECH_REGION', 'eastasia'),
    'endpoint': f"https://{os.environ.get('AZURE_SPEECH_REGION', 'eastasia')}.tts.speech.microsoft.com/",
    'default_voice': 'zh-CN-XiaoxiaoNeural',  # Azure格式语音名称
    'default_language': 'zh-CN'
}

# ===== Edge TTS配置 =====
EDGE_CONFIG = {
    'default_voice': 'zh-CN-XiaoxiaoNeural',
    'default_language': 'zh-CN'
}

# ===== 服务配置 =====
TTS_CONFIG = {
    'default_engine': os.environ.get('TTS_ENGINE', 'azure'),  # 'azure' 或 'edge'
    'max_concurrent_tasks': int(os.environ.get('MAX_CONCURRENT_TASKS', 10)),
    'cache_enabled': True,
    'cache_dir': 'static/audio',
    'supported_formats': ['mp3', 'wav'],
    'default_format': 'mp3'
}

# ===== Flask应用配置 =====
FLASK_CONFIG = {
    'host': '0.0.0.0',
    'port': 5020,
    'debug': True,
    'upload_folder': 'static/audio'
}

# ===== CORS配置 =====
CORS_CONFIG = {
    'origins': ["*"],
    'methods': ["GET", "POST", "OPTIONS", "HEAD"],
    'allow_headers': [
        "Content-Type", "Authorization", "Range", "Accept", 
        "Accept-Encoding", "Accept-Language", "Cache-Control", 
        "Pragma", "Expires"
    ],
    'expose_headers': [
        "Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"
    ],
    'supports_credentials': False,
    'max_age': 86400
}

# ===== 语言映射 =====
LANGUAGE_NAMES = {
    'zh': '中文',
    'ja': '日语', 
    'en': '英语',
    'ko': '韩语',
    'fr': '法语',
    'de': '德语',
    'es': '西班牙语',
    'ru': '俄语',
    'it': '意大利语',
    'pt': '葡萄牙语',
    'ar': '阿拉伯语',
    'th': '泰语',
    'vi': '越南语',
    'id': '印尼语',
    'ms': '马来语',
    'tr': '土耳其语',
    'pl': '波兰语',
    'nl': '荷兰语',
    'hi': '印地语',
    'other': '其他语言'
}

def get_config() -> Dict[str, Any]:
    """获取所有配置"""
    return {
        'azure': AZURE_CONFIG,
        'edge': EDGE_CONFIG,
        'tts': TTS_CONFIG,
        'flask': FLASK_CONFIG,
        'cors': CORS_CONFIG,
        'language_names': LANGUAGE_NAMES
    }

def validate_azure_config() -> bool:
    """验证Azure配置是否有效"""
    return bool(AZURE_CONFIG['speech_key'] and AZURE_CONFIG['speech_region'])

def print_config_info():
    """打印配置信息"""
    print("🔧 TTS服务配置:")
    print(f"   默认引擎: {TTS_CONFIG['default_engine'].upper()}")
    print(f"   并发任务数: {TTS_CONFIG['max_concurrent_tasks']}")
    print(f"   缓存启用: {TTS_CONFIG['cache_enabled']}")
    print(f"   支持格式: {', '.join(TTS_CONFIG['supported_formats'])}")
    
    if TTS_CONFIG['default_engine'] == 'azure':
        print(f"🔵 Azure TTS配置:")
        print(f"   区域: {AZURE_CONFIG['speech_region']}")
        print(f"   默认语音: {AZURE_CONFIG['default_voice']}")
        print(f"   配置有效: {validate_azure_config()}")
    else:
        print(f"🟢 Edge TTS配置:")
        print(f"   默认语音: {EDGE_CONFIG['default_voice']}") 