import json

from utils.logger import get_logger
import inspect

logger = get_logger()


def log_exception(exc):
    # 获取调用栈信息（跳过当前帧）
    caller_frame = inspect.stack()[1]
    caller_name = caller_frame.function
    exc_type = type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        error_msg = (
            f"JSON解析失败: {exc.msg}\n"
            f"错误位置: 第{exc.lineno}行第{exc.colno}列 (字符{exc.pos})\n"
            f"原始数据: {exc.doc}"  # 这里会输出原始 JSON 字符串
        )
        logger.error(f"{caller_name}: {exc_type}: {error_msg}")
    else:
        logger.error(f"{caller_name}: HTTP错误: {exc_type}: {exc}")

