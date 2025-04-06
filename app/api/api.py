"""API路由主入口"""
from fastapi import APIRouter
# 避免循环导入
from api.endpoints import prompt, pii, islamic

# 创建主路由实例
api_router = APIRouter()

# 注册路由
api_router.include_router(
    prompt.router,
    prefix="/prompt",  # 添加前缀
    tags=["prompt"]
)

api_router.include_router(
    pii.router,
    prefix="/pii",
    tags=["pii"]
)

api_router.include_router(
    islamic.router,
    prefix="/islamic",
    tags=["islamic"]
) 