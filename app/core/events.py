"""应用事件处理"""
from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager

from core.logging import get_logger
from core.dependencies import get_services
from core.config import settings

logger = get_logger("core.events")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting application...")
    
    # 预加载模型
    try:
        logger.info("Starting model preload...")
        services = get_services()
        
        # 预加载英文和马来文伊斯兰规则
        islamic_manager = services.islamic_context_manager
        en_rules = islamic_manager.load_rules("en")
        ms_rules = islamic_manager.load_rules("ms")
        logger.info(f"Preloaded Islamic rules for languages: en, ms")
        
        await services.model_manager.preload_models()
        logger.info("Model preload completed successfully")
    except Exception as e:
        logger.error(f"Error during preload: {str(e)}")
        # 允许程序继续，但记录错误
    
    # 启动完成，进入应用运行阶段
    yield
    
    # 关闭时执行清理
    logger.info("Shutting down application...")
    # 可以在这里添加资源清理代码
    logger.info("Application shutdown complete")

def setup_app_events(app: FastAPI) -> None:
    """配置应用事件处理器"""
    app.router.lifespan_context = lifespan 