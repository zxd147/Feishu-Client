import asyncio
import json

import lark_oapi as lark

from configs.settings import settings
from controllers.lark_client import Feishu
from controllers.llm_client import DifyClient
from utils.logger import get_logger

logger = get_logger()

class FeishuRobot:
    def __init__(self):
        self.processed_message_ids = set()  # 用于记录已处理的消息ID
        self.user_info = {}
        model_name = settings.fs_model_name
        base_url = settings.config.llm_models[model_name].base_url
        chat_endpoint = settings.config.llm_models[model_name].chat_endpoint
        conv_endpoint = settings.config.llm_models[model_name].conv_endpoint
        api_key = settings.dify_fs_secret
        concurrency_limit = settings.config.llm_models[model_name].concurrency_limit
        timeout = settings.config.llm_models[model_name].timeout
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.conv_limit = settings.config.llm_models[model_name].conv_limit
        self.params = settings.config.llm_param[model_name]
        self.max_retries = settings.max_retries
        self.feishu_client = None
        self.dify_fs_client = DifyClient(base_url, chat_endpoint, conv_endpoint, headers, concurrency_limit, timeout)
        logger.info("Dify client init success!")

    def start(self):
        # 注册事件 Register event
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(self.do_p2_im_message_receive_v1) \
            .build()
        # 初始化飞书客户端
        app_id = settings.app_id
        app_secret = settings.app_secret
        self.feishu_client = Feishu(app_id, app_secret, event_handler)
        logger.info("Feishu client running...")
        self.feishu_client.start()

    def stop(self):
        self.feishu_client.stop()

    def add_message_id(self, msg_id):
        self.processed_message_ids.add(msg_id)
        
        # 当集合大小超过1000时触发清理
        if len(self.processed_message_ids) > 1000:
            # 转换为列表并截取后半部分（保留最近添加的）
            ids_list = list(self.processed_message_ids)
            keep_ids = set(ids_list[len(ids_list)//2:])  # 取后50%
            self.processed_message_ids.clear()
            self.processed_message_ids.update(keep_ids)

    def do_p2_im_message_receive_v1(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """飞书消息处理入口 - 必须在3秒内响应确认，长任务应该异步处理"""
        # 尝试获取或创建事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()  # 手动创建
            asyncio.set_event_loop(loop)  # 将新循环绑定到当前线程
        # 提取消息基本信息
        event = data.event
        message = event.message
        message_id = message.message_id
        message_type = message.message_type
        chat_type = message.chat_type
        chat_id = message.chat_id
        sender = event.sender
        sender_id = sender.sender_id
        open_id = sender_id.open_id
        # user_id = sender_id.user_id
        # 检查是否已处理过
        if message_id in self.processed_message_ids:
            logger.info(f'忽略重复的消息: {message_id} {data.event.message.content}')
            return
        self.add_message_id(message_id)
        logger.debug(f'收到飞书消息: {lark.JSON.marshal(data, indent=4)}')
        # 用户信息
        user_name = self.feishu_client.get_user_name(open_id)
        conversation_id = self.user_info.setdefault(user_name, {}).setdefault('conversation_id', '')
        logger.info(f"用户: user_name={user_name}, open_id={open_id}, conversation_id={conversation_id}")

        # 处理文件类型消息
        if message_type == "text":
            # 解析用户消息
            try:
                content = data.event.message.content
                content_json = json.loads(content)
                text = content_json.get('text', '')
                logger.info(f"收到文字消息: message_id={message_id}, text={text}")
            except Exception as err:
                logger.error(f"消息处理异常: {err}")
                return  # 立即返回成功确认
            # 处理重置指令
            if text in {'重置', '清空对话。', '/reset'}:
                logger.info(f"准备发起新的会话")
                try:
                    self.user_info[user_name]["conversation_id"] = ''
                    self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text":"会话已重置"}))
                    logger.info(f'会话重置成功， 新的会话ID为 {self.user_info[user_name]["conversation_id"]}')

                    return  # 立即返回成功确认
                except Exception as err:
                    logger.error(f"会话重置信息发送失败: {err}")
                    return  # 立即返回成功确认
            
            # 异步处理复杂的消息处理逻辑，尽量减少同步处理时间, 避免超时
            try:
                # 创建异步任务并添加回调处理
                loop.create_task(self.text_messages_handler(user_name, chat_type, open_id, chat_id, text))
                logger.info("异步任务已后台提交到事件循环")
            except Exception as err:
                logger.error(f"用户信息处理失败: {message_id}, {str(err)}")
                return

        elif message_type == "file":
            # 解析文件信息
            try:
                content = data.event.message.content
                content_json = json.loads(content)
                file_key = content_json.get('file_key', '')
                file_name = content_json.get('file_name', '')
                logger.info(f"收到文件消息: message_id={message_id}, file_key={file_key}, file_name={file_name}")
                loop.create_task(self.file_message_handle("download_and_upload", message_id, chat_type, open_id, chat_id, file_key, file_name))
                # 发送消息告诉用户文件在处理中，请稍等
                self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "文件正在处理中，请稍等..."}))
                logger.info("异步任务已后台提交到事件循环")
                return
            except Exception as err:
                logger.error(f"解析文件消息异常: {str(err)}")
                self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "解析文件消息出错，请重试"}))
                return
        
        # 处理其他非文本消息
        else:
            self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", '{"text":"没有理解您的信息，我现在只支持文本和文件消息哦~"}')
            return  # 立即返回成功确认
        
    async def text_messages_handler(self, user_name, chat_type, open_id, chat_id, query):
        """处理消息的异步核心逻辑"""
        card_id = await self.feishu_client.create_card()
        sequence = 0
        # 发送初始卡片并确保流式更新模式开启
        response = await self.feishu_client.send_init_card(card_id, chat_type == "p2p", open_id, chat_id)
        sequence += 1
        logger.debug(f"飞书响应: code={response.code}, msg={response.msg}, data={getattr(response, 'data', None)}, log_id={response.get_log_id()}")

        params = self.params.model_dump()
        params["query"] = query
        params["user"] = user_name
        params["conversation_id"] = self.user_info[user_name]["conversation_id"]
        conv_params = {"user": user_name, "limit": self.conv_limit}
        kwargs = {"user_info": self.user_info, "conv_params": conv_params}
        # answer = await self.dify_fs_client.get_completion(params, **kwargs)
        # # 使用重试机制更新卡片
        # for retry in range(self.max_retries):
        #     try:
        #         # 使用asyncio.create_task来避免阻塞
        #         response = await self.feishu_client.update_card(card_id, answer, sequence)
        #         if sequence <= 1:
        #             logger.info(f"卡片更新成功！sequence={sequence}. ---\n... ...\n---")
        #             logger.debug(f"飞书响应: code={response.code}, msg={response.msg}, data={getattr(response, 'data', None)}, log_id={response.get_log_id()}---\n... ...\n---")
        #         else:
        #             logger.debug(f"卡片更新成功！sequence={sequence}. \n飞书响应: code={response.code}, msg={response.msg}, data={getattr(response, 'data', None)}, log_id={response.get_log_id()}")
        #         sequence += 1
        #         break
        #     except Exception as err:
        #         if retry < self.max_retries - 1:
        #             logger.warning(f"更新卡片失败 (重试 {retry+1}/{self.max_retries}): \n{str(err)}")
        #             await asyncio.sleep(0.2)  # 短暂等待后重试
        #         else:
        #             logger.error(f"更新卡片失败: {str(err)}")
        #             return None

        answer = ''
        generator = self.dify_fs_client.get_stream_completion(params, **kwargs)
        async for content in generator:
            if not content:
                continue    
            answer += content
            # 使用重试机制更新卡片
            for retry in range(self.max_retries):
                try:
                    # 使用asyncio.create_task来避免阻塞
                    response = await self.feishu_client.update_card(card_id, answer, sequence)
                    if sequence <= 1:
                        logger.info(f"卡片更新成功！sequence={sequence}. ---\n... ...\n---")
                        logger.debug(f"飞书响应: code={response.code}, msg={response.msg}, data={getattr(response, 'data', None)}, log_id={response.get_log_id()}---\n... ...\n---")
                    else:
                        logger.debug(f"卡片更新成功！sequence={sequence}. \n飞书响应: code={response.code}, msg={response.msg}, data={getattr(response, 'data', None)}, log_id={response.get_log_id()}")
                    sequence += 1
                    break
                except Exception as err:
                    if retry < self.max_retries - 1:
                        logger.warning(f"更新卡片失败 (重试 {retry+1}/{self.max_retries}): \n{str(err)}")
                        await asyncio.sleep(0.2)  # 短暂等待后重试
                    else:
                        logger.error(f"更新卡片失败: {str(err)}")
                        return None
        return None

    async def file_message_handle(self, operation_type, message_id, chat_type, open_id, chat_id, file_key=None, file_name=''):
        try:
            file_content = b''
            download_name = ''
            if "download" in operation_type:
                # 下载文件
                file_content, _ = await self.feishu_client.download_message_file(message_id, file_key)
                if not file_content:
                    logger.error(f"下载文件失败: file_key={file_key}, file_name={file_name}")
                    self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "文件下载失败，请重试"}))
                    return
                # 发送成功消息
                logger.info(f"文件下载成功!")
                self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "文件下载成功"}))
            elif "upload" in operation_type:
                # 上传文件
                file_name_to_use = file_name or download_name
                result = await self.feishu_client.upload_file_to_approval(file_content, file_name_to_use)
                if not result or "code" not in result:
                    logger.error(f"上传文件失败: {result}")
                    self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "上传文件失败，请重试"}))
                    return
                # 发送成功消息和文件code
                logger.info(f"文件上传成功!\n文件code: {result['code']}")
                self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "文件上传成功"}))
        except Exception as err:
            logger.error(f"处理文件异常: {str(err)}")
            self.feishu_client.send_common_message(chat_type == "p2p", open_id, chat_id, "text", json.dumps({"text": "处理文件时发生错误，请重试"}))
            return

    # async def chat(self, query):
    #     """微信消息处理核心逻辑"""
    #     # 获取配置
    #     params = copy.deepcopy(settings.config.llm_param[settings.fs_model_name])
    #     logger.info(f'Dify FS Request message: {query}')  # 查看消息解析是否正确
    #     # 回复文本消息示例
    #     params["query"] = query
    #     try:
    #         response_content = await self.dify_fs_client.get_completion(params)
    #         logger.info(f'Dify FS Response message: {response_content}')  # 查看消息解析是否正确
    #         return Response(content=response_content, media_type="application/xml")
    #     except Exception as error:
    #         logger.error(f'LLM response failed with error: {error}. ')
    #         raise

