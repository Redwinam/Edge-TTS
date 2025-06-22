#!/usr/bin/env python3
"""
TTS 服务 - 重构版
支持Azure TTS和Edge TTS，模块化设计
默认使用Azure TTS
"""

import os
import uuid
import asyncio
import time
from flask import Flask, render_template, request, send_from_directory, jsonify, Response, make_response
from flask_cors import CORS
import re

# 导入重构后的模块
from config import FLASK_CONFIG, CORS_CONFIG, TTS_CONFIG, LANGUAGE_NAMES, print_config_info
from services.tts_service import TTSService


app = Flask(__name__)

# 配置CORS
CORS(app, **CORS_CONFIG)

# 配置静态文件夹
if not os.path.exists(FLASK_CONFIG['upload_folder']):
    os.makedirs(FLASK_CONFIG['upload_folder'])

app.config['UPLOAD_FOLDER'] = FLASK_CONFIG['upload_folder']

# 初始化TTS服务
tts_service = TTSService()

# 打印配置信息
print_config_info()


@app.route('/')
def index():
    """主页"""
    return render_template('index.html', language_names=LANGUAGE_NAMES)


@app.route('/get_voices', methods=['GET'])
def get_voices():
    """获取可用语音列表"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        voices = loop.run_until_complete(tts_service.get_voices())
        return jsonify(voices)
    except Exception as e:
        print(f"获取语音列表失败: {e}")
        # 返回空字典，前端会处理
        return jsonify({})
    finally:
        loop.close()


@app.route('/synthesize', methods=['POST'])
def synthesize():
    """单个TTS合成"""
    text = request.form.get('text', '')
    voice = request.form.get('voice', TTS_CONFIG.get('default_voice', 'zh-CN-XiaoxiaoNeural'))
    rate = request.form.get('rate', '+0%')
    volume = request.form.get('volume', '+0%')
    pitch = request.form.get('pitch', '+0Hz')
    audio_format_to_use = TTS_CONFIG.get('default_format', 'mp3') # 使用配置的默认格式
    
    if not text:
        return jsonify({'error': '请输入文本'}), 400
    
    # 生成唯一的文件名
    filename = f"{uuid.uuid4()}.{audio_format_to_use}" # 使用实际格式作为扩展名
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # 执行异步任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success = loop.run_until_complete(
            tts_service.synthesize_single(text, output_path, voice, rate, volume, pitch, None, audio_format_to_use)
        )
        if success:
            audio_url = f"/static/audio/{filename}"
            return jsonify({'success': True, 'audio_url': audio_url, 'filename': filename})
        else:
            return jsonify({'error': '生成失败'}), 500
    except Exception as e:
        return jsonify({'error': f'生成失败: {str(e)}'}), 500
    finally:
        loop.close()


@app.route('/api/tts', methods=['POST'])
def api_tts():
    """
    API端点，支持JSON和表单请求
    支持MP3和WAV格式
    """
    try:
        data = request.get_json()
        default_audio_format = TTS_CONFIG.get('default_format', 'mp3') # 从配置获取默认格式
        if not data:
            # 尝试从表单数据获取
            text = request.form.get('text', '')
            voice = request.form.get('voice', TTS_CONFIG.get('default_voice', 'zh-CN-XiaoxiaoNeural'))
            rate = request.form.get('rate', '+0%')
            volume = request.form.get('volume', '+0%')
            pitch = request.form.get('pitch', '+0Hz')
            return_type = request.form.get('return_type', 'url')
            audio_format = request.form.get('audio_format', default_audio_format).lower()
        else:
            text = data.get('text', '')
            voice = data.get('voice', TTS_CONFIG.get('default_voice', 'zh-CN-XiaoxiaoNeural'))
            rate = data.get('rate', '+0%')
            volume = data.get('volume', '+0%')
            pitch = data.get('pitch', '+0Hz')
            return_type = data.get('return_type', 'url')
            audio_format = data.get('audio_format', default_audio_format).lower()
        
        if not text:
            return jsonify({'error': '请提供文本'}), 400

        # 验证音频格式
        if audio_format not in TTS_CONFIG['supported_formats']:
            return jsonify({'error': f'支持的音频格式: {", ".join(TTS_CONFIG["supported_formats"])}'}), 400

        # 生成唯一的文件名
        file_ext = audio_format
        filename = f"{uuid.uuid4()}.{file_ext}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 执行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                tts_service.synthesize_single(text, output_path, voice, rate, volume, pitch, None, audio_format)
            )
            
            if success:
                if return_type == 'audio':
                    # 直接返回音频文件
                    with open(output_path, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    mime_type = 'audio/wav' if audio_format == 'wav' else 'audio/mpeg'
                    return Response(audio_data, mimetype=mime_type)
                else:
                    # 返回音频URL
                    host = request.host_url.rstrip('/')
                    audio_url = f"{host}/static/audio/{filename}"
                    return jsonify({
                        'success': True, 
                        'audio_url': audio_url,
                        'filename': filename,
                        'audio_format': audio_format,
                        'engine': tts_service.get_current_engine_info().get('name', 'unknown')
                    })
            else:
                return jsonify({'error': '生成失败'}), 500
                
        except Exception as e:
            return jsonify({'error': f'生成失败: {str(e)}'}), 500
        finally:
            loop.close()
    except Exception as e:
        return jsonify({'error': f'请求处理失败: {str(e)}'}), 500


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
        grouped_voices = loop.run_until_complete(tts_service.get_voices())
        
        if language and language in grouped_voices:
            return jsonify({language: grouped_voices[language]})
        
        # 添加引擎信息
        response_data = grouped_voices.copy()
        response_data['_engine_info'] = tts_service.get_current_engine_info()
        
        return jsonify(response_data)
    except Exception as e:
        print(f"API获取语音列表失败: {e}")
        return jsonify({'error': f'获取语音列表失败: {str(e)}'}), 500
    finally:
        loop.close()


@app.route('/api/batch_tts', methods=['POST'])
def api_batch_tts():
    """
    批量生成TTS音频并合并
    完全兼容原有API，但使用新的模块化架构
    """
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': '请提供TTS项目列表'}), 400
        
        default_audio_format = TTS_CONFIG.get('default_format', 'mp3') # 从配置获取默认格式
        items = data.get('items', [])
        # 默认输出文件名后缀应与默认格式一致
        output_name_default = f'batch_tts_{uuid.uuid4().hex[:12]}.{default_audio_format}'
        output_name = data.get('output_name', output_name_default)
        rate = data.get('rate', '+0%')
        volume = data.get('volume', '+0%')
        pitch = data.get('pitch', '+0Hz')
        silence_duration = data.get('silence_duration', 200)
        audio_format = data.get('audio_format', default_audio_format).lower()
        
        # 智能模式参数
        use_concurrent = data.get('use_concurrent', True)
        max_concurrent = data.get('max_concurrent', TTS_CONFIG['max_concurrent_tasks'])
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        # 验证音频格式
        if audio_format not in TTS_CONFIG['supported_formats']:
            return jsonify({'error': f'支持的音频格式: {", ".join(TTS_CONFIG["supported_formats"])}'}), 400
        
        # 清理输出文件名，移除可能导致路径问题的字符
        safe_output_name = re.sub(r'[^\w\-_.]', '_', output_name)
        # 确保文件名不为空且有合适的扩展名
        if not safe_output_name or safe_output_name.startswith('.'):
            safe_output_name = f'batch_tts_{uuid.uuid4().hex[:8]}.{audio_format}'
        
        # 根据格式调整输出文件扩展名
        if audio_format == 'wav' and not safe_output_name.endswith('.wav'):
            safe_output_name = safe_output_name.replace('.mp3', '.wav') if safe_output_name.endswith('.mp3') else safe_output_name + '.wav'
        elif audio_format == 'mp3' and not safe_output_name.endswith('.mp3'):
            safe_output_name = safe_output_name.replace('.wav', '.mp3') if safe_output_name.endswith('.wav') else safe_output_name + '.mp3'
        
        print(f"📝 原始输出文件名: {output_name}")
        print(f"🔧 安全输出文件名: {safe_output_name}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                tts_service.create_batch_audio(
                    items, safe_output_name, rate, volume, pitch,
                    silence_duration, use_concurrent, max_concurrent, audio_format
                )
            )
            
            # 构建下载URL
            host = request.host_url.rstrip('/')
            download_url = f"{host}/static/audio/{safe_output_name}"
            
            # 返回与原API完全兼容的响应格式
            response_data = {
                'success': True,
                'download_url': download_url,
                'filename': safe_output_name,
                'items_processed': result['items_processed'],
                'audio_format': result['audio_format'],
                'generation_time': result['generation_time'],
                'processing_mode': result['processing_mode'],
                'engine': tts_service.get_current_engine_info().get('name', 'unknown')
            }
            
            # 添加去重效率信息
            if 'unique_items_synthesized' in result:
                response_data['unique_items_synthesized'] = result['unique_items_synthesized']
                
                # 计算去重效果
                duplicate_count = result['items_processed'] - result['unique_items_synthesized']
                if duplicate_count > 0:
                    efficiency_gain = round((duplicate_count / result['items_processed']) * 100, 1)
                    response_data['deduplication_info'] = {
                        'duplicate_items_found': duplicate_count,
                        'efficiency_gain_percent': efficiency_gain,
                        'description': f"通过去重减少了 {duplicate_count} 次重复合成，效率提升 {efficiency_gain}%"
                    }
            
            # 性能信息
            if result['processing_mode'] == 'concurrent':
                speedup_estimate = max(1.5, len(items) * 0.8 / result['generation_time']) if result['generation_time'] > 0 else 1.0
                performance_info = f"⚡ 并发处理 {result['items_processed']} 个音频文件 ({audio_format}), 用时 {result['generation_time']:.2f} 秒 (预估提速 {speedup_estimate:.1f}x)"
                
                # 如果有去重信息，追加到性能信息中
                if 'deduplication_info' in response_data:
                    performance_info += f" + 去重优化 {response_data['deduplication_info']['efficiency_gain_percent']}%"
                    
                response_data['performance_info'] = performance_info
            
            return jsonify(response_data)
            
        except Exception as e:
            return jsonify({'error': f'批量TTS处理失败: {str(e)}'}), 500
        finally:
            loop.close()
            
    except Exception as e:
        return jsonify({'error': f'请求处理失败: {str(e)}'}), 500


@app.route('/api/batch_tts_with_timecodes', methods=['POST'])
def api_batch_tts_with_timecodes():
    """
    批量生成TTS音频，不合并，返回每个片段的时间点信息。
    用于视频生成等场景。
    """
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': '请提供TTS项目列表'}), 400
        
        default_audio_format = TTS_CONFIG.get('default_format', 'mp3')
        items = data.get('items', [])
        # output_name is not strictly needed as we don't save a combined file, but can be used for logging or context
        # output_name_default = f'batch_timecode_run_{{uuid.uuid4()}}' 
        # output_name = data.get('output_name', output_name_default)
        
        rate = data.get('rate', '+0%')
        volume = data.get('volume', '+0%')
        pitch = data.get('pitch', '+0Hz')
        silence_duration_ms = data.get('silence_duration_ms', data.get('silence_duration', 200)) # 支持旧的silence_duration
        use_concurrent = data.get('use_concurrent', True)
        max_concurrent_from_req = data.get('max_concurrent')
        audio_format = data.get('audio_format', default_audio_format).lower()
        
        if not items:
            return jsonify({'error': 'TTS项目列表不能为空'}), 400
        
        if audio_format not in TTS_CONFIG['supported_formats']:
            return jsonify({'error': f'支持的音频格式: {", ".join(TTS_CONFIG["supported_formats"])}'}), 400

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 确定并发数，优先使用请求中的值，否则使用配置的默认值
            max_concurrent_tasks = max_concurrent_from_req if max_concurrent_from_req is not None else TTS_CONFIG['max_concurrent_tasks']

            result = loop.run_until_complete(
                tts_service.create_batch_tts_with_timecodes(
                    items,
                    rate,
                    volume,
                    pitch,
                    silence_duration_ms=int(silence_duration_ms),
                    audio_format=audio_format,
                    use_concurrent=use_concurrent,
                    max_concurrent=int(max_concurrent_tasks)
                )
            )
            
            # result 包含: success, timecodes, total_duration_with_silence_ms, items_processed_count, etc.
            if result.get('success'):
                response_data = {
                    'success': True,
                    'timecodes': result.get('timecodes', []),
                    'total_duration_with_silence_ms': result.get('total_duration_with_silence_ms'),
                    'items_processed_count': result.get('items_processed_count'),
                    'unique_items_synthesized_count': result.get('unique_items_synthesized_count'),
                    'actual_segments_with_audio_count': result.get('actual_segments_with_audio_count'),
                    'silence_between_items_ms': result.get('silence_between_items_ms'),
                    'generation_time_seconds': result.get('generation_time_seconds'),
                    'processing_mode': result.get('processing_mode'),
                    'audio_format_generated': result.get('audio_format_generated'),
                    'engine_used': tts_service.get_current_engine_info().get('name', 'unknown')
                }
                return jsonify(response_data)
            else:
                # 如果 tts_service 返回 success: False，或者有特定错误信息
                error_message = result.get('error', '时间码生成过程失败')
                return jsonify({'error': error_message, 'details': result}), 500
            
        except ValueError as ve:
            return jsonify({'error': f'参数错误: {str(ve)}'}), 400
        except Exception as e:
            app.logger.error(f"批量TTS (带时间码) 处理失败: {str(e)}", exc_info=True)
            return jsonify({'error': f'批量TTS (带时间码) 处理失败: {str(e)}'}), 500
        finally:
            loop.close()
            
    except Exception as e:
        app.logger.error(f"请求处理失败 (batch_tts_with_timecodes): {str(e)}", exc_info=True)
        return jsonify({'error': f'请求处理失败: {str(e)}'}), 500


@app.route('/api/engine/switch', methods=['POST'])
def api_switch_engine():
    """切换TTS引擎"""
    try:
        data = request.get_json()
        if not data or 'engine' not in data:
            return jsonify({'error': '请提供引擎名称'}), 400
        
        engine_name = data.get('engine')
        available_engines = tts_service.engine_manager.get_available_engines()
        
        if engine_name not in available_engines:
            return jsonify({
                'error': f'引擎不可用，可用引擎: {", ".join(available_engines)}'
            }), 400
        
        success = tts_service.switch_engine(engine_name)
        if success:
            return jsonify({
                'success': True,
                'current_engine': engine_name,
                'available_engines': available_engines
            })
        else:
            return jsonify({'error': '引擎切换失败'}), 500
            
    except Exception as e:
        return jsonify({'error': f'引擎切换失败: {str(e)}'}), 500


@app.route('/api/engine/info', methods=['GET'])
def api_engine_info():
    """获取当前引擎信息"""
    try:
        engine_info = tts_service.get_current_engine_info()
        return jsonify(engine_info)
    except Exception as e:
        return jsonify({'error': f'获取引擎信息失败: {str(e)}'}), 500


@app.route('/download/<filename>')
def download(filename):
    """下载文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/static/audio/<filename>')
def serve_audio(filename):
    """
    专门服务音频文件，支持跨域播放和Range请求
    """
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': '音频文件不存在'}), 404
        
        file_size = os.path.getsize(file_path)
        range_header = request.headers.get('Range', None)
        
        if range_header:
            # 处理Range请求
            byte_start = 0
            byte_end = file_size - 1
            
            if range_header.startswith('bytes='):
                range_match = range_header[6:].split('-')
                if range_match[0]:
                    byte_start = int(range_match[0])
                if range_match[1]:
                    byte_end = int(range_match[1])
            
            byte_start = max(0, byte_start)
            byte_end = min(file_size - 1, byte_end)
            content_length = byte_end - byte_start + 1
            
            with open(file_path, 'rb') as audio_file:
                audio_file.seek(byte_start)
                data = audio_file.read(content_length)
            
            response = make_response(data)
            response.status_code = 206
            response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
            response.headers['Content-Length'] = str(content_length)
        else:
            response = make_response(send_from_directory(app.config['UPLOAD_FOLDER'], filename))
        
        # 添加音频播放相关头部
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Type'] = 'audio/mpeg'
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Vary'] = 'Accept-Encoding, Range'
        
        return response
        
    except Exception as e:
        print(f"音频文件服务错误: {e}")
        return jsonify({'error': f'服务音频文件失败: {str(e)}'}), 500


@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点（支持两个路径）"""
    engine_info = tts_service.get_current_engine_info()
    return jsonify({
        'status': 'healthy',
        'service': 'TTS Server (重构版)',
        'version': '3.0',
        'timestamp': time.time(),
        'cors_enabled': True,
        'current_engine': engine_info.get('name', 'unknown'),
        'available_engines': engine_info.get('available_engines', []),
        'max_concurrent_tasks': TTS_CONFIG['max_concurrent_tasks'],
        'supported_formats': TTS_CONFIG['supported_formats']
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🎵 TTS 智能服务 v3.0 (重构版)")
    print("=" * 60)
    print("✨ 特性:")
    print("   🔵 默认使用Azure TTS")
    print("   🟢 保留Edge TTS作为备选")
    print("   📱 完全兼容原有API")
    print("   ⚡ 智能并发处理")
    print("   🎯 自动故障转移")
    print("   💾 智能缓存系统")
    print("   🏗️  模块化架构设计")
    print("   🌐 支持跨域访问 (CORS)")
    print("   🎵 支持MP3和WAV格式")
    print("   🔒 支持HTTPS（可选）")
    print()
    
    # 显示当前引擎信息
    engine_info = tts_service.get_current_engine_info()
    print(f"🎯 当前引擎: {engine_info.get('name', 'unknown')}")
    print(f"📊 可用引擎: {', '.join(engine_info.get('available_engines', []))}")
    print()
    
    # 检查是否启用HTTPS
    use_https = os.environ.get('TTS_HTTPS', 'false').lower() == 'true'
    ssl_cert = os.environ.get('TTS_SSL_CERT', 'ssl/cert.pem')
    ssl_key = os.environ.get('TTS_SSL_KEY', 'ssl/key.pem')
    
    if use_https and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
        protocol = "https"
        ssl_context = (ssl_cert, ssl_key)
        print(f"🔒 HTTPS服务地址: https://localhost:{FLASK_CONFIG['port']}")
        print(f"🎧 音频URL: https://localhost:{FLASK_CONFIG['port']}/static/audio/<filename>")
        print(f"🛡️  SSL证书: {ssl_cert}")
    else:
        protocol = "http"
        ssl_context = None
        print(f"🌐 HTTP服务地址: http://localhost:{FLASK_CONFIG['port']}")
        print(f"🎧 音频URL: http://localhost:{FLASK_CONFIG['port']}/static/audio/<filename>")
        if use_https:
            print("⚠️  HTTPS已启用但SSL证书文件不存在，回退到HTTP模式")
    
    print("=" * 60)
    print("💡 HTTPS启用方法:")
    print("   1. 设置环境变量: export TTS_HTTPS=true")
    print("   2. 提供SSL证书: ssl/cert.pem 和 ssl/key.pem")
    print("   3. 或自定义证书路径:")
    print("      export TTS_SSL_CERT=/path/to/cert.pem")
    print("      export TTS_SSL_KEY=/path/to/key.pem")
    print("=" * 60)
    
    app.run(debug=FLASK_CONFIG['debug'], 
            host=FLASK_CONFIG['host'], 
            port=FLASK_CONFIG['port'],
            ssl_context=ssl_context) 