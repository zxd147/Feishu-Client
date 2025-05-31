import json
from typing import Optional, Callable, AsyncGenerator

import httpx

from utils.exception import log_exception
from utils.logger import get_loger

logger = get_loger()


class BaseLLMClient:
    def __init__(self, base_url, endpoint, headers, concurrency_limit=10, timeout=30, response_parser: Optional[Callable] = None):
        self.base_url = base_url
        self.endpoint = endpoint
        self.headers = headers
        self.parser = response_parser or self._default_parser
        self.stream_parser = response_parser or self._default_stream_parser
        self.make_request = self._make_request
        # 配置连接池参数（等效于原TCPConnector）
        self.client = httpx.AsyncClient(base_url=base_url, limits=httpx.Limits(max_connections=concurrency_limit),
            timeout=httpx.Timeout(timeout), http2=True, follow_redirects=True)

    async def close(self):
        await self.client.aclose()  # 显式关闭连接池

    async def get_completion(self, params) -> str:
        """统一请求入口，子类可覆盖具体解析逻辑"""
        try:
            response = await self.make_request(params)
            answer = await self.parser(response)  # 使用注入的解析器
            return answer
        except (httpx.HTTPError, httpx.RequestError, json.JSONDecodeError, KeyError, Exception) as exc:
            log_exception(exc)
            raise

    async def get_stream_completion(self, params) -> AsyncGenerator[str, None]:
        """统一请求入口，子类可覆盖具体解析逻辑"""
        try:
            response = await self.make_request(params)
            generator = self.stream_parser(response)
            async for content in generator:
                yield content  # 直接传递数据流
        except (httpx.HTTPError, httpx.RequestError, httpx.StreamError,
                httpx.RemoteProtocolError, json.JSONDecodeError, KeyError, Exception) as exc:
            log_exception(exc)
            raise

    async def _make_request(self, params):
        """异步HTTP请求核心实现（httpx版）"""
        try:
            param_json = params.model_dump()
            logger.info(f"LLM request params: ---\n{param_json}\n---")
            response = await self.client.post(self.endpoint, headers=self.headers, json=param_json)
            return response
        except httpx.HTTPStatusError as exc:
            logger.error(f'LLM response failed with status code: {exc.response.status_code}. ')
            raise

    @staticmethod
    async def _default_parser(response) -> str:
        """默认解析逻辑, 动态解析响应：支持JSON和流式"""
        assert response.status_code == 200, f"LLM response session failed with status code: {response.status_code}, text: {response.text}"
        logger.info(f'LLM response session successfully with status code: {response.status_code}, text: {response.text}')
        answer = ''
        response_data = ''
        content_type = (getattr(response, 'content_type', None) or response.headers.get('Content-Type', '') or '').lower()
        if content_type.split(';')[0].strip() == 'application/json':
            response_data = response.json()  # 同步方法（httpx 已自动处理编码）
            answer = response_data.get('answer', '')
            response_data = "blocking...\n" + json.dumps(response_data, ensure_ascii=False, indent=4)
        elif content_type.split(';')[0].strip() == 'text/event-stream':
            async for line in response.aiter_lines():  # 使用httpx原生流式迭代器
                response_data += "streaming...\n"
                line = line.strip().replace('data: ', '', 1)
                response_data += line + '\n'
                if not line or line == "[DONE]":
                    continue
                data = json.loads(line)
                if content := data.get('answer'):
                    answer += content
        else:
            raise ValueError(f"Unsupported response.content_type: {content_type}")
        logger.info(f'LLM response_data: ===\n{response_data}\n===')
        return answer

    @staticmethod
    async def _default_stream_parser(response) -> AsyncGenerator[str, None]:
        """默认解析逻辑, 动态解析响应：支持JSON和流式"""
        assert response.status_code == 200, f"LLM response session failed with status code: {response.status_code}, text: {response.text}"
        logger.info(f"LLM response session successfully with status code: {response.status_code}, text: {response.text}")
        answer = ''
        response_data = ''
        content_type = (getattr(response, 'content_type', None) or response.headers.get('Content-Type', '') or '').lower()
        if content_type.split(';')[0].strip() == 'application/json':
            response_data = response.json()  # 同步方法（httpx 已自动处理编码）
            answer = response_data.get('answer', '')
            content = answer
            response_data = "blocking...\n" + json.dumps(response_data, ensure_ascii=False, indent=4)
        elif content_type.split(';')[0].strip() == 'text/event-stream':
            async for line in response.aiter_lines():  # 使用httpx原生流式迭代器
                response_data += "streaming...\n"
                line = line.strip().replace('data: ', '', 1)
                response_data += line + '\n'
                if not line or line == "[DONE]":
                    continue
                data = json.loads(line)
                if content := data.get('answer'):
                    answer += content
                    yield content
            content = ''
        else:
            raise ValueError(f"Unsupported response.content_type: {content_type}")
        logger.info(f'LLM response_data: ===\n{response_data}\n===')
        yield content

class LLMClient(BaseLLMClient):
    # 通用逻辑
    async def get_completion(self, params) -> str:
        answer = await super().get_completion(params)
        return answer

    async def get_stream_completion(self, params) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async for content in super().get_stream_completion(params):  # 直接复用父类的流处理
            yield content  # 逐块传递数据流

class OpenAIClient(BaseLLMClient):
    # 适配OpenAI通用逻辑
    async def get_completion(self, params) -> str:
        answer = await super().get_completion(params)
        return answer

    async def get_stream_completion(self, params) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async for content in super().get_stream_completion(params):  # 直接复用父类的流处理
            yield content  # 逐块传递数据流

class OtherClient(BaseLLMClient):
    # 适配其他平台特有逻辑
    async def get_completion(self, params) -> str:
        answer = await super().get_completion(params)
        return answer

    async def get_stream_completion(self, params) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async for content in super().get_stream_completion(params):  # 直接复用父类的流处理
            yield content  # 逐块传递数据流

class DifyClient(BaseLLMClient):
    # 适配Dify特有逻辑
    async def get_completion(self, params) -> str:
        answer = await super().get_completion(params)
        return answer

    async def get_stream_completion(self, params) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async for content in super().get_stream_completion(params):  # 直接复用父类的流处理
            yield content  # 逐块传递数据流

class FastGPTClient(BaseLLMClient):
    # 适配FastGPT特有逻辑
    async def get_completion(self, params) -> str:
        answer = await super().get_completion(params)
        answer =  answer.strip("0:")
        return answer

    async def get_stream_completion(self, params) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        first_chunk = True
        async for content in super().get_stream_completion(params):
            if first_chunk:
                content = content.replace('0:', '', 1).strip()  # 仅处理第一个chunk的前缀, 先去除'0:'再去除空格
                yield content
                first_chunk = False
            else:
                yield content

# async def get_completion(base_url, endpoint, headers, params, concurrency_limit=5, timeout=30):
#     base_url = base_url.rstrip('/') + '/' + endpoint.lstrip('/')
#     semaphore = asyncio.Semaphore(concurrency_limit)
#     param_json = params.model_dump()
#     logger.info(f"LLM request params: ---\n{param_json}\n---")

#     answer = ''
#     response_data = ''
#     try:
#         import aiohttp, asyncio
#         async with semaphore:
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(base_url, headers=headers, json=param_json, timeout=timeout) as response:
#                     # response.raise_for_status()  # 自动处理HTTP错误
#                     if response.status == 200:
#                         code = 0
#                         messages = 'LLM response session successfully'
#                         if response.content_type == 'application/json':
#                             response_data = await response.json()
#                             answer = response_data.get('answer', '')
#                         elif response.content_type == 'text/event-stream':
#                             encoding = response.charset
#                             async for line in response.content:
#                                 json_string = line.decode(encoding).strip().replace('data: ', '')
#                                 response_data += json_string + '\n'
#                                 if json_string == "[DONE]":
#                                     continue
#                                 if json_string:
#                                     try:
#                                         data = json.loads(json_string)
#                                         content = data.get('answer', '')
#                                         if content:
#                                             answer += content
#                                     except json.JSONDecodeError:
#                                         code = -1
#                                         logger.error(f"{messages}, JSONDecodeError, LLM Data Invalid JSON: {json_string}.")
#                         else:
#                             code = -1
#                             messages = f"{messages}, Unknown response.content_type: {response.content_type}"
#                     else:
#                         code = -1
#                         messages = f'LLM response failed with status code: {response.status}, text: {response.text}. '
#     except (asyncio.TimeoutError, json.JSONDecodeError, KeyError, Exception) as e:
#         error_type = type(e).__name__
#         code = -1
#         messages = f'{error_type}: {e}'
#     answer = answer[2:].strip() if answer[:2] in ("0:", "1:") else answer
#     if answer != '':
#         logger.info(f'{messages}, response_data: ===\n{response_data}\n===')
#     else:
#         if code != -1:
#             if response_data:
#                 messages = f"{messages}, ChatGPT response text is empty, response_data: ===\n{response_data}\n==="
#         logger.error(messages)
#     return answer
