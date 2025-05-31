import copy
import hashlib
import time

from fastapi import HTTPException
from fastapi.responses import Response

from configs.settings import settings
from controllers.llm_client import DifyClient
from utils.logger import get_loger
from utils.parse import generate_reply

logger = get_loger()


class WechatMp:
    def __init__(self):
        base_url = settings.config.llm_models[settings.mp_model_name].base_url
        endpoint = settings.config.llm_models[settings.mp_model_name].endpoint
        api_key = settings.dify_mp_secret or settings.config.llm_models[settings.mp_model_name].api_key
        concurrency_limit = settings.config.llm_models[settings.mp_model_name].concurrency_limit
        timeout = settings.config.llm_models[settings.mp_model_name].timeout
        self.model_name = settings.mp_model_name
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.dify_mp_client = DifyClient(base_url, endpoint, headers, concurrency_limit, timeout)

    @staticmethod
    def verify(signature, timestamp, nonce, echostr):
        """
        微信服务器验证核心逻辑
        """
        token = settings.wechat_mp_secret
        if not all([signature, timestamp, nonce, echostr]):
            raise HTTPException(status_code=400, detail="missing params")
        # 对 token、timestamp、nonce 进行字典序排序
        tmp_list = [token, timestamp, nonce]
        tmp_list.sort()
        # 拼接成字符串并进行 sha1 加密
        tmp_str = ''.join(tmp_list)
        logger.info(tmp_str)
        hash_code = hashlib.sha1(tmp_str.encode()).hexdigest()
        if hash_code != signature:
            raise HTTPException(status_code=403, detail="Invalid signature")
        logger.debug(f"verify success, echostr: {type(echostr)} =, {echostr}")
        return echostr


    async def chat(self, message):
        """微信消息处理核心逻辑"""
        # 获取配置
        params = copy.deepcopy(settings.config.llm_param[self.model_name])
        logger.info(f'Dify MP Request message: {message}')  # 查看消息解析是否正确
        # 回复文本消息示例
        query = message['Content']
        params.query = query
        try:
            response_content = await self.dify_mp_client.get_completion(params)
            # from controllers.llm_client import get_completion
            # response_content = await get_completion(self.base_url, self.endpoint, self.headers, params, concurrency_limit=5, timeout=30)
            logger.info(f'Dify MP Response message: {response_content}')  # 查看消息解析是否正确
            # 返回前端
            response_xml = generate_reply(message['FromUserName'], message['ToUserName'], int(time.time()), response_content)
            return Response(content=response_xml, media_type="application/xml")
        except Exception as error:
            logger.error(f'LLM response failed with error: {error}. ')
            raise


    # async def test():
    #     """测试用例"""
    #     model_name = settings.model_name
    #     base_url = settings.config.llm_models[model_name].base_url
    #     endpoint = settings.config.llm_models[model_name].endpoint
    #     api_key = "https://api.weixin.qq.com/cgi-bin/token"
    #     query = "你好"
    #     answer = await get_completion(base_url, endpoint, api_key, query)
    #     print(answer)


