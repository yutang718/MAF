"""依赖注入管理"""
from typing import Generator, TYPE_CHECKING
from core.logging import get_logger
from fastapi import Depends
from services.islamic_context_manager import IslamicContextManager
from services.pii_detector import PIIDetector
from services.proventra_detector import ProventraDetector
from services.mmbert_detector import ModernGuardDetector, WolfDefenderDetector, MafGuardDetector

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
            cls._instance.islamic_context_manager = IslamicContextManager()
            cls._instance.pii_detector = PIIDetector()
            cls._instance.proventra_detector = ProventraDetector()
            cls._instance.modernguard_detector = ModernGuardDetector()
            cls._instance.wolfdefender_detector = WolfDefenderDetector()
            cls._instance.mafguard_detector = MafGuardDetector()
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
            
            # 1. 初始化 PII 检测器
            logger.info("Initializing PII detector...")
            self.pii_detector.initialize()
            
            # 2. 初始化伊斯兰上下文管理器
            logger.info("Initializing Islamic context manager...")
            self.islamic_context_manager.initialize()
            
            # 3. 初始化 Proventra 检测器
            try:
                logger.info("Initializing Proventra detector...")
                self.proventra_detector.initialize()
            except Exception as e:
                logger.warning(f"Proventra model unavailable: {e}")

            # 4. 初始化 ModernGuard-1 / Wolf Defender / MAF Guard 检测器 (mmBERT; MAF Guard 需本地训练产物)
            for detector in (self.modernguard_detector, self.wolfdefender_detector, self.mafguard_detector):
                try:
                    logger.info(f"Initializing {detector.name} detector...")
                    detector.initialize()
                except Exception as e:
                    logger.warning(f"{detector.name} model unavailable: {e}")

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
            
            # 1. 清理伊斯兰上下文管理器
            logger.info("Cleaning up Islamic context manager...")
            await self.islamic_context_manager.cleanup()
            
            # 2. 清理 PII 检测器
            logger.info("Cleaning up PII detector...")
            await self.pii_detector.cleanup()
            
            logger.info("All services cleaned up successfully")
            Services._initialized = False
            
        except Exception as e:
            logger.error(f"Service cleanup failed: {str(e)}")
            raise

def get_services() -> Services:
    """获取服务实例的依赖注入函数"""
    return Services()