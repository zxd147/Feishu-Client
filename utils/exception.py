import json

from utils.logger import get_loger

logger = get_loger()


def log_exception(exc):
    exc_type = type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        error_msg = (
            f"JSON解析失败: {exc.msg}\n"
            f"错误位置: 第{exc.lineno}行第{exc.colno}列 (字符{exc.pos})\n"
            f"原始数据: {exc.doc}"  # 这里会输出原始 JSON 字符串
        )
        logger.error(f"get_stream_completion: {exc_type}: {error_msg}")
    else:
        logger.error(f"get_completion: HTTP错误: {exc_type}: {exc}")

