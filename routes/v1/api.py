from fastapi import APIRouter

from routes.v1.endpoints import health, wechat_mp, feishu_robot

api_router = APIRouter()

# 添加各个端点路由
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(wechat_mp.router, prefix="/wechat_mp", tags=["wechat_mp"])
api_router.include_router(feishu_robot.router, prefix="/feishu_robot", tags=["feishu_robot"])
