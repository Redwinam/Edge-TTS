#!/usr/bin/env python3
"""
Azure TTS引擎实现
"""
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import time
import os
from .base import TTSEngine

class AzureTTSEngine(TTSEngine):
    """Azure TTS引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.speech_key = config.get('speech_key')
        self.speech_region = config.get('speech_region')
        self.endpoint = config.get('endpoint')
        self.default_voice = config.get('default_voice', 'zh-CN-XiaoxiaoNeural')
        
        # 访问令牌缓存
        self._access_token = None
        self._token_expiry = 0
        
        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure语音服务密钥和区域不能为空")
            
        print(f"🔵 Azure TTS引擎初始化完成 (区域: {self.speech_region})")
    
    async def _get_access_token(self) -> str:
        """获取访问令牌"""
        current_time = time.time()
        
        # 如果令牌还有效，直接返回
        if self._access_token and current_time < self._token_expiry:
            return self._access_token
        
        token_url = f"https://{self.speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        headers = {
            'Ocp-Apim-Subscription-Key': self.speech_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, headers=headers) as response:
                if response.status == 200:
                    self._access_token = await response.text()
                    # 令牌有效期为10分钟，我们设置为9分钟防止边界问题
                    self._token_expiry = current_time + 540
                    print("🔵 Azure访问令牌获取成功")
                    return self._access_token
                else:
                    error_text = await response.text()
                    raise Exception(f"获取Azure访问令牌失败: {response.status} - {error_text}")
    
    async def get_voices(self) -> List[Dict[str, Any]]:
        """获取Azure TTS可用语音列表"""
        try:
            token = await self._get_access_token()
            voices_url = f"https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(voices_url, headers=headers) as response:
                    if response.status == 200:
                        voices_data = await response.json()
                        print(f"🔵 获取到 {len(voices_data)} 个Azure语音")
                        
                        # 转换为统一格式
                        formatted_voices = []
                        for voice in voices_data:
                            formatted_voice = {
                                'name': voice.get('ShortName', ''),
                                'ShortName': voice.get('ShortName', ''),
                                'gender': voice.get('Gender', ''),
                                'localName': voice.get('LocalName', ''),
                                'displayName': self._format_display_name(voice),
                                'locale': voice.get('Locale', ''),
                                'sampleRateHertz': voice.get('VoiceType', ''),
                                'voiceType': voice.get('VoiceType', 'Neural')
                            }
                            formatted_voices.append(formatted_voice)
                        
                        return formatted_voices
                    else:
                        error_text = await response.text()
                        print(f"❌ 获取Azure语音列表失败: {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            print(f"❌ Azure语音列表获取异常: {e}")
            return []
    
    def _format_display_name(self, voice: Dict[str, Any]) -> str:
        """格式化显示名称"""
        locale = voice.get('Locale', '')
        local_name = voice.get('LocalName', '')
        gender = voice.get('Gender', '')
        
        # 区域映射
        region_map = {
            'zh-CN': '中国大陆',
            'zh-TW': '中国台湾', 
            'zh-HK': '中国香港',
            'ja-JP': '日本',
            'en-US': '美国',
            'en-GB': '英国',
            'ko-KR': '韩国',
            'fr-FR': '法国',
            'de-DE': '德国',
            'es-ES': '西班牙',
            'ru-RU': '俄罗斯',
            'it-IT': '意大利',
            'pt-BR': '巴西',
            'ar-SA': '沙特阿拉伯'
        }
        
        region_name = region_map.get(locale, locale)
        gender_name = '女' if gender == 'Female' else '男'
        
        if local_name:
            return f"{region_name} {local_name} ({gender_name})"
        else:
            short_name = voice.get('ShortName', '')
            return f"{region_name} {short_name} ({gender_name})"
    
    async def synthesize(self, text: str, voice: str, **kwargs) -> bytes:
        """合成语音并返回音频数据"""
        try:
            token = await self._get_access_token()
            
            # 构建SSML
            ssml = self._build_ssml(text, voice, **kwargs)
            
            # TTS请求
            tts_url = f"https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/ssml+xml',
                'X-Microsoft-OutputFormat': 'audio-24khz-48kbitrate-mono-mp3'  # 高质量MP3
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(tts_url, headers=headers, data=ssml.encode('utf-8')) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        print(f"🔵 Azure TTS合成成功: {len(audio_data)} bytes")
                        return audio_data
                    else:
                        error_text = await response.text()
                        raise Exception(f"Azure TTS合成失败: {response.status} - {error_text}")
                        
        except Exception as e:
            print(f"❌ Azure TTS合成异常: {e}")
            raise
    
    async def synthesize_to_file(self, text: str, output_path: str, voice: str, **kwargs) -> bool:
        """合成语音并保存到文件"""
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"📁 创建目录: {output_dir}")
            
            audio_data = await self.synthesize(text, voice, **kwargs)
            
            # 检查输出格式，如果需要WAV格式则转换
            audio_format = kwargs.get('audio_format', 'mp3').lower()
            
            if audio_format == 'wav':
                # 需要转换为WAV格式
                try:
                    from pydub import AudioSegment
                    import tempfile
                    
                    # 先保存为临时MP3文件
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        temp_file.write(audio_data)
                        temp_mp3_path = temp_file.name
                    
                    # 转换为WAV
                    audio = AudioSegment.from_mp3(temp_mp3_path)
                    audio.export(output_path, format="wav")
                    
                    # 清理临时文件
                    os.remove(temp_mp3_path)
                    print(f"🔵 已转换为WAV格式: {output_path}")
                    
                except ImportError:
                    print("⚠️  pydub未安装，无法转换为WAV格式，保持MP3格式")
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
                except Exception as e:
                    print(f"⚠️  WAV转换失败: {e}，保持MP3格式")
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
            else:
                # 直接保存MP3格式
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Azure TTS文件保存失败: {e}")
            return False
    
    def _build_ssml(self, text: str, voice: str, **kwargs) -> str:
        """构建SSML格式的语音合成请求"""
        rate = kwargs.get('rate', '+0%')
        volume = kwargs.get('volume', '+0%')
        pitch = kwargs.get('pitch', '+0Hz')
        
        # 处理语速格式（Azure使用不同的格式）
        if rate.endswith('%'):
            rate_value = rate[:-1]
            if rate_value.startswith('+'):
                rate_value = rate_value[1:]
            # Azure使用倍数格式，如 1.2 表示120%
            try:
                rate_percent = int(rate_value)
                rate_multiplier = 1.0 + (rate_percent / 100.0)
                rate = f"{rate_multiplier:.1f}"
            except:
                rate = "1.0"
        
        # 处理音量格式
        if volume.endswith('%'):
            volume_value = volume[:-1] 
            if volume_value.startswith('+'):
                volume_value = volume_value[1:]
            # Azure音量范围 0-100
            try:
                volume_percent = int(volume_value)
                volume_level = max(0, min(100, 50 + volume_percent))
                volume = f"{volume_level}%"
            except:
                volume = "50%"
        
        # 处理音调格式（Azure使用相对值）
        if pitch.endswith('Hz'):
            pitch_value = pitch[:-2]
            if pitch_value.startswith('+'):
                pitch_value = pitch_value[1:]
            # 转换为相对百分比
            try:
                pitch_hz = int(pitch_value)
                pitch_percent = pitch_hz  # 简化处理
                if pitch_percent > 0:
                    pitch = f"+{pitch_percent}%"
                elif pitch_percent < 0:
                    pitch = f"{pitch_percent}%"
                else:
                    pitch = "+0%"
            except:
                pitch = "+0%"
        
        ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="{voice}">
        <prosody rate="{rate}" volume="{volume}" pitch="{pitch}">
            {text}
        </prosody>
    </voice>
</speak>'''
        
        return ssml
    
    def _extract_language_code(self, voice: Dict[str, Any]) -> Optional[str]:
        """从Azure语音信息中提取语言代码"""
        # Azure语音的locale格式如 zh-CN, ja-JP等
        locale = voice.get('locale', '') or voice.get('Locale', '')
        if locale:
            return locale.split('-')[0]
        
        # 备用方法：从name提取
        return super()._extract_language_code(voice) 