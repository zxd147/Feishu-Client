from typing import Optional

from fastapi import APIRouter
from fastapi import Request

from utils.parse import parse_xml

router = APIRouter()


@router.get("")
async def wechat_auth(request: Request, signature: Optional[str] = None, timestamp: Optional[str] = None, nonce: Optional[str] = None, echostr: Optional[int] = None):
    """验证接口"""
    wechat_mp = request.app.state.wechat_mp
    echostr = wechat_mp.verify(signature, timestamp, nonce, echostr)
    return echostr

@router.post("")
async def wechat_chat(request: Request):
    """公众号聊天接口"""
    wechat_mp = request.app.state.wechat_mp
    xml_data = await request.body()
    # 解析微信消息
    message = parse_xml(xml_data)
    answer = await wechat_mp.chat(message)
    return answer