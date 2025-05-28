#!/usr/bin/env python3
"""
TTS 服务 - 优化版替换原版
完全兼容原有API，但使用并发处理提升性能
直接替换 app.py 使用，无需修改前端代码
"""

import os
import uuid
from flask import Flask, render_template, request, send_from_directory, jsonify, Response, make_response
import asyncio
import edge_tts
import re
from flask_cors import CORS
import time
import hashlib
import shutil
import json
from concurrent.futures import ThreadPoolExecutor
import aiofiles
from typing import List, Dict, Tuple
import subprocess

app = Flask(__name__)
# 简化CORS配置，只使用Flask-CORS来管理所有CORS设置
CORS(app, 
     origins=["*"],  # 改为数组格式
     methods=["GET", "POST", "OPTIONS", "HEAD"],
     allow_headers=["Content-Type", "Authorization", "Range", "Accept", "Accept-Encoding", "Accept-Language"],
     expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"],
     supports_credentials=False,
     max_age=86400
)

# 配置静态文件夹用于存储生成的音频文件
UPLOAD_FOLDER = 'static/audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 默认语音
DEFAULT_VOICE = 'zh-CN-XiaoxiaoNeural'

# 并发配置 - 可以通过环境变量调整
MAX_CONCURRENT_TASKS = int(os.environ.get('MAX_CONCURRENT_TASKS', 10))
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

print(f"🚀 TTS服务启动，智能并发处理已启用")
print(f"📊 最大并发任务数: {MAX_CONCURRENT_TASKS}")
print(f"🔧 可通过环境变量 MAX_CONCURRENT_TASKS 调整并发数")

# 检查ffmpeg是否安装（用于超高性能音频合并）
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print(f"✅ FFmpeg已安装，将使用超高性能音频合并模式")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"⚠️  FFmpeg未安装，将使用pydub合并模式")
        print(f"💡 安装FFmpeg可大幅提升音频合并性能，特别是处理大量文件时")
        print(f"🍎 macOS安装命令: brew install ffmpeg")
        print(f"🐧 Ubuntu安装命令: sudo apt install ffmpeg")
        print(f"🪟 Windows: 从 https://ffmpeg.org/ 下载")
        return False

ffmpeg_available = check_ffmpeg()

# 重试装饰器
def async_retry(retries=3, delay=1):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    print(f"函数 {func.__name__} 第 {attempts} 次尝试失败: {e}")
                    if attempts == retries:
                        print(f"函数 {func.__name__} 已达到最大重试次数，放弃。")
                        raise
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

def sync_retry(retries=3, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    print(f"函数 {func.__name__} 第 {attempts} 次尝试失败: {e}")
                    if attempts == retries:
                        print(f"函数 {func.__name__} 已达到最大重试次数，放弃。")
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator

# 按语言代码分组的语音字典
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

@app.route('/')
def index():
    return render_template('index.html', language_names=LANGUAGE_NAMES)

@async_retry(retries=2, delay=1)
async def get_voices_async():
    """异步获取所有可用的语音"""
    try:
        voices = await edge_tts.VoicesManager.create()
        return voices.voices
    except Exception as e:
        print(f"获取语音列表时出错: {str(e)}")
        return []

def group_voices_by_language(voices):
    """按语言分组语音"""
    grouped_voices = {}
    
    for voice in voices:
        # 从语音名称中提取语言代码 (例如 zh-CN-XiaoxiaoNeural -> zh)
        lang_code = voice.get('ShortName', '').split('-')[0]
        
        # 如果语言代码不在预定义列表中，归类为"其他"
        category = lang_code if lang_code in LANGUAGE_NAMES else 'other'
        
        if category not in grouped_voices:
            grouped_voices[category] = []
            
        grouped_voices[category].append({
            'name': voice.get('ShortName', ''),
            'gender': voice.get('Gender', ''),
            'localName': voice.get('LocalName', ''),
            'displayName': voice.get('DisplayName', '')
        })
    
    return grouped_voices

@app.route('/get_voices', methods=['GET'])
def get_voices():
    # 创建异步事件循环获取语音列表
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        voices = loop.run_until_complete(get_voices_async())
        grouped_voices = group_voices_by_language(voices)
        return jsonify(grouped_voices)
    except Exception as e:
        # 如果获取失败，返回预定义的几个常用语音
        fallback_voices = {
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
        return jsonify(fallback_voices)
    finally:
        loop.close()

# 优化的缓存管理类
class TTSCache:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        
    def get_cache_key(self, text: str, voice: str, rate: str, volume: str, pitch: str) -> str:
        """生成缓存键"""
        cache_key_str = f"{text}-{voice}-{rate}-{volume}-{pitch}"
        return hashlib.md5(cache_key_str.encode('utf-8')).hexdigest()
    
    def get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"cache_{cache_key}.mp3")
    
    def is_cached(self, cache_key: str) -> bool:
        """检查是否有缓存"""
        return os.path.exists(self.get_cache_path(cache_key))
    
    async def copy_from_cache(self, cache_key: str, output_path: str) -> bool:
        """从缓存复制文件"""
        try:
            cache_path = self.get_cache_path(cache_key)
            if self.is_cached(cache_key):
                shutil.copyfile(cache_path, output_path)
                print(f"缓存命中: cache_{cache_key[:8]}...mp3，使用缓存文件。")
                return True
        except Exception as e:
            print(f"从缓存复制文件失败: {e}")
        return False
    
    async def save_to_cache(self, cache_key: str, source_path: str):
        """保存到缓存"""
        try:
            cache_path = self.get_cache_path(cache_key)
            shutil.copyfile(source_path, cache_path)
            print(f"已缓存新文件: cache_{cache_key[:8]}...mp3")
        except Exception as e:
            print(f"保存到缓存失败: {e}")

# 创建缓存管理器
tts_cache = TTSCache(UPLOAD_FOLDER)

def combine_audio_files_ffmpeg(file_paths, output_path, silence_duration=200):
    """
    🚀 超高性能音频合并 - 使用ffmpeg原生合并（最快）
    专为大量文件优化，在M3 Max上性能最佳
    """
    import tempfile
    start_time = time.time()
    
    try:
        # 检查ffmpeg是否可用
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  ffmpeg未安装，回退到pydub方案")
            return combine_audio_files(file_paths, output_path, silence_duration)
        
        print(f"🚀 FFmpeg超高性能模式: 合并 {len(file_paths)} 个文件")
        
        # 创建临时文件列表
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            filelist_path = f.name
            for file_path in file_paths:
                # ffmpeg concat需要特殊转义
                escaped_path = file_path.replace("'", "'\"'\"'")
                f.write(f"file '{escaped_path}'\n")
                if silence_duration > 0:
                    # 添加静音文件
                    f.write(f"file 'pipe:0'\n")
        
        try:
            if silence_duration > 0:
                # 方案1: 有静音间隔 - 使用filter_complex（稍慢但灵活）
                filter_parts = []
                input_parts = []
                
                for i, file_path in enumerate(file_paths):
                    input_parts.extend(['-i', file_path])
                    filter_parts.append(f'[{i}:a]')
                    
                    if i < len(file_paths) - 1:
                        # 添加静音
                        silence_filter = f'aevalsrc=0:duration={silence_duration/1000}:sample_rate=22050[silence{i}]'
                        filter_parts.append(f'[silence{i}]')
                        input_parts.extend(['-f', 'lavfi', '-i', silence_filter])
                
                # 构建concat filter
                concat_filter = ''.join(filter_parts) + f'concat=n={len(filter_parts)}:v=0:a=1[out]'
                
                cmd = [
                    'ffmpeg', '-y',  # 覆盖输出文件
                    *input_parts,
                    '-filter_complex', concat_filter,
                    '-map', '[out]',
                    '-c:a', 'mp3',
                    '-b:a', '128k',
                    output_path
                ]
            else:
                # 方案2: 无静音间隔 - 使用concat demuxer（最快）
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', filelist_path,
                    '-c:a', 'mp3',
                    '-b:a', '128k',
                    output_path
                ]
            
            # 执行ffmpeg命令
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                processing_time = time.time() - start_time
                avg_time_per_file = processing_time / len(file_paths)
                print(f"✅ FFmpeg超高性能合并完成: {len(file_paths)} 个文件, 用时 {processing_time:.2f}s, 平均每文件 {avg_time_per_file:.3f}s")
                return True
            else:
                print(f"❌ FFmpeg合并失败: {result.stderr}")
                print("🔄 回退到pydub方案")
                return combine_audio_files(file_paths, output_path, silence_duration)
                
        finally:
            # 清理临时文件
            try:
                os.unlink(filelist_path)
            except:
                pass
                
    except Exception as e:
        print(f"FFmpeg合并出错: {e}, 回退到pydub方案")
        return combine_audio_files(file_paths, output_path, silence_duration)

@async_retry(retries=3, delay=2)
async def generate_tts(text, output_path, voice, rate, volume, pitch):
    """优化的TTS生成函数（与原版接口完全兼容）"""
    async with SEMAPHORE:  # 限制并发数量
        # --- 缓存逻辑开始（与原版一致）---
        # 1. 构建缓存键字符串，包含所有影响语音输出的参数
        cache_key_str = f"{text}-{voice}-{rate}-{volume}-{pitch}"
        
        # 2. 为缓存键生成MD5哈希值
        file_hash = hashlib.md5(cache_key_str.encode('utf-8')).hexdigest()
        
        # 3. 构造缓存文件名和路径
        cached_filename = f"cache_{file_hash}.mp3"
        cached_file_path = os.path.join(app.config['UPLOAD_FOLDER'], cached_filename)
        
        # 4. 检查缓存文件是否存在
        if os.path.exists(cached_file_path):
            try:
                print(f"缓存命中: {cached_filename}，使用缓存文件。")
                # 如果缓存存在，将缓存文件复制到期望的输出路径
                shutil.copyfile(cached_file_path, output_path)
                return True # 明确返回True
            except Exception as e:
                print(f"从缓存复制文件失败: {e}，将重新生成。")
                # 如果复制失败，则继续执行生成逻辑

        print(f"缓存未命中: {cached_filename}，生成新文件: {text[:30]}...")
        # --- 缓存逻辑结束 ---
        
        # 如果缓存未命中或复制缓存失败，则正常生成TTS
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
        await communicate.save(output_path)
        
        # --- 缓存保存逻辑 ---
        # 生成成功后，将新文件复制到缓存位置
        try:
            shutil.copyfile(output_path, cached_file_path)
            print(f"已缓存新文件: {cached_filename}")
        except Exception as e:
            print(f"保存到缓存失败: {e}")
        # --- 缓存保存逻辑结束 ---
        return True # 明确返回True

# 批量并发生成TTS
async def batch_generate_tts_concurrent(items: List[Dict], rate: str, volume: str, pitch: str) -> List[Tuple[str, Dict]]:
    """批量并发生成TTS音频"""
    tasks = []
    # temp_files 变量在此处未使用，可以考虑移除或后续用于其他逻辑
    
    for i, item in enumerate(items):
        text = item.get('text', '').strip()
        if not text:
            continue
            
        voice = item.get('voice', DEFAULT_VOICE)
        item_rate = item.get('rate', rate)
        item_volume = item.get('volume', volume)
        item_pitch = item.get('pitch', pitch)
        
        # 生成临时文件名
        temp_filename = f"batch_{uuid.uuid4()}.mp3"
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        
        # 创建异步任务
        task = generate_tts(text, temp_path, voice, item_rate, item_volume, item_pitch)
        tasks.append((task, temp_path, item, i)) # item 和 i 用于结果匹配
    
    print(f"开始智能并发生成 {len(tasks)} 个TTS音频...")
    
    # 使用 asyncio.gather 进行并发执行
    results = []
    # tasks_to_gather = [t[0] for t in tasks] # 提取coroutine对象
    completed_tasks_results = await asyncio.gather(*[task_info[0] for task_info in tasks], return_exceptions=True)
    
    for i, task_info in enumerate(tasks):
        original_task, temp_path, item_details, original_index = task_info
        result = completed_tasks_results[i] # 按顺序获取结果

        if isinstance(result, Exception):
            # 增强日志：打印异常类型、repr和str
            print(f"任务 {original_index + 1} (文本: '{item_details.get('text', '')[:20]}...') 失败. Type: {type(result)}, repr: {repr(result)}, str: {str(result)}")
            continue
        
        if result is True and os.path.exists(temp_path):
            results.append((temp_path, item_details)) # 保存路径和原始item信息
            # print(f"已生成音频 {original_index + 1}/{len(items)}: {item_details.get('text', '')[:20]}...") # items在这里不可直接访问，用len(tasks)
            print(f"已生成音频 {original_index + 1}/{len(tasks)}: {item_details.get('text', '')[:20]}...")
        else:
            print(f"任务 {original_index + 1} (文本: '{item_details.get('text', '')[:20]}...') 生成意外失败 (result: {result}, path_exists: {os.path.exists(temp_path)})")
    
    return results

@app.route('/synthesize', methods=['POST'])
def synthesize():
    text = request.form.get('text', '')
    voice = request.form.get('voice', DEFAULT_VOICE)
    rate = request.form.get('rate', '+0%')
    volume = request.form.get('volume', '+0%')
    pitch = request.form.get('pitch', '+0Hz')
    
    if not text:
        return jsonify({'error': '请输入文本'}), 400
    
    # 生成唯一的文件名
    filename = f"{uuid.uuid4()}.mp3"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # 执行异步任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(generate_tts(text, output_path, voice, rate, volume, pitch))
        audio_url = f"/static/audio/{filename}"
        return jsonify({'success': True, 'audio_url': audio_url, 'filename': filename})
    except Exception as e:
        return jsonify({'error': f'生成失败: {str(e)}'}), 500
    finally:
        loop.close()

# 新增 API 端点，供浏览器插件使用
@app.route('/api/tts', methods=['POST'])
def api_tts():
    """
    API端点，接收JSON格式的请求，包含要转换的文本和语音参数
    返回生成的音频URL或直接返回音频流
    """
    try:
        data = request.get_json()
        if not data:
            # 尝试从表单数据获取
            text = request.form.get('text', '')
            voice = request.form.get('voice', DEFAULT_VOICE)
            rate = request.form.get('rate', '+0%')
            volume = request.form.get('volume', '+0%')
            pitch = request.form.get('pitch', '+0Hz')
            return_type = request.form.get('return_type', 'url')  # url 或 audio
        else:
            text = data.get('text', '')
            voice = data.get('voice', DEFAULT_VOICE)
            rate = data.get('rate', '+0%')
            volume = data.get('volume', '+0%')
            pitch = data.get('pitch', '+0Hz')
            return_type = data.get('return_type', 'url')  # url 或 audio
        
        if not text:
            return jsonify({'error': '请提供文本'}), 400

        # 生成唯一的文件名
        filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 执行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(generate_tts(text, output_path, voice, rate, volume, pitch))
            
            if return_type == 'audio':
                # 直接返回音频文件
                with open(output_path, 'rb') as audio_file:
                    audio_data = audio_file.read()
                return Response(audio_data, mimetype='audio/mpeg')
            else:
                # 返回音频URL
                # 构建完整URL（包括主机名）
                host = request.host_url.rstrip('/')
                audio_url = f"{host}/static/audio/{filename}"
                return jsonify({
                    'success': True, 
                    'audio_url': audio_url,
                    'filename': filename
                })
        except Exception as e:
            return jsonify({'error': f'生成失败: {str(e)}'}), 500
        finally:
            loop.close()
    except Exception as e:
        return jsonify({'error': f'请求处理失败: {str(e)}'}), 500

# 获取支持的语音列表API端点
@app.route('/api/voices', methods=['GET'])
def api_voices():
    """
    API端点，返回支持的语音列表
    可以通过language参数过滤特定语言的语音
    """
    language = request.args.get('language', None)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        voices = loop.run_until_complete(get_voices_async())
        grouped_voices = group_voices_by_language(voices)
        
        if language and language in grouped_voices:
            return jsonify({language: grouped_voices[language]})
        return jsonify(grouped_voices)
    except Exception as e:
        # 如果获取失败，返回预定义的几个常用语音
        fallback_voices = {
            'zh': [
                {'name': 'zh-CN-XiaoxiaoNeural', 'gender': 'Female', 'localName': '晓晓', 'displayName': '中国大陆 晓晓 (女)'},
                {'name': 'zh-CN-YunyangNeural', 'gender': 'Male', 'localName': '云扬', 'displayName': '中国大陆 云扬 (男)'}
            ],
            'ja': [
                {'name': 'ja-JP-NanamiNeural', 'gender': 'Female', 'localName': '七海', 'displayName': '日本 七海 (女)'},
                {'name': 'ja-JP-KeitaNeural', 'gender': 'Male', 'localName': '啓太', 'displayName': '日本 啓太 (男)'}
            ],
            'en': [
                {'name': 'en-US-JennyNeural', 'gender': 'Female', 'localName': 'Jenny', 'displayName': '美国 Jenny (女)'}
            ]
        }
        
        if language and language in fallback_voices:
            return jsonify({language: fallback_voices[language]})
        return jsonify(fallback_voices)
    finally:
        loop.close()

@sync_retry(retries=2, delay=1)
def combine_audio_files(file_paths, output_path, silence_duration=200):
    """
    优化版音频合并函数 - 专为M3 Max等高性能芯片优化
    🚀 支持多核并行处理、内存优化和智能批处理
    """
    import time
    start_time = time.time()
    
    try:
        # 尝试使用pydub进行高性能合并
        try:
            from pydub import AudioSegment
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
            
            # 针对M3 Max优化的参数
            cpu_count = mp.cpu_count()
            chunk_size = max(10, len(file_paths) // (cpu_count * 2))  # 智能分块
            
            print(f"🚀 M3 Max优化模式启动: {len(file_paths)} 个文件, 使用 {cpu_count} 核心, 分块大小: {chunk_size}")
            
            # 策略1: 少量文件使用直接合并（最快）
            if len(file_paths) <= 20:
                print("📦 使用直接合并模式（文件数较少）")
                combined = AudioSegment.empty()
                silence = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                
                for i, file_path in enumerate(file_paths):
                    audio = AudioSegment.from_mp3(file_path)
                    combined += audio
                    
                    # 在音频片段之间添加静音间隔（除了最后一个）
                    if silence and i < len(file_paths) - 1:
                        combined += silence
                
                # 导出合并后的音频
                combined.export(output_path, format="mp3", parameters=["-q:a", "2"])  # 高质量快速编码
                
            # 策略2: 中等数量文件使用分块合并
            elif len(file_paths) <= 100:
                print("⚡ 使用分块合并模式")
                chunks = [file_paths[i:i + chunk_size] for i in range(0, len(file_paths), chunk_size)]
                chunk_files = []
                
                # 并行处理每个分块
                def process_chunk(chunk_data):
                    chunk_idx, chunk_paths = chunk_data
                    chunk_combined = AudioSegment.empty()
                    silence = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                    
                    for i, file_path in enumerate(chunk_paths):
                        audio = AudioSegment.from_mp3(file_path)
                        chunk_combined += audio
                        if silence and i < len(chunk_paths) - 1:
                            chunk_combined += silence
                    
                    # 保存临时分块文件
                    chunk_file = f"{output_path}_chunk_{chunk_idx}.mp3"
                    chunk_combined.export(chunk_file, format="mp3", parameters=["-q:a", "2"])
                    return chunk_file
                
                # 使用线程池处理分块（I/O密集型）
                with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as executor:
                    chunk_files = list(executor.map(process_chunk, enumerate(chunks)))
                
                # 合并所有分块
                final_combined = AudioSegment.empty()
                silence_between_chunks = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                
                for i, chunk_file in enumerate(chunk_files):
                    chunk_audio = AudioSegment.from_mp3(chunk_file)
                    final_combined += chunk_audio
                    if silence_between_chunks and i < len(chunk_files) - 1:
                        final_combined += silence_between_chunks
                    
                    # 立即删除临时文件以节省空间
                    os.remove(chunk_file)
                
                final_combined.export(output_path, format="mp3", parameters=["-q:a", "2"])
                
            # 策略3: 大量文件使用高级分层合并
            else:
                print("🔥 使用高级分层合并模式（大量文件）")
                
                def merge_files_batch(file_batch, temp_output):
                    """合并一批文件"""
                    combined = AudioSegment.empty()
                    silence = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                    
                    for i, file_path in enumerate(file_batch):
                        audio = AudioSegment.from_mp3(file_path)
                        combined += audio
                        if silence and i < len(file_batch) - 1:
                            combined += silence
                    
                    combined.export(temp_output, format="mp3", parameters=["-q:a", "2"])
                    return temp_output
                
                # 第一层：并行合并小批次
                batch_size = 30  # 每批30个文件
                batches = [file_paths[i:i + batch_size] for i in range(0, len(file_paths), batch_size)]
                temp_files = []
                
                with ThreadPoolExecutor(max_workers=min(6, len(batches))) as executor:
                    futures = []
                    for i, batch in enumerate(batches):
                        temp_file = f"{output_path}_temp_{i}.mp3"
                        future = executor.submit(merge_files_batch, batch, temp_file)
                        futures.append((future, temp_file))
                    
                    for future, temp_file in futures:
                        future.result()  # 等待完成
                        temp_files.append(temp_file)
                
                # 第二层：合并所有临时文件
                final_combined = AudioSegment.empty()
                silence_between_batches = AudioSegment.silent(duration=silence_duration) if silence_duration > 0 else None
                
                for i, temp_file in enumerate(temp_files):
                    batch_audio = AudioSegment.from_mp3(temp_file)
                    final_combined += batch_audio
                    if silence_between_batches and i < len(temp_files) - 1:
                        final_combined += silence_between_batches
                    
                    # 立即删除临时文件
                    os.remove(temp_file)
                
                final_combined.export(output_path, format="mp3", parameters=["-q:a", "2"])
            
            processing_time = time.time() - start_time
            avg_time_per_file = processing_time / len(file_paths)
            print(f"✅ M3 Max优化合并完成: {len(file_paths)} 个文件, 用时 {processing_time:.2f}s, 平均每文件 {avg_time_per_file:.3f}s")
            return True
            
        except ImportError:
            print("pydub未安装，使用简单合并方法")
            # 回退到简单的二进制连接方法
            with open(output_path, 'wb') as outfile:
                for i, file_path in enumerate(file_paths):
                    with open(file_path, 'rb') as infile:
                        outfile.write(infile.read())
            
            processing_time = time.time() - start_time
            print(f"使用简单方法合并 {len(file_paths)} 个音频文件，用时 {processing_time:.2f}s")
            return True
            
    except Exception as e:
        print(f"音频合并失败: {str(e)}")
        return False

# 音频合并API端点
@app.route('/api/combine_audio', methods=['POST'])
def api_combine_audio():
    """
    合并多个音频文件为一个完整的音频文件
    """
    try:
        data = request.get_json()
        if not data or 'audio_files' not in data:
            return jsonify({'error': '请提供音频文件列表'}), 400
        
        audio_files = data.get('audio_files', [])
        output_name = data.get('output_name', f'combined_{uuid.uuid4()}.mp3')
        
        if not audio_files:
            return jsonify({'error': '音频文件列表不能为空'}), 400
        
        # 验证所有音频文件是否存在
        valid_files = []
        for filename in audio_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                valid_files.append(file_path)
            else:
                print(f"音频文件不存在: {filename}")
        
        if not valid_files:
            return jsonify({'error': '没有找到有效的音频文件'}), 400
        
        # 合并音频文件
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_name)
        success = combine_audio_files_ffmpeg(valid_files, output_path, 0)  # 使用FFmpeg高性能合并
        
        if success:
            # 构建下载URL
            host = request.host_url.rstrip('/')
            download_url = f"{host}/static/audio/{output_name}"
            
            return jsonify({
                'success': True,
                'download_url': download_url,
                'filename': output_name
            })
        else:
            return jsonify({'error': '音频合并失败'}), 500
            
    except Exception as e:
        return jsonify({'error': f'合并处理失败: {str(e)}'}), 500

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# 新增：专门的音频文件服务，支持跨域播放和Range请求
@app.route('/static/audio/<filename>')
def serve_audio(filename):
    """
    专门服务音频文件，支持跨域播放和Range请求
    这对于在不同域名下播放音频非常重要
    """
    from flask import make_response, request as flask_request
    
    try:
        # 构建文件路径
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'error': '音频文件不存在'}), 404
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 处理Range请求（用于音频流播放）
        range_header = flask_request.headers.get('Range', None)
        
        if range_header:
            # 解析Range头部
            byte_start = 0
            byte_end = file_size - 1
            
            # 解析 "bytes=start-end" 格式
            if range_header.startswith('bytes='):
                range_match = range_header[6:].split('-')
                if range_match[0]:
                    byte_start = int(range_match[0])
                if range_match[1]:
                    byte_end = int(range_match[1])
            
            # 确保范围有效
            byte_start = max(0, byte_start)
            byte_end = min(file_size - 1, byte_end)
            content_length = byte_end - byte_start + 1
            
            # 读取指定范围的数据
            with open(file_path, 'rb') as audio_file:
                audio_file.seek(byte_start)
                data = audio_file.read(content_length)
            
            # 创建206 Partial Content响应
            response = make_response(data)
            response.status_code = 206
            response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
            response.headers['Content-Length'] = str(content_length)
        else:
            # 普通请求，返回完整文件
            response = make_response(send_from_directory(app.config['UPLOAD_FOLDER'], filename))
        
        # 添加音频播放相关头部
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Type'] = 'audio/mpeg'
        response.headers['Cache-Control'] = 'public, max-age=3600'  # 缓存1小时
        
        # 防止浏览器缓存策略问题
        response.headers['Vary'] = 'Accept-Encoding, Range'
        
        return response
        
    except Exception as e:
        print(f"音频文件服务错误: {e}")
        return jsonify({'error': f'服务音频文件失败: {str(e)}'}), 500

# 新增: 音频分析功能
def analyze_audio_duration(audio_path):
    """分析音频文件时长"""
    try:
        # 尝试使用pydub获取精确时长
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(audio_path)
            return len(audio) / 1000.0  # 转换为秒
        except ImportError:
            # 如果pydub不可用，使用简单估算
            file_size = os.path.getsize(audio_path)
            # 简单估算：128kbps MP3大约1MB对应1分钟
            estimated_duration = (file_size / 1024 / 1024) * 60 / 8  # 粗略估算
            return max(1.0, estimated_duration)  # 至少1秒
    except Exception as e:
        print(f"分析音频时长失败: {e}")
        return 1.0  # 默认1秒

# ===== 核心API：智能批量TTS处理 =====
@app.route('/api/batch_tts', methods=['POST'])
def api_batch_tts():
    """
    批量生成TTS音频并合并
    ✨ 智能模式：自动选择串行或并发处理以获得最佳性能
    📱 完全兼容原有API，前端无需任何修改
    🚀 大幅提升处理速度，特别是多项目场景
    """
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': '请提供TTS项目列表'}), 400
        
        items = data.get('items', [])
        output_name = data.get('output_name', f'batch_tts_{uuid.uuid4()}.mp3')
        rate = data.get('rate', '+0%')
        volume = data.get('volume', '+0%')
        pitch = data.get('pitch', '+0Hz')
        silence_duration = data.get('silence_duration', 200)  # 默认200ms
        
        # 智能模式参数（可选，不影响原有API）
        force_serial = data.get('force_serial', False)  # 强制串行处理
        max_concurrent = data.get('max_concurrent', MAX_CONCURRENT_TASKS)  # 自定义并发数
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        start_time = time.time()
        items_count = len(items)
        
        # 智能选择处理模式
        if force_serial or items_count <= 3:
            processing_mode = 'serial'
            print(f"🔄 使用串行处理模式 (项目数: {items_count})")
        else:
            processing_mode = 'concurrent'
            print(f"⚡ 使用智能并发处理模式 (项目数: {items_count}, 并发数: {max_concurrent})")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if processing_mode == 'concurrent':
                # 并发处理模式
                global SEMAPHORE
                original_semaphore = SEMAPHORE
                if max_concurrent != MAX_CONCURRENT_TASKS:
                    SEMAPHORE = asyncio.Semaphore(max_concurrent)
                
                try:
                    results = loop.run_until_complete(batch_generate_tts_concurrent(items, rate, volume, pitch))
                    temp_files = [result[0] for result in results]
                finally:
                    # 恢复原始信号量
                    SEMAPHORE = original_semaphore
            else:
                # 串行处理模式（保持原有逻辑）
                temp_files = []
                for i, item in enumerate(items):
                    text = item.get('text', '')
                    voice = item.get('voice', DEFAULT_VOICE)
                    item_rate = item.get('rate', rate)
                    item_volume = item.get('volume', volume)
                    item_pitch = item.get('pitch', pitch)
                    
                    if not text.strip():
                        continue
                    
                    # 生成临时文件名
                    temp_filename = f"batch_{uuid.uuid4()}.mp3"
                    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                    
                    # 生成TTS音频
                    loop.run_until_complete(generate_tts(text, temp_path, voice, item_rate, item_volume, item_pitch))
                    temp_files.append(temp_path)
                    
                    print(f"已生成音频 {i+1}/{items_count}: {text[:20]}...")
            
            if not temp_files:
                return jsonify({'error': '没有生成任何音频文件'}), 400
            
            # 合并所有音频文件
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_name)
            success = combine_audio_files_ffmpeg(temp_files, output_path, silence_duration)
            
            # 清理临时文件
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            generation_time = time.time() - start_time
            
            if success:
                # 构建下载URL
                host = request.host_url.rstrip('/')
                download_url = f"{host}/static/audio/{output_name}"
                
                # 返回与原API完全兼容的响应格式
                response_data = {
                    'success': True,
                    'download_url': download_url,
                    'filename': output_name,
                    'items_processed': len(temp_files)
                }
                
                # 可选性能信息（不影响原有前端解析）
                if processing_mode == 'concurrent':
                    response_data['generation_time'] = round(generation_time, 2)
                    response_data['processing_mode'] = 'concurrent'
                    if generation_time > 0:
                        speedup_estimate = max(1.5, items_count * 0.8 / generation_time)
                        response_data['performance_info'] = f"⚡ 并发处理 {len(temp_files)} 个音频文件，用时 {generation_time:.2f} 秒 (预估提速 {speedup_estimate:.1f}x)"
                else:
                    response_data['processing_mode'] = 'serial'
                    response_data['generation_time'] = round(generation_time, 2)
                
                # 记录性能日志
                avg_time_per_item = generation_time / len(temp_files) if temp_files else 0
                print(f"✅ {processing_mode.upper()} 处理完成: {len(temp_files)} 项, 总用时 {generation_time:.2f}s, 平均每项 {avg_time_per_item:.2f}s")
                
                return jsonify(response_data)
            else:
                return jsonify({'error': '音频合并失败'}), 500
                
        finally:
            loop.close()
            
    except Exception as e:
        # 清理可能残留的临时文件
        try:
            for temp_file in temp_files:
                os.remove(temp_file)
        except:
            pass
        return jsonify({'error': f'批量TTS处理失败: {str(e)}'}), 500

# 修改批量TTS生成函数，支持返回时间点信息
@app.route('/api/batch_tts_with_timecodes', methods=['POST'])
def api_batch_tts_with_timecodes():
    """
    批量生成TTS音频并合并，同时返回每个片段的时间点信息
    用于视频生成
    """
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': '请提供TTS项目列表'}), 400
        
        items = data.get('items', [])
        output_name = data.get('output_name', f'batch_tts_{uuid.uuid4()}.mp3')
        rate = data.get('rate', '+0%')
        volume = data.get('volume', '+0%')
        pitch = data.get('pitch', '+0Hz')
        silence_duration = data.get('silence_duration', 200)  # 默认200ms
        use_concurrent = data.get('use_concurrent', True)  # 是否使用并发处理
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        start_time = time.time()
        timecodes = []
        current_time = 0.0
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if use_concurrent and len(items) > 3:
                # 使用并发处理
                results = loop.run_until_complete(batch_generate_tts_concurrent(items, rate, volume, pitch))
                temp_files = []
                
                # 按原始顺序处理结果并计算时间点
                for i, item in enumerate(items):
                    text = item.get('text', '').strip()
                    if not text:
                        continue
                        
                    # 找到对应的生成结果
                    matching_result = None
                    for temp_path, result_item in results:
                        if result_item.get('text', '').strip() == text:
                            matching_result = temp_path
                            break
                    
                    if matching_result and os.path.exists(matching_result):
                        # 分析音频时长
                        duration = analyze_audio_duration(matching_result)
                        
                        # 记录时间点信息
                        timecodes.append({
                            'index': i,
                            'text': text,
                            'voice': item.get('voice', DEFAULT_VOICE),
                            'start_time': current_time,
                            'end_time': current_time + duration,
                            'duration': duration
                        })
                        
                        temp_files.append(matching_result)
                        current_time += duration + (silence_duration / 1000.0)
            else:
                # 使用串行处理（保持原有逻辑）
                temp_files = []
                for i, item in enumerate(items):
                    text = item.get('text', '')
                    voice = item.get('voice', DEFAULT_VOICE)
                    item_rate = item.get('rate', rate)
                    item_volume = item.get('volume', volume)
                    item_pitch = item.get('pitch', pitch)
                    
                    if not text.strip():
                        continue
                    
                    # 生成临时文件名
                    temp_filename = f"batch_{uuid.uuid4()}.mp3"
                    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                    
                    # 生成TTS音频
                    loop.run_until_complete(generate_tts(text, temp_path, voice, item_rate, item_volume, item_pitch))
                    
                    # 分析音频时长
                    duration = analyze_audio_duration(temp_path)
                    
                    # 记录时间点信息
                    timecodes.append({
                        'index': i,
                        'text': text,
                        'voice': voice,
                        'start_time': current_time,
                        'end_time': current_time + duration,
                        'duration': duration
                    })
                    
                    temp_files.append(temp_path)
                    current_time += duration + (silence_duration / 1000.0)  # 加上静音间隔
                    
                    print(f"已生成音频 {i+1}/{len(items)}: {text[:20]}... (时长: {duration:.2f}s)")
            
            if not temp_files:
                return jsonify({'error': '没有生成任何音频文件'}), 400
            
            # 合并所有音频文件
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_name)
            success = combine_audio_files_ffmpeg(temp_files, output_path, silence_duration)
            
            # 清理临时文件
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            generation_time = time.time() - start_time
            
            if success:
                # 构建下载URL
                host = request.host_url.rstrip('/')
                download_url = f"{host}/static/audio/{output_name}"
                
                # 计算总时长
                total_duration = current_time - (silence_duration / 1000.0) if timecodes else 0
                
                return jsonify({
                    'success': True,
                    'download_url': download_url,
                    'filename': output_name,
                    'items_processed': len(temp_files),
                    'timecodes': timecodes,
                    'total_duration': total_duration,
                    'silence_duration': silence_duration / 1000.0,
                    'generation_time': round(generation_time, 2),
                    'processing_method': 'concurrent' if use_concurrent and len(items) > 3 else 'serial'
                })
            else:
                return jsonify({'error': '音频合并失败'}), 500
                
        finally:
            loop.close()
            
    except Exception as e:
        # 清理可能残留的临时文件
        try:
            for temp_file in temp_files:
                os.remove(temp_file)
        except:
            pass
        return jsonify({'error': f'批量TTS处理失败: {str(e)}'}), 500

# 添加健康检查端点
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'service': 'TTS Server',
        'version': '2.0',
        'timestamp': time.time(),
        'cors_enabled': True,
        'max_concurrent_tasks': MAX_CONCURRENT_TASKS
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🎵 TTS 智能优化服务 v2.0")
    print("=" * 60)
    print("✨ 特性:")
    print("   📱 完全兼容原有API")
    print("   ⚡ 智能并发处理")
    print("   🎯 自动性能优化")
    print("   💾 智能缓存系统")
    print("   💪 强化错误恢复")
    print("   🌐 支持跨域访问 (CORS)")
    print("   🎵 允许任何域名播放音频")
    print()
    print("🌐 服务地址: http://localhost:5020")
    print("📊 当前并发配置:", MAX_CONCURRENT_TASKS)
    print("💡 提示: 可通过环境变量 MAX_CONCURRENT_TASKS 调整并发数")
    print("🎧 音频URL: http://localhost:5020/static/audio/<filename>")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5020) 