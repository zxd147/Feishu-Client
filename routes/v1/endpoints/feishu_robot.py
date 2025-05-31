from fastapi import APIRouter
from fastapi import Request

router = APIRouter()

@router.post("")
async def feishu_robot(request: Request):
    """飞书机器人接口"""
    data = await request.body()
    return data