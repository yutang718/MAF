"""依赖注入管理"""
from typing import Generator, TYPE_CHECKING
from core.logging import get_logger
from fastapi import Depends
from services.model_manager import ModelManager
from services.islamic_context_manager import IslamicContextManager
from services.pii_detector import PIIDetector
from services.prompt_checker import PromptChecker

# 使用 TYPE_CHECKING 避免循环导入
if TYPE_CHECKING:
    from services.pii_detector import PIIDetector

logger = get_logger(__name__)

class Services:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Services, cls).__new__(cls)
            # 创建所有服务实例
            cls._instance.model_manager = ModelManager()
            cls._instance.islamic_context_manager = IslamicContextManager()
            cls._instance.pii_detector = PIIDetector()
            cls._instance.prompt_checker = PromptChecker(cls._instance.model_manager)
        return cls._instance

    def __init__(self):
        # 确保只初始化一次
        if not Services._initialized:
            self.initialize()
            Services._initialized = True

    def initialize(self) -> None:
        """初始化所有服务"""
        try:
            logger.info("Starting services initialization...")
            
            # 按依赖顺序初始化
            # 1. 首先初始化模型管理器（其他服务可能依赖它）
            logger.info("Initializing model manager...")
            self.model_manager.initialize()
            
            # 2. 初始化 PII 检测器
            logger.info("Initializing PII detector...")
            self.pii_detector.initialize()
            
            # 3. 初始化伊斯兰上下文管理器
            logger.info("Initializing Islamic context manager...")
            self.islamic_context_manager.initialize()
            
            # 4. 初始化提示词检查器
            logger.info("Initializing prompt checker...")
            self.prompt_checker.initialize()
            
            logger.info("All services initialized successfully")
            Services._initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing services: {str(e)}")
            Services._initialized = False
            raise

    async def cleanup(self) -> None:
        """清理所有服务资源"""
        try:
            logger.info("Starting services cleanup...")
            
            # 按依赖顺序反向清理
            # 1. 清理提示词检查器
            logger.info("Cleaning up prompt checker...")
            await self.prompt_checker.cleanup()
            
            # 2. 清理伊斯兰上下文管理器
            logger.info("Cleaning up Islamic context manager...")
            await self.islamic_context_manager.cleanup()
            
            # 3. 清理 PII 检测器
            logger.info("Cleaning up PII detector...")
            await self.pii_detector.cleanup()
            
            # 4. 最后清理模型管理器
            logger.info("Cleaning up model manager...")
            await self.model_manager.cleanup()
            
            logger.info("All services cleaned up successfully")
            Services._initialized = False
            
        except Exception as e:
            logger.error(f"Service cleanup failed: {str(e)}")
            raise

def get_services() -> Services:
    """获取服务实例的依赖注入函数"""
    return Services()