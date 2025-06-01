# SDK 使用说明 SDK user guide：https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development
import asyncio
import io
import json
import traceback
import uuid

import lark_oapi as lark
import requests
from lark_oapi.api.cardkit.v1 import ContentCardElementRequest, ContentCardElementRequestBody, \
    ContentCardElementResponse, CreateCardRequest, CreateCardRequestBody, CreateCardResponse
from lark_oapi.api.contact.v3 import *
from lark_oapi.api.im.v1 import *

from utils.logger import get_loger

logger = get_loger()


class Feishu:
    card_template = {
        "schema": "2.0",
        "config": {
            "streaming_mode": True,
            "summary": {
                "content": "[思考中]"
            },
            "streaming_config": {
                "print_frequency_ms": {
                    "default": 20,
                    "android": 15,
                    "ios": 25,
                    "pc": 30
                },

                "print_step": {
                    "default": 2,
                    "android": 3,
                    "ios": 4,
                    "pc": 5
                },

                "print_strategy": "fast",
            }
        },
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "content": "思考中",
                    "element_id": "markdown_1"
                }
            ]
        }
    }

    def __init__(self, client_id, client_secret, event_handler):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cli = lark.ws.Client(client_id, client_secret, event_handler=event_handler, log_level=lark.LogLevel.DEBUG)
        self.client = lark.Client.builder().app_id(client_id).app_secret(client_secret).build()

    def start(self):
        self.cli.start()

    def stop(self):
        try:
            # 优先使用get_running_loop()（Python 3.7+）
            loop = asyncio.get_running_loop()
            loop.create_task(self.cli._disconnect())  # 异步调度
        except RuntimeError:  # 无运行循环时
            # 创建新循环并同步执行
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.cli._disconnect())
            finally:
                loop.close()

    async def create_card(self):
        # 创建卡片 https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/cardkit-v1/card/create
        card_create_request: CreateCardRequest = CreateCardRequest.builder() \
            .request_body(CreateCardRequestBody.builder()
                          .type("card_json")
                          .data(json.dumps(self.card_template)
                                ).build()).build()

        # 发起请求
        card_create_response: CreateCardResponse = self.client.cardkit.v1.card.create(card_create_request)
        if not card_create_response.success():
            logger.error(
                f"client.cardkit.v1.card.create failed, code: {card_create_response.code}, msg: {card_create_response.msg}, log_id: {card_create_response.get_log_id()}, resp: \n{json.dumps(json.loads(card_create_response.raw.content), indent=4, ensure_ascii=False)}")
            return None

        return card_create_response.data.card_id

    async def send_card(self, card_id, is_p2p, open_id, chat_id):

        if is_p2p:
            response = self._send_message("open_id", open_id, "interactive", "{\"type\":\"card\",\"data\":{\"card_id\":\"" + card_id + "\"}}")
        else:
            response = self._send_message("chat_id", chat_id, "interactive", "{\"type\":\"card\",\"data\":{\"card_id\":\"" + card_id + "\"}}")
        return response

    async def update_card(self, card_id, content, sequence=0):
        # 添加重试机制
        max_retries = 3
        retry_delay = 0.5  # 减少初始重试延迟

        for retry in range(max_retries):
            try:
                request: ContentCardElementRequest = ContentCardElementRequest.builder() \
                    .card_id(card_id) \
                    .element_id("markdown_1") \
                    .request_body(ContentCardElementRequestBody.builder()
                                  .uuid(str(uuid.uuid4()))
                                  .content(content)
                                  .sequence(sequence)
                                  .build()) \
                    .build()
                response: ContentCardElementResponse = self.client.cardkit.v1.card_element.content(request)
                if not response.success():
                    raise Exception(
                        f"client.im.v1.chat.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
                    )
                return response
            except Exception as e:
                if "Server Internal Error" in str(e) and retry < max_retries - 1:
                    logger.warning(f"飞书服务器错误，第{retry+1}次重试，将在{retry_delay}秒后重试")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # 减少指数退避增长率
                    return None
                else:
                    if retry == max_retries - 1:
                        logger.error(f"更新卡片失败，已重试{max_retries}次: {str(e)}")
                    raise  # 重试用尽，重新抛出

    # 发送消息
    # Send a message
    # # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        return None

    def _send_message(self, receive_id_type, receive_id, msg_type, content):
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        response = self.client.im.v1.message.create(request)
        if not response.success():
            raise Exception(
                f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
        return response

    def send_common_message(self, is_p2p, open_id,chat_id, msg_type, content):
        if is_p2p:
            self._send_message("open_id", open_id, msg_type, content)
        else:
            self._send_message("chat_id", chat_id, msg_type, content)

    def get_user_name(self, open_id):
        # 构造请求对象
        request: GetUserRequest = GetUserRequest.builder() \
            .user_id(open_id) \
            .user_id_type("open_id") \
            .build()

        # 发起请求
        response: GetUserResponse = self.client.contact.v3.user.get(request)
        #输出response

        logger.info(f"client.contact.v3.user.get , code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.contact.v3.user.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
            return None

        return response.data.user.name

    async def download_message_file(self, message_id, file_key):
        """
        下载聊天消息中的文件
        :params message_id: 消息ID
        :params file_key: 文件的唯一标识
        :return: (file_content, file_name) 文件二进制内容和文件名
        """
        logger.info(f"开始下载消息文件: message_id={message_id}, file_key={file_key}")
        try:
            # 构造请求获取文件资源
            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(file_key) \
                .type("file") \
                .build()

            # 发起请求
            response = self.client.im.v1.message_resource.get(request)

            # 处理失败返回
            if not response.success():
                logger.error(
                    f"下载文件失败: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
                )
                return None, None

            # 从响应中获取文件内容和文件名
            file_content = response.file.read()
            file_name = response.file_name

            logger.info(f"文件下载成功: {file_name}, 大小: {len(file_content)} 字节")
            return file_content, file_name

        except Exception as e:
            logger.error(f"下载文件异常: {str(e)}")
            logger.error(traceback.format_exc())
            return None, None

    async def upload_file_to_approval(self, file_content, file_name, file_type="attachment"):
        """
        上传文件到审批系统
        :params file_content: 文件二进制内容
        :params file_name: 文件名
        :params file_type: 文件类型，attachment表示附件，image表示图片
        :return: 文件code和url的字典
        """
        logger.info(f"开始上传文件到审批系统: {file_name}")
        try:
            # 直接使用requests获取tenant_access_token，避免SDK兼容性问题
            token_url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
            token_data = {
                "app_id": self.client_id,
                "app_secret": self.client_secret
            }

            token_response = requests.post(token_url, json=token_data)
            token_result = token_response.json()

            if token_response.status_code != 200 or token_result.get('code') != 0:
                logger.error(f"获取tenant_access_token失败: {token_result}")
                return None

            tenant_access_token = token_result.get('tenant_access_token')

            # 准备上传文件
            url = "https://www.feishu.cn/approval/openapi/v2/file/upload"
            headers = {
                "Authorization": f"Bearer {tenant_access_token}"
            }

            # 准备multipart/form-data格式的数据，与Java代码保持一致
            files = {
                'content': (file_name, io.BytesIO(file_content)),
            }
            data = {
                'name': file_name,
                'type': file_type
            }

            # 发送请求
            response = requests.post(url, headers=headers, files=files, data=data)

            # 检查响应
            if response.status_code != 200:
                logger.error(f"上传文件到审批系统失败: status_code={response.status_code}, response={response.text}")
                return None

            # 解析响应
            result = response.json()
            if result.get('code') != 0:
                logger.error(f"上传文件到审批系统响应错误: {result}")
                return None

            file_code = result.get('data', {}).get('code')
            file_url = result.get('data', {}).get('url')

            logger.info(f"文件上传成功: code={file_code}, url={file_url}")
            return {
                'code': file_code,
                'url': file_url
            }

        except Exception as e:
            logger.error(f"上传文件到审批系统异常: {str(e)}")
            logger.error(traceback.format_exc())
            return None
            
            