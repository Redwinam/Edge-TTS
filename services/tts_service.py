#!/usr/bin/env python3
"""
TTS服务核心逻辑
"""
import asyncio
import hashlib
import os
import shutil
import time
import uuid
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

from config import TTS_CONFIG, AZURE_CONFIG, EDGE_CONFIG
from engines import TTSEngineManager, AzureTTSEngine, EdgeTTSEngine
from utils.cache import TTSCache
from utils.audio import AudioProcessor
from utils.decorators import async_retry


class TTSService:
    """TTS服务类，统一管理不同的TTS引擎"""
    
    def __init__(self):
        self.engine_manager = TTSEngineManager()
        self.cache = TTSCache(TTS_CONFIG['cache_dir'])
        self.audio_processor = AudioProcessor()
        self._semaphores = {}
        
        # 初始化引擎
        self._initialize_engines()
        
    def _initialize_engines(self):
        """初始化所有TTS引擎"""
        try:
            # 初始化Azure TTS引擎
            azure_engine = AzureTTSEngine(AZURE_CONFIG)
            self.engine_manager.register_engine('azure', azure_engine)
            print("🔵 Azure TTS引擎注册成功")
        except Exception as e:
            print(f"⚠️  Azure TTS引擎初始化失败: {e}")
        
        try:
            # 初始化Edge TTS引擎
            edge_engine = EdgeTTSEngine(EDGE_CONFIG)
            self.engine_manager.register_engine('edge', edge_engine)
            print("🟢 Edge TTS引擎注册成功")
        except Exception as e:
            print(f"⚠️  Edge TTS引擎初始化失败: {e}")
        
        # 设置默认引擎
        default_engine = TTS_CONFIG['default_engine']
        if not self.engine_manager.set_current_engine(default_engine):
            # 如果默认引擎不可用，尝试其他引擎
            available_engines = self.engine_manager.get_available_engines()
            if available_engines:
                fallback_engine = available_engines[0]
                self.engine_manager.set_current_engine(fallback_engine)
                print(f"⚡ 默认引擎 {default_engine} 不可用，切换到 {fallback_engine}")
            else:
                raise RuntimeError("没有可用的TTS引擎")
    
    def get_semaphore(self, max_concurrent=None):
        """获取当前事件循环的Semaphore"""
        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
            
            if max_concurrent and max_concurrent != TTS_CONFIG['max_concurrent_tasks']:
                return asyncio.Semaphore(max_concurrent)
            
            if loop_id not in self._semaphores:
                self._semaphores[loop_id] = asyncio.Semaphore(TTS_CONFIG['max_concurrent_tasks'])
            
            return self._semaphores[loop_id]
        except RuntimeError:
            concurrent_limit = max_concurrent if max_concurrent else TTS_CONFIG['max_concurrent_tasks']
            return asyncio.Semaphore(concurrent_limit)
    
    async def get_voices(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取可用语音列表"""
        current_engine = self.engine_manager.get_current_engine()
        if not current_engine:
            return {}
        
        try:
            voices = await current_engine.get_voices()
            if voices:
                return current_engine.group_voices_by_language(voices)
            else:
                # 如果获取失败，尝试故障转移
                if await self.engine_manager.fallback_to_next_engine():
                    current_engine = self.engine_manager.get_current_engine()
                    voices = await current_engine.get_voices()
                    return current_engine.group_voices_by_language(voices)
                else:
                    # 返回备用语音列表
                    return current_engine.get_fallback_voices()
        except Exception as e:
            print(f"❌ 获取语音列表失败: {e}")
            # 返回备用语音列表
            current_engine = self.engine_manager.get_current_engine()
            if current_engine:
                return current_engine.get_fallback_voices()
            return {}
    
    @async_retry(retries=3, delay=2)
    async def synthesize_single(self, text: str, output_path: str, voice: str, 
                               rate: str, volume: str, pitch: str, 
                               max_concurrent=None, audio_format="wav") -> bool:
        """合成单个TTS音频"""
        async with self.get_semaphore(max_concurrent):
            # 检查缓存
            cache_key = self.cache.get_cache_key(text, voice, rate, volume, pitch, audio_format)
            
            if await self.cache.copy_from_cache(cache_key, output_path):
                return True
            
            print(f"缓存未命中，生成新文件: {text[:30]}... (格式: {audio_format})")
            
            # 使用当前引擎合成
            current_engine = self.engine_manager.get_current_engine()
            if not current_engine:
                raise RuntimeError("没有可用的TTS引擎")
            
            try:
                success = await current_engine.synthesize_to_file(
                    text, output_path, voice, 
                    rate=rate, volume=volume, pitch=pitch, audio_format=audio_format
                )
                
                if success:
                    # 保存到缓存
                    await self.cache.save_to_cache(cache_key, output_path)
                    return True
                else:
                    raise Exception("TTS合成失败")
                    
            except Exception as e:
                print(f"❌ 使用当前引擎合成失败: {e}")
                
                # 尝试故障转移
                if await self.engine_manager.fallback_to_next_engine():
                    print("🔄 尝试使用备用引擎...")
                    fallback_engine = self.engine_manager.get_current_engine()
                    success = await fallback_engine.synthesize_to_file(
                        text, output_path, voice,
                        rate=rate, volume=volume, pitch=pitch, audio_format=audio_format
                    )
                    
                    if success:
                        await self.cache.save_to_cache(cache_key, output_path)
                        return True
                
                raise e
    
    async def batch_synthesize_concurrent(self, items: List[Dict], rate: str, volume: str, 
                                        pitch: str, max_concurrent=None, 
                                        audio_format="wav") -> List[Tuple[str, Dict]]:
        """批量并发合成TTS音频"""
        tasks = []
        
        for i, item in enumerate(items):
            text = item.get('text', '').strip()
            if not text:
                continue
            
            voice = item.get('voice', AZURE_CONFIG['default_voice'])
            item_rate = item.get('rate', rate)
            item_volume = item.get('volume', volume)
            item_pitch = item.get('pitch', pitch)
            
            # 生成临时文件名
            temp_filename = f"batch_{uuid.uuid4()}.{audio_format}"
            temp_path = os.path.join(TTS_CONFIG['cache_dir'], temp_filename)
            
            # 创建异步任务
            task = self.synthesize_single(text, temp_path, voice, item_rate, 
                                        item_volume, item_pitch, max_concurrent, audio_format)
            tasks.append((task, temp_path, item, i))
        
        print(f"开始智能并发生成 {len(tasks)} 个TTS音频...")
        
        # 并发执行
        results = []
        completed_tasks_results = await asyncio.gather(*[task_info[0] for task_info in tasks], return_exceptions=True)
        
        for i, task_info in enumerate(tasks):
            original_task, temp_path, item_details, original_index = task_info
            result = completed_tasks_results[i]
            
            if isinstance(result, Exception):
                print(f"❌ 任务 {original_index + 1} 失败: {result}")
                continue
            
            # 验证文件
            if result is True and os.path.exists(temp_path):
                file_size = os.path.getsize(temp_path)
                if file_size > 0:
                    results.append((temp_path, item_details))
                    print(f"✅ 已生成音频 {original_index + 1}/{len(tasks)}: {item_details.get('text', '')[:20]}... (大小: {file_size} bytes)")
                else:
                    print(f"⚠️  任务 {original_index + 1} 生成的文件为空")
                    try:
                        os.remove(temp_path)
                    except:
                        pass
        
        print(f"🎵 并发生成完成: 成功 {len(results)}/{len(tasks)} 个音频文件")
        return results
    
    async def create_batch_audio(self, items: List[Dict], output_name: str, 
                               rate: str, volume: str, pitch: str,
                               silence_duration: int = 200, 
                               use_concurrent: bool = True,
                               max_concurrent: Optional[int] = None,
                               audio_format: str = "wav") -> Dict[str, Any]:
        """批量创建音频并合并"""
        start_time = time.time()
        items_count = len(items)
        
        # 智能选择处理模式
        if not use_concurrent or items_count <= 3:
            processing_mode = 'serial'
            print(f"🔄 使用串行处理模式 (项目数: {items_count}, 格式: {audio_format})")
            temp_files = await self._batch_synthesize_serial(items, rate, volume, pitch, audio_format)
        else:
            processing_mode = 'concurrent'
            concurrent_limit = max_concurrent or TTS_CONFIG['max_concurrent_tasks']
            print(f"⚡ 使用智能并发处理模式 (项目数: {items_count}, 并发数: {concurrent_limit}, 格式: {audio_format})")
            results = await self.batch_synthesize_concurrent(items, rate, volume, pitch, concurrent_limit, audio_format)
            temp_files = [result[0] for result in results]
        
        if not temp_files:
            raise ValueError('没有生成任何音频文件')
        
        # 验证文件
        validated_files = []
        for temp_file in temp_files:
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                validated_files.append(temp_file)
        
        if not validated_files:
            raise ValueError('没有有效的音频文件可合并')
        
        # 合并音频文件
        output_path = os.path.join(TTS_CONFIG['cache_dir'], output_name)
        success = await self.audio_processor.combine_audio_files(
            validated_files, output_path, silence_duration, audio_format
        )
        
        # 清理临时文件
        for temp_file in validated_files:
            try:
                os.remove(temp_file)
            except:
                pass
        
        generation_time = time.time() - start_time
        
        if not success:
            raise RuntimeError('音频合并失败')
        
        return {
            'output_path': output_path,
            'items_processed': len(validated_files),
            'generation_time': round(generation_time, 2),
            'processing_mode': processing_mode,
            'audio_format': audio_format
        }
    
    async def _batch_synthesize_serial(self, items: List[Dict], rate: str, volume: str, 
                                     pitch: str, audio_format: str = "wav") -> List[str]:
        """串行批量合成"""
        temp_files = []
        
        for i, item in enumerate(items):
            text = item.get('text', '')
            voice = item.get('voice', AZURE_CONFIG['default_voice'])
            item_rate = item.get('rate', rate)
            item_volume = item.get('volume', volume)
            item_pitch = item.get('pitch', pitch)
            
            if not text.strip():
                continue
            
            # 生成临时文件名
            file_ext = audio_format
            temp_filename = f"batch_{uuid.uuid4()}.{file_ext}"
            temp_path = os.path.join(TTS_CONFIG['cache_dir'], temp_filename)
            
            # 合成TTS音频
            success = await self.synthesize_single(text, temp_path, voice, item_rate, 
                                                 item_volume, item_pitch, None, audio_format)
            if success:
                temp_files.append(temp_path)
                print(f"已生成音频 {i+1}/{len(items)}: {text[:20]}... (格式: {audio_format})")
        
        return temp_files
    
    def get_current_engine_info(self) -> Dict[str, Any]:
        """获取当前引擎信息"""
        current_engine = self.engine_manager.get_current_engine()
        if current_engine:
            return {
                'name': current_engine.name,
                'available_engines': self.engine_manager.get_available_engines(),
                'config': current_engine.config
            }
        return {}
    
    def switch_engine(self, engine_name: str) -> bool:
        """切换TTS引擎"""
        return self.engine_manager.set_current_engine(engine_name) 