#!/usr/bin/env python3
"""
实用装饰器
"""
import asyncio
import time
import functools
from typing import Callable, Any


def async_retry(retries: int = 3, delay: float = 1):
    """异步重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
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


def sync_retry(retries: int = 3, delay: float = 1):
    """同步重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
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


def timing(func: Callable) -> Callable:
    """计时装饰器"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            print(f"⏱️  {func.__name__} 执行时间: {end_time - start_time:.2f}s")
            return result
        except Exception as e:
            end_time = time.time()
            print(f"❌ {func.__name__} 执行失败 (用时: {end_time - start_time:.2f}s): {e}")
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            print(f"⏱️  {func.__name__} 执行时间: {end_time - start_time:.2f}s")
            return result
        except Exception as e:
            end_time = time.time()
            print(f"❌ {func.__name__} 执行失败 (用时: {end_time - start_time:.2f}s): {e}")
            raise
    
    # 判断是否为异步函数
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper 