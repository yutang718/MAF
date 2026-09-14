"""
FastAPI 应用主入口
"""
# 标准库导入
import asyncio
import os
from pathlib import Path
from typing import Optional

# 第三方库导入
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 本地导入
from core.logging import get_logger
from core.config import settings
from core.dependencies import Services
from api.api import api_router

# 初始化日志
logger = get_logger(__name__)

def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )
    
    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册 API 路由
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # 初始化全局服务实例
    Services()
    
    # 托管前端静态文件（单 image 部署时由 Dockerfile 设置 STATIC_DIR）
    mount_frontend(app)
    
    return app


def mount_frontend(app: FastAPI) -> None:
    """若存在前端构建产物，则托管静态资源并提供 SPA fallback"""
    static_dir = Path(os.getenv("STATIC_DIR", Path(__file__).parent / "static"))
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        logger.info(f"Frontend static dir not found, API-only mode: {static_dir}")
        return
    
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    
    # 注册在 API 路由之后，仅兜底非 API 路径
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = static_dir / full_path
        if full_path and candidate.is_file() and candidate.resolve().is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index_file)
    
    logger.info(f"Serving frontend from {static_dir}")

# 创建应用实例
app = create_app()

# 全局服务实例
services: Optional[Services] = None

@app.on_event("startup")
async def startup_event():
    """应用启动事件处理"""
    try:
        logger.info("Starting application...")
        global services
        
        # 初始化服务
        services = Services()
        services.initialize()
        
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件处理"""
    try:
        logger.info("Shutting down application...")
        global services
        
        if services:
            await services.cleanup()
            
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )