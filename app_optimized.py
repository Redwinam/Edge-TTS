import os
import uuid
from flask import Flask, render_template, request, send_from_directory, jsonify, Response
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

app = Flask(__name__)
# 启用CORS，允许跨域请求，这对浏览器插件调用API很重要
CORS(app)

# 配置静态文件夹用于存储生成的音频文件
UPLOAD_FOLDER = 'static/audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 默认语音
DEFAULT_VOICE = 'zh-CN-XiaoxiaoNeural'

# 并发配置
MAX_CONCURRENT_TASKS = 10  # 最大并发任务数
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

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
                print(f"缓存命中: cache_{cache_key}.mp3，使用缓存文件。")
                return True
        except Exception as e:
            print(f"从缓存复制文件失败: {e}")
        return False
    
    async def save_to_cache(self, cache_key: str, source_path: str):
        """保存到缓存"""
        try:
            cache_path = self.get_cache_path(cache_key)
            shutil.copyfile(source_path, cache_path)
            print(f"已缓存新文件: cache_{cache_key}.mp3")
        except Exception as e:
            print(f"保存到缓存失败: {e}")

# 创建缓存管理器
tts_cache = TTSCache(UPLOAD_FOLDER)

@async_retry(retries=3, delay=2)
async def generate_tts_concurrent(text: str, output_path: str, voice: str, rate: str, volume: str, pitch: str):
    """并发安全的TTS生成函数"""
    async with SEMAPHORE:  # 限制并发数量
        # 检查缓存
        cache_key = tts_cache.get_cache_key(text, voice, rate, volume, pitch)
        
        if await tts_cache.copy_from_cache(cache_key, output_path):
            return True
        
        print(f"缓存未命中: cache_{cache_key}.mp3，生成新文件。")
        
        # 生成TTS
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
        await communicate.save(output_path)
        
        # 保存到缓存
        await tts_cache.save_to_cache(cache_key, output_path)
        return True

# 批量并发生成TTS
async def batch_generate_tts_concurrent(items: List[Dict], rate: str, volume: str, pitch: str) -> List[Tuple[str, Dict]]:
    """批量并发生成TTS音频"""
    tasks = []
    temp_files = []
    
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
        task = generate_tts_concurrent(text, temp_path, voice, item_rate, item_volume, item_pitch)
        tasks.append((task, temp_path, item, i))
    
    print(f"开始并发生成 {len(tasks)} 个TTS音频...")
    
    # 使用 asyncio.gather 进行并发执行
    results = []
    completed_tasks = await asyncio.gather(*[task[0] for task in tasks], return_exceptions=True)
    
    for i, (result, (_, temp_path, item, index)) in enumerate(zip(completed_tasks, tasks)):
        if isinstance(result, Exception):
            print(f"任务 {index+1} 失败: {result}")
            continue
        
        if result and os.path.exists(temp_path):
            results.append((temp_path, item))
            print(f"已生成音频 {index+1}/{len(items)}: {item.get('text', '')[:20]}...")
        else:
            print(f"任务 {index+1} 生成失败")
    
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
        loop.run_until_complete(generate_tts_concurrent(text, output_path, voice, rate, volume, pitch))
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
            loop.run_until_complete(generate_tts_concurrent(text, output_path, voice, rate, volume, pitch))
            
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
        success = combine_audio_files(valid_files, output_path, 0)  # 使用200ms间隔
        
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

@sync_retry(retries=2, delay=1)
def combine_audio_files(file_paths, output_path, silence_duration=200):
    """
    使用pydub合并音频文件（如果可用），否则使用简单方法
    """
    try:
        # 尝试使用pydub进行专业合并
        try:
            from pydub import AudioSegment
            
            combined = AudioSegment.empty()
            silence = AudioSegment.silent(duration=silence_duration)  # 可配置的静音间隔
            
            for i, file_path in enumerate(file_paths):
                audio = AudioSegment.from_mp3(file_path)
                combined += audio
                
                # 在音频片段之间添加静音间隔（除了最后一个）
                if i < len(file_paths) - 1:
                    combined += silence
            
            # 导出合并后的音频
            combined.export(output_path, format="mp3")
            print(f"使用pydub成功合并 {len(file_paths)} 个音频文件，静音间隔: {silence_duration}ms")
            return True
            
        except ImportError:
            print("pydub未安装，使用简单合并方法")
            # 回退到简单的二进制连接方法
            with open(output_path, 'wb') as outfile:
                for i, file_path in enumerate(file_paths):
                    with open(file_path, 'rb') as infile:
                        outfile.write(infile.read())
            
            print(f"使用简单方法合并 {len(file_paths)} 个音频文件")
            return True
            
    except Exception as e:
        print(f"音频合并失败: {str(e)}")
        return False

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

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

# 优化的批量TTS生成API（支持并发）
@app.route('/api/batch_tts_concurrent', methods=['POST'])
def api_batch_tts_concurrent():
    """
    高性能并发批量生成TTS音频并合并
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
        max_concurrent = data.get('max_concurrent', MAX_CONCURRENT_TASKS)  # 允许自定义并发数
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        # 临时调整并发限制
        global SEMAPHORE
        original_semaphore = SEMAPHORE
        if max_concurrent != MAX_CONCURRENT_TASKS:
            SEMAPHORE = asyncio.Semaphore(max_concurrent)
        
        start_time = time.time()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 并发生成所有音频文件
            results = loop.run_until_complete(batch_generate_tts_concurrent(items, rate, volume, pitch))
            
            if not results:
                return jsonify({'error': '没有生成任何音频文件'}), 400
            
            # 按原始顺序排序结果
            temp_files = [result[0] for result in results]
            
            # 合并所有音频文件
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_name)
            success = combine_audio_files(temp_files, output_path, silence_duration)
            
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
                
                return jsonify({
                    'success': True,
                    'download_url': download_url,
                    'filename': output_name,
                    'items_processed': len(results),
                    'total_items': len(items),
                    'generation_time': round(generation_time, 2),
                    'concurrent_tasks': max_concurrent,
                    'performance_info': f"并发生成 {len(results)} 个音频文件，用时 {generation_time:.2f} 秒"
                })
            else:
                return jsonify({'error': '音频合并失败'}), 500
                
        finally:
            # 恢复原始信号量
            SEMAPHORE = original_semaphore
            loop.close()
            
    except Exception as e:
        return jsonify({'error': f'并发批量TTS处理失败: {str(e)}'}), 500

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
            if use_concurrent:
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
                    loop.run_until_complete(generate_tts_concurrent(text, temp_path, voice, item_rate, item_volume, item_pitch))
                    
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
            success = combine_audio_files(temp_files, output_path, silence_duration)
            
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
                    'processing_method': 'concurrent' if use_concurrent else 'serial'
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

# 保留原有的批量TTS API端点（现在默认使用并发处理）
@app.route('/api/batch_tts', methods=['POST'])
def api_batch_tts():
    """
    批量生成TTS音频并合并（现在默认使用并发处理以提升性能）
    保持API兼容性，前端无需修改
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
        # 新增：支持禁用并发处理（用于兼容性）
        use_concurrent = data.get('use_concurrent', True)  # 默认启用并发
        max_concurrent = data.get('max_concurrent', MAX_CONCURRENT_TASKS)  # 允许自定义并发数
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        start_time = time.time()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if use_concurrent and len(items) > 3:  # 大于3个项目时使用并发
                # 临时调整并发限制
                global SEMAPHORE
                original_semaphore = SEMAPHORE
                if max_concurrent != MAX_CONCURRENT_TASKS:
                    SEMAPHORE = asyncio.Semaphore(max_concurrent)
                
                try:
                    # 使用并发处理
                    print(f"使用并发处理模式，并发数: {max_concurrent}")
                    results = loop.run_until_complete(batch_generate_tts_concurrent(items, rate, volume, pitch))
                    temp_files = [result[0] for result in results]
                finally:
                    # 恢复原始信号量
                    SEMAPHORE = original_semaphore
            else:
                # 使用串行处理（向后兼容或少量项目）
                print("使用串行处理模式")
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
                    loop.run_until_complete(generate_tts_concurrent(text, temp_path, voice, item_rate, item_volume, item_pitch))
                    temp_files.append(temp_path)
                    
                    print(f"已生成音频 {i+1}/{len(items)}: {text[:20]}...")
            
            if not temp_files:
                return jsonify({'error': '没有生成任何音频文件'}), 400
            
            # 合并所有音频文件
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_name)
            success = combine_audio_files(temp_files, output_path, silence_duration)
            
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
                
                # 返回与原API兼容的响应格式
                response_data = {
                    'success': True,
                    'download_url': download_url,
                    'filename': output_name,
                    'items_processed': len(temp_files)
                }
                
                # 可选：添加性能信息（不影响原有前端）
                if use_concurrent and len(items) > 3:
                    response_data['generation_time'] = round(generation_time, 2)
                    response_data['processing_mode'] = 'concurrent'
                    response_data['performance_info'] = f"并发处理 {len(temp_files)} 个音频文件，用时 {generation_time:.2f} 秒"
                else:
                    response_data['processing_mode'] = 'serial'
                
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

if __name__ == '__main__':
    print(f"TTS服务启动，最大并发任务数: {MAX_CONCURRENT_TASKS}")
    app.run(debug=True, host='0.0.0.0', port=5020) 