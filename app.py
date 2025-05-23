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

@async_retry(retries=3, delay=2)
async def generate_tts(text, output_path, voice, rate, volume, pitch):
    # --- 缓存逻辑开始 ---
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
            return # 提前返回，无需重新生成
        except Exception as e:
            print(f"从缓存复制文件失败: {e}，将重新生成。")
            # 如果复制失败，则继续执行生成逻辑

    print(f"缓存未命中: {cached_filename}，生成新文件。")
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

# 批量TTS生成和合并API端点
@app.route('/api/batch_tts', methods=['POST'])
def api_batch_tts():
    """
    批量生成TTS音频并合并
    接收格式: {
        "items": [
            {"text": "文本内容", "voice": "语音名称"},
            {"text": "文本内容", "voice": "语音名称"}
        ],
        "output_name": "输出文件名",
        "silence_duration": 200  // 可选：静音间隔时长（毫秒）
    }
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
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        # 依次生成所有音频文件
        temp_files = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for i, item in enumerate(items):
                text = item.get('text', '')
                voice = item.get('voice', DEFAULT_VOICE)
                
                if not text.strip():
                    continue
                
                # 生成临时文件名
                temp_filename = f"batch_{uuid.uuid4()}.mp3"
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                
                # 生成TTS音频
                loop.run_until_complete(generate_tts(text, temp_path, voice, rate, volume, pitch))
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
            
            if success:
                # 构建下载URL
                host = request.host_url.rstrip('/')
                download_url = f"{host}/static/audio/{output_name}"
                
                return jsonify({
                    'success': True,
                    'download_url': download_url,
                    'filename': output_name,
                    'items_processed': len(temp_files)
                })
            else:
                return jsonify({'error': '音频合并失败'}), 500
                
        finally:
            loop.close()
            
    except Exception as e:
        # 清理可能残留的临时文件
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
        return jsonify({'error': f'批量TTS处理失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5020) 