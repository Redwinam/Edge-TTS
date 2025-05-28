import requests
import time
import json

# 测试数据
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
] * 3  # 30个项目

def test_original_api(items, base_url="http://localhost:5020"):
    """测试原始串行API"""
    print("测试原始串行批量TTS API...")
    
    payload = {
        "items": items,
        "output_name": f"test_original_{int(time.time())}.mp3",
        "silence_duration": 200
    }
    
    start_time = time.time()
    response = requests.post(f"{base_url}/api/batch_tts", json=payload)
    end_time = time.time()
    
    if response.status_code == 200:
        result = response.json()
        total_time = end_time - start_time
        print(f"✅ 原始API完成")
        print(f"   处理时间: {total_time:.2f} 秒")
        print(f"   处理项目: {result.get('items_processed', 0)}")
        print(f"   平均每项: {total_time / len(items):.2f} 秒")
        return total_time, result
    else:
        print(f"❌ 原始API失败: {response.text}")
        return None, None

def test_concurrent_api(items, base_url="http://localhost:5020", max_concurrent=10):
    """测试优化的并发API"""
    print(f"测试并发批量TTS API (并发数: {max_concurrent})...")
    
    payload = {
        "items": items,
        "output_name": f"test_concurrent_{int(time.time())}.mp3",
        "silence_duration": 200,
        "max_concurrent": max_concurrent
    }
    
    start_time = time.time()
    response = requests.post(f"{base_url}/api/batch_tts_concurrent", json=payload)
    end_time = time.time()
    
    if response.status_code == 200:
        result = response.json()
        total_time = end_time - start_time
        print(f"✅ 并发API完成")
        print(f"   处理时间: {total_time:.2f} 秒")
        print(f"   处理项目: {result.get('items_processed', 0)}")
        print(f"   平均每项: {total_time / len(items):.2f} 秒")
        print(f"   性能提升: {result.get('performance_info', 'N/A')}")
        return total_time, result
    else:
        print(f"❌ 并发API失败: {response.text}")
        return None, None

def run_performance_comparison():
    """运行性能比较测试"""
    print("=" * 60)
    print("TTS 性能比较测试")
    print("=" * 60)
    print(f"测试项目数量: {len(test_items)}")
    print()
    
    # 测试原始API
    original_time, original_result = test_original_api(test_items)
    print()
    
    # 测试并发API (不同并发数)
    concurrent_configs = [5, 10, 15]
    concurrent_results = []
    
    for max_concurrent in concurrent_configs:
        concurrent_time, concurrent_result = test_concurrent_api(
            test_items, max_concurrent=max_concurrent
        )
        if concurrent_time:
            concurrent_results.append((max_concurrent, concurrent_time, concurrent_result))
        print()
    
    # 性能总结
    print("=" * 60)
    print("性能总结")
    print("=" * 60)
    
    if original_time:
        print(f"原始串行处理: {original_time:.2f} 秒")
    
    for max_concurrent, concurrent_time, result in concurrent_results:
        speedup = original_time / concurrent_time if original_time else 0
        print(f"并发处理({max_concurrent}线程): {concurrent_time:.2f} 秒 (提升 {speedup:.2f}x)")
    
    # 推荐配置
    if concurrent_results:
        best_config = min(concurrent_results, key=lambda x: x[1])
        best_concurrent, best_time, _ = best_config
        if original_time:
            improvement = ((original_time - best_time) / original_time) * 100
            print()
            print(f"🎯 推荐配置: {best_concurrent} 并发线程")
            print(f"🚀 性能提升: {improvement:.1f}%")
            print(f"⏱️  时间节省: {original_time - best_time:.2f} 秒")

if __name__ == "__main__":
    run_performance_comparison() 