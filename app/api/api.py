"""API路由主入口"""
from fastapi import APIRouter
# 避免循环导入
from api.endpoints import prompt, pii, islamic, hikma

# 创建主路由实例
api_router = APIRouter()

# 注册路由
api_router.include_router(
    prompt.router,
    prefix="/prompt",
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

api_router.include_router(
    hikma.router,
    prefix="/hikma",
    tags=["hikma"]
) 