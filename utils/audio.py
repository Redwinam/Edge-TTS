#!/usr/bin/env python3
"""
音频处理工具
"""
import os
import subprocess
import tempfile
import time
import asyncio
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
import uuid


class AudioProcessor:
    """音频处理器"""
    
    def __init__(self):
        self.ffmpeg_available = self._check_ffmpeg()
        
    def _check_ffmpeg(self) -> bool:
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print(f"✅ FFmpeg已安装，将使用超高性能音频合并模式")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"⚠️  FFmpeg未安装，将使用pydub合并模式")
            return False
    
    async def combine_audio_files(self, file_paths: List[str], output_path: str, 
                                silence_duration: int = 0, 
                                audio_format: str = "wav") -> bool:
        """合并音频文件"""
        if self.ffmpeg_available:
            return await self._combine_with_ffmpeg(file_paths, output_path, silence_duration, audio_format)
        else:
            return await self._combine_with_pydub(file_paths, output_path, silence_duration, audio_format)
    
    async def _combine_with_ffmpeg(self, file_paths: List[str], output_path: str, 
                                 silence_duration: int, audio_format: str) -> bool:
        """使用FFmpeg进行超高性能音频合并"""
        start_time = time.time()
        
        try:
            print(f"🚀 FFmpeg超高性能模式: 合并 {len(file_paths)} 个文件 (格式: {audio_format})")
            
            # 验证文件
            valid_files = [f for f in file_paths if os.path.exists(f) and os.path.getsize(f) > 0]
            if not valid_files:
                print("❌ 没有有效的音频文件")
                return False
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"📁 创建输出目录: {output_dir}")
            
            # 确定输出编码设置
            if audio_format.lower() == "wav":
                codec_settings = ['-c:a', 'pcm_s16le']
                print("📊 使用WAV格式输出 (PCM 16-bit)")
            else:
                codec_settings = ['-c:a', 'mp3', '-b:a', '128k']
                print("📊 使用MP3格式输出 (128kbps)")
            
            # 在线程池中执行FFmpeg操作
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                success = await loop.run_in_executor(
                    executor, 
                    self._run_ffmpeg_combine, 
                    valid_files, output_path, silence_duration, codec_settings
                )
            
            if success:
                processing_time = time.time() - start_time
                avg_time_per_file = processing_time / len(valid_files)
                print(f"✅ FFmpeg超高性能合并完成: {len(valid_files)} 个文件, 用时 {processing_time:.2f}s, 平均每文件 {avg_time_per_file:.3f}s")
                return True
            else:
                print("🔄 FFmpeg合并失败，回退到pydub方案")
                return await self._combine_with_pydub(file_paths, output_path, silence_duration, audio_format)
                
        except Exception as e:
            print(f"FFmpeg合并出错: {e}, 回退到pydub方案")
            return await self._combine_with_pydub(file_paths, output_path, silence_duration, audio_format)
    
    def _run_ffmpeg_combine(self, valid_files: List[str], output_path: str, 
                          silence_duration: int, codec_settings: List[str]) -> bool:
        """在线程中运行FFmpeg合并"""
        target_sample_rate = 48000 # 目标采样率
        try:
            input_parts = []
            filter_complex_parts = []
            stream_labels = [] # To store labels like [a0], [a1] for concat filter

            if silence_duration > 0:
                for i, file_path in enumerate(valid_files):
                    input_parts.extend(['-i', file_path])
                    # Resample current audio file and give it a label for concat
                    filter_complex_parts.append(f'[{i}:a]aresample={target_sample_rate}[s{i}]') 
                    stream_labels.append(f'[s{i}]')
                    
                    if i < len(valid_files) - 1:
                        # Generate silence with target sample rate and label it
                        silence_label = f'[silence{i}]'
                        # Using a unique stream index for silence input to avoid conflict if file count is large
                        silence_input_idx_ffmpeg = len(valid_files) + i 
                        silence_filter_str = f'aevalsrc=0:duration={silence_duration/1000}:sample_rate={target_sample_rate}'
                        input_parts.extend(['-f', 'lavfi', '-i', silence_filter_str])
                        # The input for silence is len(valid_files) + i for ffmpeg indexing
                        filter_complex_parts.append(f'[{silence_input_idx_ffmpeg}:a]acopy{silence_label}') 
                        stream_labels.append(silence_label)
                
                concat_filter = ''.join(stream_labels) + f'concat=n={len(stream_labels)}:v=0:a=1[out]'
                filter_complex_parts.append(concat_filter)

            else: # No silence duration
                for i, file_path in enumerate(valid_files):
                    input_parts.extend(['-i', file_path])
                    # Resample current audio file and give it a temp label [sa0], [sa1] etc.
                    filter_complex_parts.append(f'[{i}:a]aresample={target_sample_rate}[s{i}]')
                    stream_labels.append(f'[s{i}]')
                
                if not stream_labels: # Should not happen if valid_files is not empty
                    print("错误：没有有效的流进行合并。")
                    return False

                concat_filter = ''.join(stream_labels) + f'concat=n={len(stream_labels)}:v=0:a=1[out]'
                filter_complex_parts.append(concat_filter)

            final_filter_complex = ';'.join(filter_complex_parts)

            cmd = [
                'ffmpeg', '-y',
                *input_parts,
                '-filter_complex', final_filter_complex,
                '-map', '[out]',
                '-ar', str(target_sample_rate),
                *codec_settings,
                output_path
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"FFmpeg执行异常: {e}")
            return False
    
    async def _combine_with_pydub(self, file_paths: List[str], output_path: str, 
                                silence_duration: int, audio_format: str) -> bool:
        """使用pydub进行音频合并"""
        start_time = time.time()
        
        try:
            from pydub import AudioSegment
            import multiprocessing as mp
            from concurrent.futures import ThreadPoolExecutor
            
            cpu_count = mp.cpu_count()
            chunk_size = max(10, len(file_paths) // (cpu_count * 2))
            
            print(f"🔧 pydub优化模式: {len(file_paths)} 个文件, 使用 {cpu_count} 核心, 分块大小: {chunk_size} (格式: {audio_format})")
            
            # 确定音频格式
            if audio_format.lower() == "wav":
                audio_loader = AudioSegment.from_wav
                export_format = "wav"
                export_params = {"parameters": ["-acodec", "pcm_s16le"]}
            else:
                audio_loader = AudioSegment.from_mp3
                export_format = "mp3"
                export_params = {"parameters": ["-q:a", "2"]}
            
            # 在线程池中执行合并
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                success = await loop.run_in_executor(
                    executor,
                    self._run_pydub_combine,
                    file_paths, output_path, silence_duration, 
                    audio_loader, export_format, export_params, chunk_size
                )
            
            if success:
                processing_time = time.time() - start_time
                print(f"✅ pydub合并完成: {len(file_paths)} 个文件, 用时 {processing_time:.2f}s")
                return True
            else:
                return False
                
        except ImportError:
            print("pydub未安装，使用简单合并方法")
            return await self._simple_combine(file_paths, output_path)
        except Exception as e:
            print(f"pydub合并失败: {e}")
            return False
    
    def _run_pydub_combine(self, file_paths: List[str], output_path: str, silence_duration: int,
                         audio_loader, export_format: str, export_params: dict, chunk_size: int) -> bool:
        """在线程中运行pydub合并"""
        try:
            from pydub import AudioSegment
            
            if len(file_paths) <= 20:
                # 直接合并
                combined = AudioSegment.empty()
                silence = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                
                for i, file_path in enumerate(file_paths):
                    if os.path.exists(file_path):
                        audio = audio_loader(file_path)
                        combined += audio
                        if silence and i < len(file_paths) - 1:
                            combined += silence
                
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    print(f"📁 创建输出目录: {output_dir}")
                
                combined.export(output_path, format=export_format, **export_params)
                
            else:
                # 分块合并
                chunks = [file_paths[i:i + chunk_size] for i in range(0, len(file_paths), chunk_size)]
                chunk_files = []
                
                # 使用临时目录存储chunk文件，避免路径中的非ASCII字符问题
                temp_dir = tempfile.mkdtemp(prefix="tts_chunks_")
                
                try:
                    # 处理每个分块
                    for chunk_idx, chunk_paths in enumerate(chunks):
                        chunk_combined = AudioSegment.empty()
                        silence = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                        
                        for i, file_path in enumerate(chunk_paths):
                            if os.path.exists(file_path):
                                audio = audio_loader(file_path)
                                chunk_combined += audio
                                if silence and i < len(chunk_paths) - 1:
                                    chunk_combined += silence
                        
                        # 保存临时分块文件到临时目录，使用安全的文件名
                        chunk_filename = f"chunk_{chunk_idx}_{uuid.uuid4().hex[:8]}.{export_format}"
                        chunk_file = os.path.join(temp_dir, chunk_filename)
                        chunk_combined.export(chunk_file, format=export_format, **export_params)
                        chunk_files.append(chunk_file)
                    
                    # 合并所有分块
                    final_combined = AudioSegment.empty()
                    silence_between_chunks = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                    
                    for i, chunk_file in enumerate(chunk_files):
                        chunk_audio = audio_loader(chunk_file)
                        final_combined += chunk_audio
                        if silence_between_chunks and i < len(chunk_files) - 1:
                            final_combined += silence_between_chunks
                    
                    # 确保输出目录存在
                    output_dir = os.path.dirname(output_path)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                        print(f"📁 创建输出目录: {output_dir}")
                    
                    final_combined.export(output_path, format=export_format, **export_params)
                    
                finally:
                    # 清理临时文件和目录
                    for chunk_file in chunk_files:
                        try:
                            if os.path.exists(chunk_file):
                                os.remove(chunk_file)
                        except Exception as e:
                            print(f"⚠️ 清理临时chunk文件失败: {chunk_file}, 错误: {e}")
                    
                    try:
                        if os.path.exists(temp_dir):
                            os.rmdir(temp_dir)
                    except Exception as e:
                        print(f"⚠️ 清理临时目录失败: {temp_dir}, 错误: {e}")
            
            return True
            
        except Exception as e:
            print(f"pydub执行异常: {e}")
            return False
    
    async def _simple_combine(self, file_paths: List[str], output_path: str) -> bool:
        """简单的二进制连接合并"""
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, self._run_simple_combine, file_paths, output_path)
            return True
        except Exception as e:
            print(f"简单合并失败: {e}")
            return False
    
    def _run_simple_combine(self, file_paths: List[str], output_path: str):
        """在线程中运行简单合并"""
        with open(output_path, 'wb') as outfile:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as infile:
                        outfile.write(infile.read())
    
    def analyze_audio_duration(self, audio_path: str) -> float:
        """分析音频文件时长"""
        try:
            from pydub import AudioSegment
            # 尝试根据文件扩展名选择加载器
            file_ext = os.path.splitext(audio_path)[1].lower()
            if file_ext == ".wav":
                audio = AudioSegment.from_wav(audio_path)
            elif file_ext == ".mp3":
                audio = AudioSegment.from_mp3(audio_path)
            else:
                # 尝试通用加载器
                audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # pydub 时长单位为毫秒
        except ImportError:
            print("⚠️ pydub未安装，无法准确分析音频时长。将根据文件大小进行粗略估算。")
            # 简单估算 (假设 128kbps MP3, 即 16KB/秒)
            file_size = os.path.getsize(audio_path)
            estimated_duration = file_size / (16 * 1024) 
            return max(0.1, estimated_duration) # 避免返回0
        except Exception as e:
            print(f"❌ 分析音频 {audio_path} 时长失败: {e}. 将根据文件大小进行粗略估算。")
            file_size = os.path.getsize(audio_path)
            estimated_duration = file_size / (16 * 1024)
            return max(0.1, estimated_duration) # 避免返回0

    async def get_audio_durations(self, audio_paths: List[str]) -> List[float]:
        """异步获取一组音频文件的时长列表"""
        durations = []
        # 在线程池中执行时长分析，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            tasks = [loop.run_in_executor(executor, self.analyze_audio_duration, path) for path in audio_paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ 获取音频 {audio_paths[i]} 时长时发生错误: {result}")
                # 对于获取失败的音频，可以根据需要返回一个默认值或标记
                # 这里我们尝试基于文件大小进行估算作为后备
                try:
                    file_size = os.path.getsize(audio_paths[i])
                    estimated_duration = file_size / (16 * 1024) # 假设 128kbps MP3
                    durations.append(max(0.1, estimated_duration))
                    print(f"   ⚠️  后备估算时长: {durations[-1]:.2f}s (基于文件大小)")
                except Exception as size_error:
                    print(f"   ❌ 无法获取文件大小进行后备估算: {size_error}")
                    durations.append(0.0) # 或其他合适的默认值
            else:
                durations.append(result)
        return durations 