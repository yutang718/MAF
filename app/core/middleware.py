from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from core.logging import get_logger

logger = get_logger("core.middleware")

class APIErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            
            # 记录404错误的详细信息
            if response.status_code == 404:
                logger.warning(
                    f"404 Not Found: {request.method} {request.url.path}\n"
                    f"Headers: {dict(request.headers)}\n"
                    f"Query Params: {dict(request.query_params)}"
                )
            
            return response
            
        except Exception as e:
            logger.exception("Unhandled error in request pipeline")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            ) 