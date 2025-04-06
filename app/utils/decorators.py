"""装饰器工具模块"""
import time
import functools
from typing import Callable, Any
from core.logging import get_logger

# 修正：添加logger名称
logger = get_logger("utils.decorators")

def timed(func: Callable) -> Callable:
    """
    计时装饰器，记录函数执行时间
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.debug(f"{func.__name__} took {elapsed_time:.4f}s to execute")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed_time:.4f}s: {str(e)}")
            raise
    return wrapper

def async_timed(func: Callable) -> Callable:
    """
    异步函数计时装饰器
    
    Args:
        func: 要装饰的异步函数
        
    Returns:
        装饰后的异步函数
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.debug(f"{func.__name__} took {elapsed_time:.4f}s to execute")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed_time:.4f}s: {str(e)}")
            raise
    return wrapper 