"""API路由主入口"""
from fastapi import APIRouter
# 避免循环导入
from api.endpoints import prompt, pii, islamic, hikma, promptguard, proventra, mmbert_guards, benchmark

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

api_router.include_router(
    promptguard.router,
    prefix="/promptguard",
    tags=["promptguard"]
)

api_router.include_router(
    proventra.router,
    prefix="/proventra",
    tags=["proventra"]
)

api_router.include_router(
    mmbert_guards.modernguard_router,
    prefix="/modernguard",
    tags=["modernguard"]
)

api_router.include_router(
    mmbert_guards.wolfdefender_router,
    prefix="/wolfdefender",
    tags=["wolfdefender"]
)

api_router.include_router(
    mmbert_guards.mafguard_router,
    prefix="/mafguard",
    tags=["mafguard"]
)

api_router.include_router(
    benchmark.router,
    prefix="/benchmark",
    tags=["benchmark"]
)