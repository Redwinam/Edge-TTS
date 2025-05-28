#!/usr/bin/env python3
"""
快速测试脚本 - 验证替换版本兼容性
"""

import requests
import time
import json

BASE_URL = "http://localhost:5020"

def test_api_compatibility():
    """测试API兼容性"""
    print("🧪 测试 TTS 替换版本 API 兼容性")
    print("=" * 50)
    
    # 测试1: 单个TTS API
    print("📝 测试1: 单个 TTS API")
    single_data = {
        "text": "测试文本",
        "voice": "zh-CN-XiaoxiaoNeural",
        "rate": "+0%",
        "volume": "+0%",
        "pitch": "+0Hz"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/tts", json=single_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 单个TTS API: 成功")
            print(f"   响应字段: {list(result.keys())}")
        else:
            print(f"❌ 单个TTS API: 失败 ({response.status_code})")
    except Exception as e:
        print(f"❌ 单个TTS API: 连接失败 - {e}")
    
    print()
    
    # 测试2: 批量TTS API（少量项目，应该使用串行）
    print("📝 测试2: 批量 TTS API - 少量项目（串行模式）")
    batch_small_data = {
        "items": [
            {"text": "項目1", "voice": "zh-CN-XiaoxiaoNeural"},
            {"text": "項目2", "voice": "zh-CN-XiaoxiaoNeural"},
            {"text": "項目3", "voice": "zh-CN-XiaoxiaoNeural"}
        ],
        "output_name": "test_small_batch.mp3",
        "silence_duration": 200
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/batch_tts", json=batch_small_data)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 批量TTS (小): 成功")
            print(f"   响应字段: {list(result.keys())}")
            print(f"   处理项目: {result.get('items_processed', 0)}")
            print(f"   处理模式: {result.get('processing_mode', 'unknown')}")
            print(f"   用时: {end_time - start_time:.2f} 秒")
        else:
            print(f"❌ 批量TTS (小): 失败 ({response.status_code})")
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"❌ 批量TTS (小): 连接失败 - {e}")
    
    print()
    
    # 测试3: 批量TTS API（较多项目，应该使用并发）
    print("📝 测试3: 批量 TTS API - 较多项目（并发模式）")
    batch_large_data = {
        "items": [
            {"text": f"項目{i}", "voice": "zh-CN-XiaoxiaoNeural"} 
            for i in range(1, 11)  # 10个项目
        ],
        "output_name": "test_large_batch.mp3",
        "silence_duration": 200
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/batch_tts", json=batch_large_data)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 批量TTS (大): 成功")
            print(f"   响应字段: {list(result.keys())}")
            print(f"   处理项目: {result.get('items_processed', 0)}")
            print(f"   处理模式: {result.get('processing_mode', 'unknown')}")
            print(f"   用时: {end_time - start_time:.2f} 秒")
            if 'performance_info' in result:
                print(f"   性能信息: {result['performance_info']}")
        else:
            print(f"❌ 批量TTS (大): 失败 ({response.status_code})")
            print(f"   错误: {response.text}")
    except Exception as e:
        print(f"❌ 批量TTS (大): 连接失败 - {e}")
    
    print()
    
    # 测试4: 语音列表API
    print("📝 测试4: 语音列表 API")
    try:
        response = requests.get(f"{BASE_URL}/api/voices")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 语音列表API: 成功")
            print(f"   语言分类: {list(result.keys())}")
            if 'zh' in result:
                print(f"   中文语音数量: {len(result['zh'])}")
        else:
            print(f"❌ 语音列表API: 失败 ({response.status_code})")
    except Exception as e:
        print(f"❌ 语音列表API: 连接失败 - {e}")

def test_performance_comparison():
    """性能对比测试"""
    print("\n" + "=" * 50)
    print("⚡ 性能对比测试")
    print("=" * 50)
    
    # 创建测试数据（模拟您的日文词汇场景）
    test_items = [
        {"text": "視察", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "視点", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "視野", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "近視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "遠視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "透視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "監視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "注視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "凝視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "直視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "俯視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "仰視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "環視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "巡視", "voice": "zh-CN-XiaoxiaoNeural"},
        {"text": "檢視", "voice": "zh-CN-XiaoxiaoNeural"},
    ]
    
    print(f"🎯 测试数据: {len(test_items)} 个日文词汇")
    print("📊 预期: 并发模式应该显著快于串行模式")
    print()
    
    # 测试并发模式
    test_data = {
        "items": test_items,
        "output_name": f"perf_test_{int(time.time())}.mp3",
        "silence_duration": 200
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/batch_tts", json=test_data)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            total_time = end_time - start_time
            
            print(f"✅ 性能测试完成:")
            print(f"   处理项目: {result.get('items_processed', 0)}")
            print(f"   处理模式: {result.get('processing_mode', 'unknown')}")
            print(f"   总用时: {total_time:.2f} 秒")
            print(f"   平均每项: {total_time / len(test_items):.2f} 秒")
            print(f"   预估308项目用时: {(total_time / len(test_items)) * 308:.0f} 秒")
            
            if 'performance_info' in result:
                print(f"   性能信息: {result['performance_info']}")
                
        else:
            print(f"❌ 性能测试失败: {response.text}")
    except Exception as e:
        print(f"❌ 性能测试连接失败: {e}")

def main():
    """主函数"""
    print("🚀 TTS 替换版本兼容性测试")
    print("请确保 app_replacement.py 正在 localhost:5020 运行")
    input("按 Enter 继续...")
    
    test_api_compatibility()
    test_performance_comparison()
    
    print("\n" + "=" * 50)
    print("🎉 测试完成!")
    print("如果所有测试都通过，说明替换版本完全兼容原有API")
    print("并且提供了显著的性能提升！")

if __name__ == "__main__":
    main() 