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
                               max_concurrent=None, audio_format="mp3") -> bool:
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
                                        audio_format="mp3") -> List[Tuple[str, Dict]]:
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
    
    def _deduplicate_items(self, items: List[Dict]) -> Tuple[List[Dict], Dict[str, List[int]]]:
        """
        对批量TTS项目进行去重处理
        
        Args:
            items: 原始项目列表
            
        Returns:
            tuple: (去重后的项目列表, 去重映射表)
                  去重映射表格式: {unique_key: [原始索引列表]}
        """
        seen_items = {}  # 存储已见过的项目
        unique_items = []  # 去重后的唯一项目
        dedup_map = {}  # 映射表：unique_key -> 原始索引列表
        
        for i, item in enumerate(items):
            text = item.get('text', '').strip()
            if not text:
                continue
                
            voice = item.get('voice', AZURE_CONFIG['default_voice'])
            rate = item.get('rate', '+0%')
            volume = item.get('volume', '+0%')
            pitch = item.get('pitch', '+0Hz')
            
            # 生成唯一标识键
            unique_key = f"{text}|{voice}|{rate}|{volume}|{pitch}"
            
            if unique_key in seen_items:
                # 如果已存在，添加到映射表
                dedup_map[unique_key].append(i)
            else:
                # 新的唯一项目
                seen_items[unique_key] = len(unique_items)
                unique_items.append(item)
                dedup_map[unique_key] = [i]
        
        original_count = len(items)
        unique_count = len(unique_items)
        duplicate_count = original_count - unique_count
        
        if duplicate_count > 0:
            print(f"🔄 内容去重: 原始 {original_count} 个项目 → 去重后 {unique_count} 个项目 (减少 {duplicate_count} 个重复项目)")
            
            # 打印去重详情
            for unique_key, indices in dedup_map.items():
                if len(indices) > 1:
                    text_preview = unique_key.split('|')[0][:30]
                    print(f"   📋 重复内容: '{text_preview}...' 出现 {len(indices)} 次 (位置: {indices})")
        else:
            print(f"✅ 无重复内容: {original_count} 个项目均为唯一")
            
        return unique_items, dedup_map

    def _reconstruct_results_with_dedup(self, unique_results: List[str], 
                                      dedup_map: Dict[str, List[int]], 
                                      unique_items: List[Dict]) -> List[str]:
        """
        根据去重映射表重建完整的结果列表
        
        Args:
            unique_results: 去重后的音频文件路径列表
            dedup_map: 去重映射表
            unique_items: 去重后的项目列表
            
        Returns:
            完整的音频文件路径列表（包含重复项目的复制）
        """
        if not unique_results or not dedup_map:
            return unique_results
            
        full_results = [None] * sum(len(indices) for indices in dedup_map.values())
        
        # 为每个唯一项目生成键
        for i, (unique_item, result_path) in enumerate(zip(unique_items, unique_results)):
            text = unique_item.get('text', '').strip()
            voice = unique_item.get('voice', AZURE_CONFIG['default_voice'])
            rate = unique_item.get('rate', '+0%')
            volume = unique_item.get('volume', '+0%')
            pitch = unique_item.get('pitch', '+0Hz')
            
            unique_key = f"{text}|{voice}|{rate}|{volume}|{pitch}"
            
            if unique_key in dedup_map:
                # 复制音频文件到所有需要的位置
                for original_index in dedup_map[unique_key]:
                    full_results[original_index] = result_path
        
        # 过滤掉None值（可能是空文本项目）
        return [result for result in full_results if result is not None]

    async def create_batch_audio(self, items: List[Dict], output_name: str, 
                               rate: str, volume: str, pitch: str,
                               silence_duration: int = 200, 
                               use_concurrent: bool = True,
                               max_concurrent: Optional[int] = None,
                               audio_format: str = "mp3") -> Dict[str, Any]:
        """批量创建音频并合并"""
        start_time = time.time()
        original_items_count = len(items)
        
        # 🔄 内容去重处理
        unique_items, dedup_map = self._deduplicate_items(items)
        items_count = len(unique_items)
        
        # 智能选择处理模式
        if not use_concurrent or items_count <= 3:
            processing_mode = 'serial'
            print(f"🔄 使用串行处理模式 (项目数: {items_count}, 格式: {audio_format})")
            temp_files = await self._batch_synthesize_serial(unique_items, rate, volume, pitch, audio_format)
        else:
            processing_mode = 'concurrent'
            concurrent_limit = max_concurrent or TTS_CONFIG['max_concurrent_tasks']
            print(f"⚡ 使用智能并发处理模式 (项目数: {items_count}, 并发数: {concurrent_limit}, 格式: {audio_format})")
            results = await self.batch_synthesize_concurrent(unique_items, rate, volume, pitch, concurrent_limit, audio_format)
            temp_files = [result[0] for result in results]
        
        if not temp_files:
            raise ValueError('没有生成任何音频文件')
        
        # 🔄 根据去重映射重建完整结果
        if len(unique_items) < original_items_count:
            print(f"🔄 重建完整音频序列: {len(temp_files)} 个唯一文件 → {original_items_count} 个音频片段")
            full_temp_files = self._reconstruct_results_with_dedup(temp_files, dedup_map, unique_items)
        else:
            full_temp_files = temp_files
        
        # 验证文件
        validated_files = []
        for temp_file in full_temp_files:
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                validated_files.append(temp_file)
        
        if not validated_files:
            raise ValueError('没有有效的音频文件可合并')
        
        # 合并音频文件
        output_path = os.path.join(TTS_CONFIG['cache_dir'], output_name)
        success = await self.audio_processor.combine_audio_files(
            validated_files, output_path, silence_duration, audio_format
        )
        
        # 清理临时文件（只删除唯一的文件，避免重复删除）
        unique_temp_files = list(set(temp_files))  # 去除重复的文件路径
        for temp_file in unique_temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        generation_time = time.time() - start_time
        
        if not success:
            raise RuntimeError('音频合并失败')
        
        duplicate_count = original_items_count - items_count
        efficiency_info = ""
        if duplicate_count > 0:
            efficiency_gain = round((duplicate_count / original_items_count) * 100, 1)
            efficiency_info = f" (去重节省 {duplicate_count} 次合成，效率提升 {efficiency_gain}%)"
        
        return {
            'output_path': output_path,
            'items_processed': original_items_count,  # 返回原始项目数
            'unique_items_synthesized': items_count,   # 实际合成的唯一项目数
            'generation_time': round(generation_time, 2),
            'processing_mode': processing_mode,
            'audio_format': audio_format,
            'efficiency_info': efficiency_info
        }
    
    async def _batch_synthesize_serial(self, items: List[Dict], rate: str, volume: str, 
                                     pitch: str, audio_format: str = "mp3") -> List[str]:
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

    async def create_batch_tts_with_timecodes(self, items: List[Dict], 
                                            rate: str, volume: str, pitch: str,
                                            silence_duration_ms: int = 200, 
                                            audio_format: str = "mp3",
                                            use_concurrent: bool = True,
                                            max_concurrent: Optional[int] = None) -> Dict[str, Any]:
        """
        批量合成TTS音频，不合并，返回各片段的时间码信息。
        """
        start_time = time.time()
        original_items_count = len(items)
        
        # 1. 内容去重
        # unique_items: list of unique item dicts
        # dedup_map: dict where key is "text|voice|rate|volume|pitch" and value is list of original indices
        unique_items, dedup_map = self._deduplicate_items(items)
        items_to_synthesize_count = len(unique_items)
        
        print(f"⏱️ 开始批量TTS（带时间码）: {original_items_count} 个原始项目, {items_to_synthesize_count} 个唯一项目")

        # 2. 合成唯一的音频片段
        # synthesized_unique_audios: list of dicts {'path': str, 'item_detail': dict, 'duration': float (initially 0)}
        # This list's order matches the order of unique_items
        synthesized_unique_audios = []

        if items_to_synthesize_count == 0: # 如果没有唯一项目（例如所有输入都是空文本）
            print("⚠️ 没有有效的唯一项目进行合成。")
        elif not use_concurrent or items_to_synthesize_count <= 3:
            processing_mode = 'serial'
            print(f"🔄 使用串行处理模式 (唯一项目数: {items_to_synthesize_count}, 格式: {audio_format})")
            synthesized_paths = await self._batch_synthesize_serial(unique_items, rate, volume, pitch, audio_format)
            for i, path in enumerate(synthesized_paths):
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    synthesized_unique_audios.append({'path': path, 'item_detail': unique_items[i], 'duration': 0.0})
                else:
                    print(f"⚠️ 串行合成的音频无效或为空: {path} (对应唯一项目索引 {i})")
                    # 添加一个占位符，或记录错误，以便后续处理
                    synthesized_unique_audios.append({'path': None, 'item_detail': unique_items[i], 'duration': 0.0, 'error': 'synthesis_failed_or_empty'})
        else:
            processing_mode = 'concurrent'
            concurrent_limit = max_concurrent or TTS_CONFIG['max_concurrent_tasks']
            print(f"⚡ 使用智能并发处理模式 (唯一项目数: {items_to_synthesize_count}, 并发数: {concurrent_limit}, 格式: {audio_format})")
            # results: List[Tuple[str, Dict]] -> (temp_path, item_details_from_unique_items)
            # The order of `results` corresponds to the order of `unique_items`
            results = await self.batch_synthesize_concurrent(unique_items, rate, volume, pitch, concurrent_limit, audio_format)
            for i, (path, item_detail) in enumerate(results): # item_detail is from unique_items
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    synthesized_unique_audios.append({'path': path, 'item_detail': item_detail, 'duration': 0.0})
                else:
                    print(f"⚠️ 并发合成的音频无效或为空: {path} (对应唯一项目索引 {i})")
                    synthesized_unique_audios.append({'path': None, 'item_detail': item_detail, 'duration': 0.0, 'error': 'synthesis_failed_or_empty'})
        
        if not synthesized_unique_audios and items_to_synthesize_count > 0 : # 如果有尝试合成但列表为空
             raise ValueError('所有唯一项目的音频合成均失败，无法进行时间码分析')
        elif items_to_synthesize_count == 0: # 如果开始就没有唯一项目
            pass # 继续执行，将返回空时间码等


        # 3. 获取每个有效唯一音频片段的时长
        valid_audio_paths_for_duration_analysis = [info['path'] for info in synthesized_unique_audios if info['path']]
        
        if valid_audio_paths_for_duration_analysis:
            print(f"🔍 分析 {len(valid_audio_paths_for_duration_analysis)} 个唯一音频文件的时长...")
            durations_sec = await self.audio_processor.get_audio_durations(valid_audio_paths_for_duration_analysis)
            
            # 将时长更新回 synthesized_unique_audios
            duration_idx = 0
            for info in synthesized_unique_audios:
                if info['path']: # 只为有路径的文件更新时长
                    if duration_idx < len(durations_sec):
                        info['duration'] = durations_sec[duration_idx]
                        print(f"   📄 音频: ...{info['path'][-20:]}, 时长: {info['duration']:.3f}s")
                        duration_idx += 1
                    else: # 不应发生，如果发生了说明 durations_sec 长度不够
                        print(f"   ⚠️ 警告: 音频 {info['path']} 没有对应的时长信息。")
                        info['duration'] = 0.0 # 或其他默认/错误标记

        # 4. 根据去重映射和时长计算时间码
        # `final_timecodes_ordered` will store dicts {text, original_index, start_time_ms, duration_ms, end_time_ms}
        # in the order of the original `items`
        final_timecodes_ordered = [None] * original_items_count
        
        # Create a map from unique_item's key to its info (path, duration)
        # The key must be generated exactly as in _deduplicate_items
        unique_item_key_to_info_map = {}
        for i, unique_item_detail_dict in enumerate(synthesized_unique_audios):
            # unique_item_detail_dict['item_detail'] is the item from unique_items
            # unique_item_detail_dict['duration'] is its calculated duration
            key = self._generate_item_key(unique_item_detail_dict['item_detail'], rate, volume, pitch)
            unique_item_key_to_info_map[key] = {
                'duration': unique_item_detail_dict['duration'], 
                'path': unique_item_detail_dict['path'], # For reference or cleanup
                'synthesized_item': unique_item_detail_dict['item_detail'] # The actual item that was synthesized
            }

        # Iterate through the original items' structure using dedup_map
        for unique_key_from_dedup, original_indices_list in dedup_map.items():
            # Get the synthesized info for this unique_key
            synthesized_info = unique_item_key_to_info_map.get(unique_key_from_dedup)
            
            item_duration_sec = 0.0
            if synthesized_info:
                item_duration_sec = synthesized_info['duration']
            else:
                # This case implies a mismatch or an item that was in dedup_map but not synthesized
                # (e.g., if all items were empty strings, unique_items would be empty)
                # Or, if the key generation had subtle differences.
                # _deduplicate_items filters out empty text items, so unique_items won't contain them.
                # dedup_map's keys are based on non-empty text items.
                print(f"⚠️ 警告: 在 'unique_item_key_to_info_map' 中未找到键 '{unique_key_from_dedup}'。")
                print(f"    这可能表示该唯一项合成失败或键生成不一致。受影响的原始索引: {original_indices_list}")
                # For items associated with this key, duration will be 0.
            
            item_duration_ms = item_duration_sec * 1000

            for original_idx in original_indices_list:
                original_item_text = items[original_idx].get('text', '')
                # We don't use current_time_ms here yet, will calculate cumulative time later
                timecode_entry = {
                    'text': original_item_text,
                    'original_index': original_idx,
                    'duration_ms': round(item_duration_ms), 
                    'synthesized_text': synthesized_info['synthesized_item'].get('text', '') if synthesized_info and synthesized_info.get('synthesized_item') else original_item_text, # Text actually sent for synthesis
                    'voice_used': synthesized_info['synthesized_item'].get('voice') if synthesized_info and synthesized_info.get('synthesized_item') else items[original_idx].get('voice'),
                }
                final_timecodes_ordered[original_idx] = timecode_entry
        
        # Calculate cumulative start and end times including silence
        actual_timecodes_with_silence = []
        running_time_ms = 0.0
        for i in range(original_items_count):
            entry = final_timecodes_ordered[i]
            if entry: # If it's a valid entry (not None)
                entry['start_time_ms'] = round(running_time_ms)
                entry['end_time_ms'] = round(running_time_ms + entry['duration_ms'])
                actual_timecodes_with_silence.append(entry)
                
                running_time_ms += entry['duration_ms']
                # Add silence if it's not the last actual item that will have audio
                # Check if there's a next valid item to determine if silence is needed
                is_last_valid_item = True
                for k in range(i + 1, original_items_count):
                    if final_timecodes_ordered[k] and final_timecodes_ordered[k]['duration_ms'] > 0:
                        is_last_valid_item = False
                        break
                
                if not is_last_valid_item and entry['duration_ms'] > 0 : # Add silence only if current has duration and is not the last one with duration
                     running_time_ms += silence_duration_ms
                elif not is_last_valid_item and entry['duration_ms'] == 0 and silence_duration_ms > 0: # if item has 0 duration but silence is configured
                    # this means it's a placeholder, we might still add silence if it's not the absolute last item
                    # This logic can be tricky: if many 0-duration items, do we add silence after each?
                    # For now, only add silence after items that *had* audio or if explicitly handled.
                    # Simplified: add silence if not the last entry in the final list.
                    # Let's refine: Add silence if this item exists AND it's not the last *overall* item in the original list
                    # AND there's another valid item coming up or silence_duration > 0
                    # The previous check `is_last_valid_item` is better.
                     pass


            else: # Handle items that were not processed (e.g. original item was empty text and filtered out early)
                # If you need placeholders for these in the timecode list:
                # actual_timecodes_with_silence.append({
                #     'text': items[i].get('text', ''), 
                #     'original_index': i, 
                #     'duration_ms': 0, 
                #     'start_time_ms': round(running_time_ms), 
                #     'end_time_ms': round(running_time_ms),
                #     'error': 'item_skipped_or_empty'
                # })
                # If silence still needs to be added for consistency:
                # if i < original_items_count - 1 and silence_duration_ms > 0:
                #    running_time_ms += silence_duration_ms
                pass


        # 5. 清理临时唯一音频文件
        paths_to_clean = [info['path'] for info in synthesized_unique_audios if info['path']]
        if paths_to_clean:
            print(f"🧹 清理 {len(paths_to_clean)} 个临时唯一音频文件...")
            cleaned_count = 0
            for path in paths_to_clean:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        cleaned_count += 1
                except Exception as e:
                    print(f"删除临时文件 {path} 失败: {e}")
            print(f"   => 成功清理 {cleaned_count} 个文件。")

        generation_time = time.time() - start_time
        
        return {
            'success': True,
            'timecodes': actual_timecodes_with_silence,
            'total_duration_with_silence_ms': round(running_time_ms),
            'items_processed_count': original_items_count,
            'unique_items_synthesized_count': items_to_synthesize_count, # Number of unique items we attempted to synthesize
            'actual_segments_with_audio_count': len([tc for tc in actual_timecodes_with_silence if tc['duration_ms'] > 0]),
            'silence_between_items_ms': silence_duration_ms,
            'generation_time_seconds': round(generation_time, 2),
            'processing_mode': processing_mode,
            'audio_format_generated': audio_format 
        }

    def _generate_item_key(self, item: Dict, default_rate: str, default_volume: str, default_pitch: str) -> str:
        """辅助方法: 为TTS item生成与_deduplicate_items中一致的唯一键"""
        text = item.get('text', '').strip()
        
        # 获取当前引擎的默认语音或全局默认语音
        current_engine_config = self.engine_manager.get_current_engine().config if self.engine_manager.get_current_engine() else {}
        # TTS_CONFIG['default_voice'] 作为最终备选
        default_voice_from_engine = current_engine_config.get('default_voice')
        if not default_voice_from_engine: # Fallback to global config if engine has no specific default
            default_voice_from_engine = TTS_CONFIG.get('default_voice', 'zh-CN-XiaoxiaoNeural') # Fallback to a hardcoded general default

        voice = item.get('voice', default_voice_from_engine)
        rate_val = item.get('rate', default_rate) 
        volume_val = item.get('volume', default_volume)
        pitch_val = item.get('pitch', default_pitch)
        return f"{text}|{voice}|{rate_val}|{volume_val}|{pitch_val}" 