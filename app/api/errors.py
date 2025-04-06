"""API错误处理模块"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from typing import Any, Dict
from core.logging import get_logger

# 修正：添加logger名称
logger = get_logger("api.errors")

async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    处理FastAPI的请求验证错误
    
    Args:
        request: FastAPI请求对象
        exc: 验证错误异常
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.error(f"Validation error for {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation Error",
            "errors": exc.errors()
        }
    )

async def pydantic_validation_exception_handler(
    request: Request, 
    exc: ValidationError
) -> JSONResponse:
    """
    处理Pydantic模型验证错误
    
    Args:
        request: FastAPI请求对象
        exc: Pydantic验证错误异常
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.error(f"Pydantic validation error for {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Data Validation Error",
            "errors": exc.errors()
        }
    )

async def general_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """
    处理通用异常
    
    Args:
        request: FastAPI请求对象
        exc: 异常对象
        
    Returns:
        JSONResponse: 错误响应
    """
    error_id = str(id(exc))
    logger.error(f"Unhandled error {error_id} for {request.url.path}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error_id": error_id,
            "message": str(exc)
        }
    )

def get_error_response(status_code: int, message: str, **kwargs: Any) -> Dict[str, Any]:
    """
    生成标准错误响应
    
    Args:
        status_code: HTTP状态码
        message: 错误消息
        **kwargs: 其他错误详情
        
    Returns:
        Dict[str, Any]: 错误响应字典
    """
    response = {
        "status_code": status_code,
        "message": message,
        **kwargs
    }
    logger.debug(f"Generated error response: {response}")
    return response 