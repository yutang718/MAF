"""
FastAPI 应用主入口
"""
# 标准库导入
import asyncio
import os
from pathlib import Path
from typing import Optional

# 第三方库导入
from fastapi import FastAPI, HTTPException
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

    # 安全治理服务（compliance/）挂在同一域名下，必须在 SPA fallback 之前注册
    mount_governance_proxy(app)

    # 托管前端静态文件（单 image 部署时由 Dockerfile 设置 STATIC_DIR）
    mount_frontend(app)

    return app


# 逐跳头不能原样转发
_HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
                "transfer-encoding", "upgrade", "host", "content-length", "content-encoding"}


def mount_governance_proxy(app: FastAPI) -> None:
    """把 /api/v1/governance/* 转发给安全治理服务（GOVERN_URL），前端因此只需一个源"""
    target = os.getenv("GOVERN_URL", "").rstrip("/")
    if not target:
        logger.info("GOVERN_URL not set, security governance proxy disabled")
        return
    import httpx
    from fastapi import Request
    from fastapi.responses import Response

    client = httpx.AsyncClient(base_url=target, timeout=httpx.Timeout(120.0, connect=5.0))

    @app.api_route(f"{settings.API_V1_STR}/governance/{{path:path}}",
                   methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def governance_proxy(path: str, request: Request):
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_HEADERS}
        if request.client:
            headers["x-forwarded-for"] = request.client.host
        headers["x-forwarded-proto"] = request.url.scheme
        try:
            upstream = await client.request(
                request.method, f"{settings.API_V1_STR}/governance/{path}", params=request.query_params,
                headers=headers, content=await request.body())
        except httpx.HTTPError as e:
            logger.warning(f"governance service unreachable: {e}")
            raise HTTPException(status_code=502, detail="Security governance service is unreachable")
        response = Response(content=upstream.content, status_code=upstream.status_code,
                            headers={k: v for k, v in upstream.headers.items()
                                     if k.lower() not in _HOP_HEADERS and k.lower() != "set-cookie"})
        # 多个 Set-Cookie 需逐条保留
        for cookie in upstream.headers.get_list("set-cookie"):
            response.headers.append("set-cookie", cookie)
        return response

    logger.info(f"Proxying {settings.API_V1_STR}/governance to {target}")


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
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
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