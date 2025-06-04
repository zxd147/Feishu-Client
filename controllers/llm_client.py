import json
from contextlib import asynccontextmanager
from typing import Optional, Any, Callable, AsyncGenerator

import httpx

from utils.exception import log_exception
from utils.logger import get_logger

logger = get_logger()


class BaseLLMClient:
    def __init__(self, base_url, chat_endpoint, headers, concurrency_limit=10, timeout=30, callback_parser: Optional[Callable[[Any], Any]] = None, **kwargs):
        self.base_url = base_url
        self.chat_endpoint = chat_endpoint
        self.headers = headers
        self.parser = callback_parser or self._default_parser
        self.stream_parser = callback_parser or self._default_stream_parser
        self.make_request = self._make_request
        self.make_stream_request = self._make_stream_request
        # 配置连接池参数（等效于原TCPConnector）
        self.client = httpx.AsyncClient(base_url=base_url, limits=httpx.Limits(max_connections=concurrency_limit),
            timeout=httpx.Timeout(timeout), http2=True, follow_redirects=True)

    async def close(self):
        await self.client.aclose()  # 显式关闭连接池

    async def get_completion(self, params, **kwargs) -> str:
        """统一请求入口，子类可覆盖具体解析逻辑"""
        try:
            answer = await self.make_request(params, **kwargs)
            return answer
        except (httpx.HTTPError, httpx.RequestError, json.JSONDecodeError, KeyError, Exception) as exc:
            log_exception(exc)
            return "调用LLM平台报错"

    async def get_stream_completion(self, params, **kwargs) -> AsyncGenerator[str, None]:
        """统一流式请求入口，子类可覆盖具体解析逻辑"""
        try:
            async with self.make_stream_request(params, **kwargs) as generator:
                async for content in generator:
                    yield content
        except (httpx.HTTPError, httpx.RequestError, httpx.StreamError, httpx.RemoteProtocolError, json.JSONDecodeError, KeyError, Exception) as exc:
            log_exception(exc)
            yield "调用LLM平台报错"

    async def _make_request(self, params, **kwargs):
        """异步HTTP请求核心实现（httpx版）"""
        try:
            logger.info(f"LLM request params: ---\n{params}\n---")
            async with self.client.stream("POST", self.chat_endpoint, headers=self.headers, json=params) as response:
                answer = await self.parser(response)  # 使用注入的解析器
            return answer
        except httpx.HTTPStatusError as exc:
            logger.error(f'LLM response failed with status code: {exc.response.status_code}, text: {exc.response.text}')
            raise

    @asynccontextmanager
    async def _make_stream_request(self, params, **kwargs):
        """异步流式HTTP请求核心实现（httpx版）"""
        gen = None  # 显式初始化变量
        try:
            logger.info(f"LLM request params: ---\n{params}\n---")
            async with self.client.stream("POST", self.chat_endpoint, headers=self.headers, json=params) as response:
                gen = self.stream_parser(response)  # 使用注入的解析器
                yield gen
        except httpx.HTTPStatusError as exc:
            logger.error(f'LLM response failed with status code: {exc.response.status_code}, text: {exc.response.text}')
            raise
        finally:
            if hasattr(gen, 'aclose'):  # 检查是否为生成器
                await gen.aclose()  # 显式关闭

    async def _default_parser(self, response) -> str:
        """默认解析逻辑, 动态解析响应：支持JSON和SSE"""
        await self.assert_response(response)
        content_type = (getattr(response, 'content_type', None) or response.headers.get('Content-Type', '') or '').lower()
        if content_type.split(';')[0].strip() == 'application/json':
            response_data = "blocking...\n"
            _, answer, response_data = await self.parse_json_response(response, response_data)
        elif content_type.split(';')[0].strip() == 'text/event-stream':
            answer = ''
            response_data = "streaming...\n"
            async for line in response.aiter_lines():
                content, answer, response_data = await self.parse_event_stream(line, answer, response_data)
                if content is None:
                    continue
        else:
            raise ValueError(f"Unsupported response.content_type: {content_type}")
        logger.info(f'LLM response data[:500]: ===\n{response_data[:500]}\n===')
        logger.info(f'LLM answer: {answer}')
        return answer

    async def _default_stream_parser(self, response) -> AsyncGenerator[str, None]:
        """默认解析逻辑, 动态解析响应：支持JSON和SSE"""
        await self.assert_response(response)
        content_type = (getattr(response, 'content_type', None) or response.headers.get('Content-Type', '') or '').lower()
        if content_type.split(';')[0].strip() == 'application/json':
            response_data = "blocking...\n"
            content, answer, response_data = await self.parse_json_response(response, response_data)
        elif content_type.split(';')[0].strip() == 'text/event-stream':
            answer = ''
            response_data = "streaming...\n"
            async for line in response.aiter_lines():
                content, answer, response_data = await self.parse_event_stream(line, answer, response_data)
                if content is None:
                    continue
                yield content
            content = ''
        else:
            raise ValueError(f"Unsupported response.content_type: {content_type}, text: {(await response.aread()).decode('utf-8')}.")
        logger.info(f'LLM response data[:500]: ===\n{response_data[:500]}\n===')
        logger.info(f'LLM answer: ===\n{answer}\n===')
        yield content

    @staticmethod
    async def assert_response(response):
        assert response.status_code == 200, f"LLM response session failed with status code: {response.status_code}, text: {(await response.aread()).decode('utf-8')}."
        logger.info(f'LLM response session successfully with status code: {response.status_code}')

    @staticmethod
    async def parse_json_response(response, response_data):
        response_json = (await response.aread()).decode('utf-8')  # 显式读取字节流按数据, 解码为字符串
        response_dict = json.loads(response_json)
        content = response_dict['choices'][0]['message'].get('content', '')
        if isinstance(content, list):
            content = next((item['text']['content'] for item in content if item.get('type') == 'text'), content)
        response_data += response_json + '\n'
        answer = content
        return content, answer, response_data

    @staticmethod
    async def parse_event_stream(line, answer, response_data):
        response_data += line + '\n'
        line = line.strip().replace('data: ', '', 1)
        if not line or line == "[DONE]" or not line.startswith("{"):
            return None, answer, response_data
        data = json.loads(line)
        choice = data['choices'][0]
        if content := choice['delta'].get('content', ''):
            answer += content
        return content, answer, response_data

class LLMClient(BaseLLMClient):
    # 通用逻辑
    async def get_completion(self, params, **kwargs) -> str:
        answer = await super().get_completion(params, **kwargs)
        return answer

    async def get_stream_completion(self, params, **kwargs) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async with super().get_stream_completion(params, **kwargs) as generator:  # 直接复用父类的流处理
            async for content in generator:
                yield content  # 逐块传递数据流

class OpenAIClient(BaseLLMClient):
    # 适配OpenAI通用逻辑
    async def get_completion(self, params, **kwargs) -> str:
        answer = await super().get_completion(params, **kwargs)
        return answer

    async def get_stream_completion(self, params, **kwargs) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async with super().get_stream_completion(params, **kwargs) as generator:  # 直接复用父类的流处理
            async for content in generator:
                yield content  # 逐块传递数据流

class OtherClient(BaseLLMClient):
    # 适配其他平台特有逻辑
    async def get_completion(self, params, **kwargs) -> str:
        answer = await super().get_completion(params, **kwargs)
        return answer

    async def get_stream_completion(self, params, **kwargs) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async with super().get_stream_completion(params, **kwargs) as generator:  # 直接复用父类的流处理
            async for content in generator:
                yield content  # 逐块传递数据流

class DifyClient(BaseLLMClient):
    # 适配Dify特有逻辑

    def __init__(self, base_url, chat_endpoint, conv_endpoint, headers, concurrency_limit, timeout, **kwargs):
        super().__init__(base_url, chat_endpoint, headers, concurrency_limit, timeout, **kwargs)
        self.conv_endpoint = conv_endpoint

    async def _make_request(self, params, **kwargs):
        """异步HTTP请求核心实现（httpx版）"""
        try:
            user_info = kwargs.get("user_info")  # 从kwargs获取
            conv_params = kwargs.get("conv_params")  # 从kwargs获取
            user_name = params["user"]
            logger.info(f"LLM request params: ---\n{params}\n---")
            async with self.client.stream("POST", self.chat_endpoint, headers=self.headers, json=params) as response:
                if not user_info[user_name]["conversation_id"]:
                    await self.update_conversation_id(user_name, user_info, conv_params)
                answer = await self.parser(response)  # 使用注入的解析器
            return answer
        except httpx.HTTPStatusError as exc:
            logger.error(f'LLM response failed with status code: {exc.response.status_code}, text: {exc.response.text}')
            raise

    @asynccontextmanager
    async def _make_stream_request(self, params, **kwargs):
        """异步流式HTTP请求核心实现（httpx版）"""
        try:
            conv_params = kwargs.get("conv_params")  # 从kwargs获取
            user_info = kwargs.get("user_info")  # 从kwargs获取
            user_name = params["user"]
            logger.info(f"LLM request params: ---\n{params}\n---")
            async with self.client.stream("POST", self.chat_endpoint, headers=self.headers, json=params) as response:
                if not user_info[user_name]["conversation_id"]:
                    await self.update_conversation_id(user_name, user_info, conv_params)
                gen = self.stream_parser(response)  # 使用注入的解析器
                yield gen
        except httpx.HTTPStatusError as exc:
            logger.error(f'LLM response failed with status code: {exc.response.status_code}, text: {exc.response.text}')
            raise
        finally:
            if hasattr(gen, 'aclose'):  # 检查是否为生成器
                await gen.aclose()  # 显式关闭

    @staticmethod
    async def parse_json_response(response, response_data):
        response_json = (await response.aread()).decode('utf-8')  # 显式读取字节流按数据, 解码为字符串
        response_dict = json.loads(response_json)
        content = response_dict.get('answer', '')
        response_data += response_json + '\n'
        answer = content
        return content, answer, response_data

    @staticmethod
    async def parse_event_stream(line, answer, response_data):
        response_data += line + '\n'
        line = line.strip().replace('data: ', '', 1)
        if not line or line == "[DONE]" or not line.startswith("{"):
            return None, answer, response_data
        data = json.loads(line)
        if content := data.get('answer', ''):
            answer += content
        return content, answer, response_data

    async def update_conversation_id(self, user_name, user_info, conv_params):
        get_response = await self.client.get(self.conv_endpoint, params=conv_params, headers=self.headers)
        conv_data = get_response.json()
        conv_list = conv_data.get("data", [])
        logger.debug(f"获取到的conversations id列表: {conv_list}")
        new_conversations_id = conv_list[0]["id"]
        old_conversations_id = user_info[user_name].get("conversation_id")
        user_info[user_name]["conversation_id"] = new_conversations_id
        logger.info(f'已获取到conversations id列表，将```{user_name}```的conversations id从```{old_conversations_id}```更新为```{new_conversations_id}```')

class FastGPTClient(BaseLLMClient):
    # 适配FastGPT特有逻辑
    async def get_completion(self, params, **kwargs) -> str:
        answer = await super().get_completion(params, **kwargs)
        return answer

    async def get_stream_completion(self, params, **kwargs) -> AsyncGenerator[str, None]:
        """重写父类方法，保持异步生成器类型"""
        async with super().get_stream_completion(params, **kwargs) as generator:  # 直接复用父类的流处理
            async for content in generator:
                yield content  # 逐块传递数据流

    @staticmethod
    async def parse_json_response(response, response_data):
        content, answer, response_data = await super().parse_json_response(response, response_data)
        content = content.replace('0:', '', 1).replace('1:', '', 1).strip()
        answer = content
        return content, answer, response_data

    @staticmethod
    async def parse_event_stream(line, answer, response_data):
        content, answer, response_data = await super().parse_event_stream(line, answer, response_data)
        answer = answer.replace('0:', '', 1).replace('1:', '', 1).strip()
        return content, answer, response_data






























# async def get_completion(base_url, chat_endpoint, headers, params, concurrency_limit=5, timeout=30):
#     base_url = base_url.rstrip('/') + '/' + chat_endpoint.lstrip('/')
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
