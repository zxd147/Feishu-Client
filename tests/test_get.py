import asyncio
import json

import httpx

base_url = "http://172.16.10.25/v1"
chat_endpoint = "/chat-messages"
conversations_endpoint = "/conversations"

user = "abc-123"
limit = 20
concurrency_limit = 5
timeout = 30
headers = {
    "Authorization": f"Bearer app-vTtbF4zPgAHHJvCLOsagL27B",
    "Content-Type": "application/json"
}
get_header = {"Authorization": f"Bearer app-vTtbF4zPgAHHJvCLOsagL27B"}
client = httpx.AsyncClient(base_url=base_url, limits=httpx.Limits(max_connections=concurrency_limit),
                           timeout=httpx.Timeout(timeout), http2=True, follow_redirects=True)
sync_client = httpx.Client(base_url=base_url)

async def post_request(params, user_info, **kwargs):
    # try:
    if True:
        async with client.stream("POST", chat_endpoint, headers=headers, json=params) as post_response:
            # 此处的 post_response 仅包含响应头，不阻塞等待响应体
            assert post_response.status_code >= 200, "status_code not >= 200."
            status_code = post_response.status_code
            print(status_code)
            kwargs['user_info'] = user_info
            return await parser_response(post_response, **kwargs)
    # except (httpx.HTTPStatusError, httpx.RequestError) as e:
    #     print(f"POST请求失败: {e}")
    #     raise
    return None

async def parser_response(post_response, **kwargs):
    """默认解析逻辑, 动态解析响应：支持JSON和流式"""
    assert post_response.status_code == 200, f"LLM response session failed with status code: {post_response.status_code}, text: {(await post_response.aread()).decode('utf-8')}"
    conv_params = kwargs.get("conv_params", '')
    user_info = kwargs.get("user_info", {})
    await get_request(user_info, conv_params=conv_params)  # 立即发送GET请求（无需等待POST响应体）
    status_code = post_response.status_code
    print(status_code)
    if post_response.status_code != 200:
        error_text = await post_response.aread()  # 显式读取错误信息
        error_text = error_text.decode('utf-8')
        print(error_text)
        raise ValueError(f"请求失败{post_response.url}\n状态码: {post_response.status_code}\n响应体: {error_text}")
    answer = ''
    response_data = ''
    content_type = (getattr(post_response, 'content_type', None) or post_response.headers.get('Content-Type', '') or '').lower()
    if content_type.split(';')[0].strip() == 'application/json':
        response_data += "blocking...\n"
        response_json = (await post_response.aread()).decode('utf-8')  # 显式读取数据
        response_dict = json.loads(response_json)
        answer = response_dict.get('answer', '')
        response_data += response_json
    elif content_type.split(';')[0].strip() == 'text/event-stream':
        response_data += "streaming...\n"
        async for line in post_response.aiter_lines():  # 使用httpx原生流式迭代器
            response_data += line + '\n'
            # print(f"line: {line}")
            line = line.strip().replace('data: ', '', 1)
            if not line or line == "[DONE]":
                continue
            data = json.loads(line)
            if content := data.get('answer'):
                answer += content
    else:
        raise ValueError(f"Unsupported response.content_type: {content_type}")
    print(f"response_data: {response_data}")
    print(f"answer: {answer}")
    return answer

async def get_request(user_info, **kwargs):
    # get_response = sync_client.get(f"{conversations_endpoint}?user={user}&limit={limit}", headers=get_header)
    conv_params = kwargs.get('conv_params', '')
    get_response = await client.get(conversations_endpoint, params=conv_params, headers=headers)
    data = get_response.json()
    conversations_id_list = data.get("data", [])
    user_info[user] = conversations_id_list[0]["id"]
    print(f"get conversations_id_list: {conversations_id_list}")
    conversations_id = conversations_id_list[0]["id"]
    print(f"new conversations_id: {conversations_id}")

async def main():
    params = {
        "inputs": {},
        "query": "你是谁？",
        "response_mode": "blocking",
        # "response_mode": "streaming",
        "conversation_id": "",
        "user": user
    }
    user_info = {}
    conv_params = {"user": user, "limit": limit}
    print(f"user_info: {user_info}")
    await get_request(user_info, conv_params=conv_params)
    print(f"user_info: {user_info}")

    _ = await post_request(params, user_info, conv_params=conv_params)
    print(f"user_info: {user_info}")


asyncio.run(main())
