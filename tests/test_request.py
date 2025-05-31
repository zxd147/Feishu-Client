import asyncio

import httpx

request_params = {"model":"dify","query":"你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好你好","response_mode":"blocking","user":"user-123","conversation_id":"","inputs":{},"messages":[],"stream":True}
client = httpx.AsyncClient(base_url="http://172.16.10.25/v1", limits=httpx.Limits(max_connections=10),
                                timeout=httpx.Timeout(30), http2=True, follow_redirects=True)
headers = {'Authorization': 'Bearer app-vTtbF4zPgAHHJvCLOsagL27B', 'Content-Type': 'application/json'}
endpoint = "/chat-messages"


async def make_request():
    """异步HTTP请求核心实现（httpx版）"""
    response = await client.post(endpoint, headers=headers, json=request_params)
    response.raise_for_status()  # 自动处理HTTP错误
    return response

async def main():
        result = await make_request()
        print(result, result.status_code, result.json())

asyncio.run(main())