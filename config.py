# TTS 服务配置文件

# 并发控制配置
MAX_CONCURRENT_TASKS = 10  # 默认最大并发任务数
MIN_CONCURRENT_TASKS = 1   # 最小并发任务数
MAX_ALLOWED_CONCURRENT = 20  # 允许的最大并发数（防止系统过载）

# 重试配置
DEFAULT_RETRIES = 3        # 默认重试次数
DEFAULT_RETRY_DELAY = 2    # 默认重试延迟（秒）

# 缓存配置
ENABLE_CACHE = True        # 是否启用缓存
CACHE_MAX_SIZE_MB = 1000   # 缓存最大大小（MB）
CACHE_CLEANUP_INTERVAL = 3600  # 缓存清理间隔（秒）

# 音频配置
DEFAULT_SILENCE_DURATION = 200  # 默认静音间隔（毫秒）
SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav']
DEFAULT_AUDIO_FORMAT = 'mp3'

# 网络配置
CONNECTION_TIMEOUT = 30    # 连接超时（秒）
READ_TIMEOUT = 60         # 读取超时（秒）

# 服务器配置
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5020
DEBUG_MODE = True

# 文件管理配置
TEMP_FILE_CLEANUP_DELAY = 300  # 临时文件清理延迟（秒）
MAX_TEMP_FILES = 100           # 最大临时文件数

# 性能监控配置
ENABLE_PERFORMANCE_LOGGING = True  # 是否启用性能日志
LOG_SLOW_REQUESTS = True           # 是否记录慢请求
SLOW_REQUEST_THRESHOLD = 5.0       # 慢请求阈值（秒）

# 根据系统负载动态调整并发数的配置
ENABLE_DYNAMIC_CONCURRENCY = True   # 是否启用动态并发调整
CPU_THRESHOLD = 80                  # CPU使用率阈值（%）
MEMORY_THRESHOLD = 85               # 内存使用率阈值（%）

def get_optimal_concurrent_tasks():
    """根据系统资源动态计算最优并发数"""
    import os
    import psutil
    
    try:
        # 获取CPU核心数
        cpu_count = os.cpu_count() or 4
        
        # 获取系统负载
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        # 基础并发数为CPU核心数的1.5倍
        base_concurrent = int(cpu_count * 1.5)
        
        # 根据系统负载调整
        if cpu_percent > CPU_THRESHOLD or memory_percent > MEMORY_THRESHOLD:
            # 系统负载高，减少并发
            optimal_concurrent = max(MIN_CONCURRENT_TASKS, base_concurrent // 2)
        else:
            # 系统负载正常，使用标准并发数
            optimal_concurrent = min(MAX_CONCURRENT_TASKS, base_concurrent)
        
        return optimal_concurrent
    except:
        # 如果无法获取系统信息，返回默认值
        return MAX_CONCURRENT_TASKS

def validate_concurrent_setting(concurrent_tasks):
    """验证并发设置是否合理"""
    if concurrent_tasks < MIN_CONCURRENT_TASKS:
        return MIN_CONCURRENT_TASKS
    elif concurrent_tasks > MAX_ALLOWED_CONCURRENT:
        return MAX_ALLOWED_CONCURRENT
    else:
        return concurrent_tasks 