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
                                silence_duration: int = 200, 
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
            if silence_duration > 0:
                # 有静音间隔的合并
                filter_parts = []
                input_parts = []
                
                for i, file_path in enumerate(valid_files):
                    input_parts.extend(['-i', file_path])
                    filter_parts.append(f'[{i}:a]aresample={target_sample_rate}') # 确保输入被重采样到目标采样率
                    
                    if i < len(valid_files) - 1:
                        silence_input_idx = len(valid_files) + i
                        # 使用目标采样率生成静音
                        silence_filter_str = f'aevalsrc=0:duration={silence_duration/1000}:sample_rate={target_sample_rate}'
                        input_parts.extend(['-f', 'lavfi', '-i', silence_filter_str])
                        filter_parts.append(f'[{silence_input_idx}:a]')
                
                concat_filter = ''.join(filter_parts) + f'concat=n={len(filter_parts)}:v=0:a=1[out]'
                
                cmd = [
                    'ffmpeg', '-y',
                    *input_parts,
                    '-filter_complex', concat_filter,
                    '-map', '[out]',
                    '-ar', str(target_sample_rate), # 确保输出采样率
                    *codec_settings,
                    output_path
                ]
            else:
                # 无静音间隔的合并
                # 对于concat demuxer，FFmpeg通常会尝试使用第一个输入的参数。
                # 为了确保48kHz，我们可以对每个输入进行预处理或在filter_complex中处理，
                # 但更简单的方式是确保所有输入片段已经是48kHz。
                # 如果之前的步骤已确保所有片段为48kHz WAV，此处的concat应该能正确工作。
                # 我们也可以在最后加 -ar 48000 强制输出采样率
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                    filelist_path = f.name
                    for file_path in valid_files:
                        abs_path = os.path.abspath(file_path)
                        escaped_path = abs_path.replace("'", r"\'").replace('"', r'\"')
                        # FFmpeg的concat demuxer需要文件路径。如果文件本身不是48kHz，这里不会自动转换。
                        # 假设上游缓存的文件已经是48kHz。
                        f.write(f"file '{escaped_path}'\n")
                
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', filelist_path,
                    '-ar', str(target_sample_rate), # 强制输出采样率为48000Hz
                    *codec_settings,
                    output_path
                ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # 清理临时文件
            if silence_duration == 0 and 'filelist_path' in locals():
                try:
                    os.unlink(filelist_path)
                except:
                    pass
            
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
                
                combined.export(output_path, format=export_format, **export_params)
                
            else:
                # 分块合并
                chunks = [file_paths[i:i + chunk_size] for i in range(0, len(file_paths), chunk_size)]
                chunk_files = []
                
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
                    
                    # 保存临时分块文件
                    chunk_file = f"{output_path}_chunk_{chunk_idx}.{export_format}"
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
                    
                    # 删除临时文件
                    os.remove(chunk_file)
                
                final_combined.export(output_path, format=export_format, **export_params)
            
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
            audio = AudioSegment.from_mp3(audio_path)
            return len(audio) / 1000.0
        except ImportError:
            # 简单估算
            file_size = os.path.getsize(audio_path)
            estimated_duration = (file_size / 1024 / 1024) * 60 / 8
            return max(1.0, estimated_duration)
        except Exception as e:
            print(f"分析音频时长失败: {e}")
            return 1.0 