#!/usr/bin/env python3
"""
TTS缓存管理工具
"""
import os
import hashlib
import shutil
import aiofiles
from typing import Optional


class TTSCache:
    """TTS缓存管理类"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def get_cache_key(self, text: str, voice: str, rate: str, volume: str, 
                     pitch: str, audio_format: str = "mp3") -> str:
        """生成缓存键"""
        cache_key_str = f"{text}-{voice}-{rate}-{volume}-{pitch}-{audio_format}"
        return hashlib.md5(cache_key_str.encode('utf-8')).hexdigest()
    
    def get_cache_path(self, cache_key: str, audio_format: str = "mp3") -> str:
        """获取缓存文件路径"""
        file_ext = "wav" if audio_format.lower() == "wav" else "mp3"
        return os.path.join(self.cache_dir, f"cache_{cache_key}.{file_ext}")
    
    def is_cached(self, cache_key: str, audio_format: str = "mp3") -> bool:
        """检查是否有缓存"""
        cache_path = self.get_cache_path(cache_key, audio_format)
        return os.path.exists(cache_path) and os.path.getsize(cache_path) > 0
    
    async def copy_from_cache(self, cache_key: str, output_path: str) -> bool:
        """从缓存复制文件"""
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"📁 创建输出目录: {output_dir}")
            
            # 从输出路径推断格式
            output_ext = os.path.splitext(output_path)[1].lower()
            audio_format = "wav" if output_ext == ".wav" else "mp3"
            
            cache_path = self.get_cache_path(cache_key, audio_format)
            
            if self.is_cached(cache_key, audio_format):
                # 使用异步文件操作提高性能
                async with aiofiles.open(cache_path, 'rb') as src:
                    content = await src.read()
                async with aiofiles.open(output_path, 'wb') as dst:
                    await dst.write(content)
                
                print(f"缓存命中: cache_{cache_key[:8]}...{output_ext}，使用缓存文件。")
                return True
        except Exception as e:
            print(f"从缓存复制文件失败: {e}")
        return False
    
    async def save_to_cache(self, cache_key: str, source_path: str):
        """保存到缓存"""
        try:
            # 确保缓存目录存在
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
                print(f"📁 创建缓存目录: {self.cache_dir}")
            
            # 从源文件路径推断格式
            source_ext = os.path.splitext(source_path)[1].lower()
            audio_format = "wav" if source_ext == ".wav" else "mp3"
            
            cache_path = self.get_cache_path(cache_key, audio_format)
            
            # 使用异步文件操作
            async with aiofiles.open(source_path, 'rb') as src:
                content = await src.read()
            async with aiofiles.open(cache_path, 'wb') as dst:
                await dst.write(content)
            
            print(f"已缓存新文件: cache_{cache_key[:8]}...{source_ext}")
        except Exception as e:
            print(f"保存到缓存失败: {e}")
    
    def clear_cache(self, max_files: int = 1000) -> int:
        """清理缓存，保留最近使用的文件"""
        try:
            cache_files = []
            for filename in os.listdir(self.cache_dir):
                if filename.startswith('cache_'):
                    file_path = os.path.join(self.cache_dir, filename)
                    if os.path.isfile(file_path):
                        mtime = os.path.getmtime(file_path)
                        cache_files.append((mtime, file_path))
            
            # 按修改时间排序，删除最旧的文件
            cache_files.sort(reverse=True)  # 最新的在前
            
            deleted_count = 0
            if len(cache_files) > max_files:
                files_to_delete = cache_files[max_files:]
                for _, file_path in files_to_delete:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except:
                        pass
            
            if deleted_count > 0:
                print(f"🧹 已清理 {deleted_count} 个旧缓存文件")
            
            return deleted_count
        except Exception as e:
            print(f"清理缓存失败: {e}")
            return 0
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        try:
            cache_files = []
            total_size = 0
            
            for filename in os.listdir(self.cache_dir):
                if filename.startswith('cache_'):
                    file_path = os.path.join(self.cache_dir, filename)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        cache_files.append(filename)
            
            return {
                'file_count': len(cache_files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_dir': self.cache_dir
            }
        except Exception as e:
            print(f"获取缓存统计失败: {e}")
            return {'file_count': 0, 'total_size_mb': 0, 'cache_dir': self.cache_dir} 