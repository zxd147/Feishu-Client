from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.api_route("", methods=["GET", "POST"])
@router.api_route("", methods=["GET", "POST"])
async def health():
    """Health check."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    health_data = {"status": "healthy", "timestamp": timestamp}
    # 返回JSON格式的响应
    return JSONResponse(content=health_data, status_code=200)

