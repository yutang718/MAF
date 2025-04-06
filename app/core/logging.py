"""日志配置模块"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from core.config import settings

# 创建logs目录
log_dir = Path(settings.BASE_DIR) / "logs"
log_dir.mkdir(exist_ok=True)

# 日志文件路径
log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"

# 创建格式化器
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def setup_logger(name: str) -> logging.Logger:
    """
    设置并返回logger
    
    Args:
        name: logger名称
        
    Returns:
        logging.Logger: 配置好的logger实例
    """
    logger = logging.getLogger(name)
    
    # 如果logger已经有handlers，说明已经配置过，直接返回
    if logger.handlers:
        return logger
        
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # 创建文件处理器
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    # 设置不向上传播
    logger.propagate = False
    
    return logger

# 创建根logger
root_logger = setup_logger("app")

def get_logger(name: str) -> logging.Logger:
    """
    获取logger实例
    
    Args:
        name: logger名称，会自动添加app前缀
        
    Returns:
        logging.Logger: logger实例
    """
    return setup_logger(f"app.{name}")

# 添加一些常用的日志装饰器
def log_function_call(logger):
    """函数调用日志装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f"Calling {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Finished {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}")
                raise
        return wrapper
    return decorator

def log_execution_time(logger):
    """执行时间日志装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                logger.info(f"{func.__name__} took {end_time - start_time:.2f} seconds")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}")
                raise
        return wrapper
    return decorator 