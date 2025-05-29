#!/usr/bin/env python3
"""
TTS服务去重功能测试脚本
"""

import requests
import json
import time

def test_deduplication():
    """测试TTS服务的去重功能"""
    
    # 测试用例：包含重复内容的TTS请求
    test_items = [
        {"text": "扇風機", "voice": "ja-JP-NanamiNeural"},
        {"text": "こんにちは", "voice": "ja-JP-NanamiNeural"},
        {"text": "扇風機", "voice": "ja-JP-NanamiNeural"},  # 重复1
        {"text": "ゼン", "voice": "ja-JP-NanamiNeural"},
        {"text": "修繕", "voice": "ja-JP-NanamiNeural"},
        {"text": "ゼン", "voice": "ja-JP-NanamiNeural"},      # 重复2
        {"text": "扇風機", "voice": "ja-JP-NanamiNeural"},  # 重复3
        {"text": "新しい内容", "voice": "ja-JP-NanamiNeural"},
    ]
    
    print("🧪 测试TTS服务去重功能")
    print(f"📝 测试项目数: {len(test_items)} 个")
    print("📋 重复内容统计:")
    
    # 统计重复项
    content_count = {}
    for item in test_items:
        key = f"{item['text']}|{item['voice']}"
        content_count[key] = content_count.get(key, 0) + 1
    
    for key, count in content_count.items():
        if count > 1:
            text = key.split('|')[0]
            print(f"   - '{text}' 出现 {count} 次")
    
    # 发送请求到TTS服务
    url = "http://localhost:5000/api/batch_tts"
    
    payload = {
        "items": test_items,
        "output_name": f"dedup_test_{int(time.time())}.wav",
        "audio_format": "wav",
        "use_concurrent": True
    }
    
    print(f"\n🚀 发送批量TTS请求...")
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=180)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("✅ 请求成功!")
                print(f"📊 处理结果:")
                print(f"   - 原始项目数: {result.get('items_processed', 'N/A')}")
                print(f"   - 实际合成数: {result.get('unique_items_synthesized', 'N/A')}")
                print(f"   - 处理时间: {result.get('generation_time', 'N/A')} 秒")
                print(f"   - 处理模式: {result.get('processing_mode', 'N/A')}")
                print(f"   - 音频格式: {result.get('audio_format', 'N/A')}")
                
                # 去重信息
                if 'deduplication_info' in result:
                    dedup_info = result['deduplication_info']
                    print(f"\n🔄 去重效果:")
                    print(f"   - 发现重复项: {dedup_info.get('duplicate_items_found', 0)} 个")
                    print(f"   - 效率提升: {dedup_info.get('efficiency_gain_percent', 0)}%")
                    print(f"   - 说明: {dedup_info.get('description', 'N/A')}")
                
                # 性能信息
                if 'performance_info' in result:
                    print(f"\n⚡ 性能信息:")
                    print(f"   {result['performance_info']}")
                
                print(f"\n🎵 音频文件: {result.get('download_url', 'N/A')}")
                
            else:
                print(f"❌ 请求失败: {result.get('error', 'Unknown error')}")
                
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"   响应: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    total_time = time.time() - start_time
    print(f"\n⏱️  总测试时间: {total_time:.2f} 秒")

if __name__ == "__main__":
    test_deduplication() 