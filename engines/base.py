#!/usr/bin/env python3
"""
TTS引擎抽象基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio

class TTSEngine(ABC):
    """TTS引擎抽象基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def get_voices(self) -> List[Dict[str, Any]]:
        """获取可用语音列表"""
        pass
    
    @abstractmethod
    async def synthesize(self, text: str, voice: str, **kwargs) -> bytes:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            voice: 语音名称
            **kwargs: 其他参数（rate, volume, pitch等）
            
        Returns:
            音频数据（bytes）
        """
        pass
    
    @abstractmethod
    async def synthesize_to_file(self, text: str, output_path: str, voice: str, **kwargs) -> bool:
        """
        合成语音并保存到文件
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            voice: 语音名称
            **kwargs: 其他参数
            
        Returns:
            是否成功
        """
        pass
    
    def group_voices_by_language(self, voices: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按语言分组语音"""
        grouped_voices = {}
        
        for voice in voices:
            # 从语音名称中提取语言代码
            lang_code = self._extract_language_code(voice)
            category = lang_code if lang_code else 'other'
            
            if category not in grouped_voices:
                grouped_voices[category] = []
                
            grouped_voices[category].append(voice)
        
        return grouped_voices
    
    def _extract_language_code(self, voice: Dict[str, Any]) -> Optional[str]:
        """从语音信息中提取语言代码"""
        voice_name = voice.get('name', '') or voice.get('ShortName', '')
        if voice_name:
            # 提取前两位语言代码，如 zh-CN-XiaoxiaoNeural -> zh
            parts = voice_name.split('-')
            if len(parts) >= 2:
                return parts[0]
        return None
    
    def get_fallback_voices(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取备用语音列表（当获取失败时使用）"""
        return {
            'zh': [
                {'name': 'zh-CN-XiaoxiaoNeural', 'gender': 'Female', 'localName': '晓晓', 'displayName': '中国大陆 晓晓 (女)'},
                {'name': 'zh-CN-YunyangNeural', 'gender': 'Male', 'localName': '云扬', 'displayName': '中国大陆 云扬 (男)'},
                {'name': 'zh-CN-YunxiNeural', 'gender': 'Male', 'localName': '云希', 'displayName': '中国大陆 云希 (男)'},
                {'name': 'zh-CN-XiaomoNeural', 'gender': 'Female', 'localName': '晓墨', 'displayName': '中国大陆 晓墨 (女)'},
                {'name': 'zh-CN-XiaoxuanNeural', 'gender': 'Female', 'localName': '晓萱', 'displayName': '中国大陆 晓萱 (女)'}
            ],
            'ja': [
                {'name': 'ja-JP-NanamiNeural', 'gender': 'Female', 'localName': '七海', 'displayName': '日本 七海 (女)'},
                {'name': 'ja-JP-KeitaNeural', 'gender': 'Male', 'localName': '啓太', 'displayName': '日本 啓太 (男)'}
            ],
            'en': [
                {'name': 'en-US-JennyNeural', 'gender': 'Female', 'localName': 'Jenny', 'displayName': '美国 Jenny (女)'},
                {'name': 'en-GB-SoniaNeural', 'gender': 'Female', 'localName': 'Sonia', 'displayName': '英国 Sonia (女)'}
            ]
        }

class TTSEngineManager:
    """TTS引擎管理器"""
    
    def __init__(self):
        self.engines: Dict[str, TTSEngine] = {}
        self.current_engine: Optional[TTSEngine] = None
        
    def register_engine(self, name: str, engine: TTSEngine):
        """注册TTS引擎"""
        self.engines[name] = engine
        print(f"🔌 已注册TTS引擎: {name}")
        
    def set_current_engine(self, name: str) -> bool:
        """设置当前使用的引擎"""
        if name in self.engines:
            self.current_engine = self.engines[name]
            print(f"🎯 切换到TTS引擎: {name}")
            return True
        return False
        
    def get_current_engine(self) -> Optional[TTSEngine]:
        """获取当前引擎"""
        return self.current_engine
        
    def get_available_engines(self) -> List[str]:
        """获取可用引擎列表"""
        return list(self.engines.keys())
        
    async def fallback_to_next_engine(self) -> bool:
        """故障转移到下一个可用引擎"""
        current_name = None
        for name, engine in self.engines.items():
            if engine == self.current_engine:
                current_name = name
                break
                
        # 尝试切换到其他引擎
        for name, engine in self.engines.items():
            if name != current_name:
                try:
                    # 简单测试引擎是否可用
                    await engine.get_voices()
                    self.current_engine = engine
                    print(f"⚡ 故障转移到引擎: {name}")
                    return True
                except Exception as e:
                    print(f"❌ 引擎 {name} 不可用: {e}")
                    continue
        return False 