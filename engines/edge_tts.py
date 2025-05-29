#!/usr/bin/env python3
"""
Edge TTS引擎实现
"""
import asyncio
import edge_tts
import os
from typing import List, Dict, Any, Optional
from .base import TTSEngine

class EdgeTTSEngine(TTSEngine):
    """Edge TTS引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.default_voice = config.get('default_voice', 'zh-CN-XiaoxiaoNeural')
        print(f"🟢 Edge TTS引擎初始化完成")
    
    async def get_voices(self) -> List[Dict[str, Any]]:
        """获取Edge TTS可用语音列表"""
        try:
            voices = await edge_tts.VoicesManager.create()
            voice_list = voices.voices
            print(f"🟢 获取到 {len(voice_list)} 个Edge语音")
            
            # 转换为统一格式
            formatted_voices = []
            for voice in voice_list:
                formatted_voice = {
                    'name': voice.get('ShortName', ''),
                    'ShortName': voice.get('ShortName', ''),
                    'gender': voice.get('Gender', ''),
                    'localName': voice.get('LocalName', ''),
                    'displayName': voice.get('DisplayName', ''),
                    'locale': voice.get('Locale', ''),
                    'voiceType': 'Neural'
                }
                formatted_voices.append(formatted_voice)
            
            return formatted_voices
            
        except Exception as e:
            print(f"❌ Edge语音列表获取异常: {e}")
            return []
    
    async def synthesize(self, text: str, voice: str, **kwargs) -> bytes:
        """合成语音并返回音频数据"""
        try:
            rate = kwargs.get('rate', '+0%')
            volume = kwargs.get('volume', '+0%')
            pitch = kwargs.get('pitch', '+0Hz')
            
            communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
            
            # 收集音频数据
            audio_data = b''
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            print(f"🟢 Edge TTS合成成功: {len(audio_data)} bytes")
            return audio_data
            
        except Exception as e:
            print(f"❌ Edge TTS合成异常: {e}")
            raise
    
    async def synthesize_to_file(self, text: str, output_path: str, voice: str, **kwargs) -> bool:
        """合成语音并保存到文件"""
        try:
            rate = kwargs.get('rate', '+0%')
            volume = kwargs.get('volume', '+0%')
            pitch = kwargs.get('pitch', '+0Hz')
            audio_format = kwargs.get('audio_format', 'mp3').lower()
            
            communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
            
            if audio_format == 'wav':
                # 需要转换为WAV格式
                try:
                    from pydub import AudioSegment
                    import tempfile
                    
                    # 先生成为临时MP3文件
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        temp_mp3_path = temp_file.name
                    
                    await communicate.save(temp_mp3_path)
                    
                    # 转换为WAV
                    audio = AudioSegment.from_mp3(temp_mp3_path)
                    audio.export(output_path, format="wav")
                    
                    # 清理临时文件
                    os.remove(temp_mp3_path)
                    print(f"🟢 已转换为WAV格式: {output_path}")
                    
                except ImportError:
                    print("⚠️  pydub未安装，无法转换为WAV格式，保持MP3格式")
                    await communicate.save(output_path)
                except Exception as e:
                    print(f"⚠️  WAV转换失败: {e}，保持MP3格式")
                    await communicate.save(output_path)
            else:
                # 直接保存MP3格式
                await communicate.save(output_path)
            
            return True
            
        except Exception as e:
            print(f"❌ Edge TTS文件保存失败: {e}")
            return False 