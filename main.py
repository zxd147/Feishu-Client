import asyncio
import signal

from models.exception_model import SigIntException, SigTermException, ShutdownSignalException
from controllers.feishu_robot import FeishuRobot
from controllers.lark_client import loop
from utils.exception import single_exception
from utils.logger import setup_logger, get_logger
from utils.status import async_keep_alive, graceful_shutdown


# 初始化日志
setup_logger()
logger = get_logger()
# 注册信号处理
signal.signal(signal.SIGINT, graceful_shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, graceful_shutdown)  # kill

if __name__ == "__main__":
    try:
        logger.info("Service starting...")
        feishu_robot = FeishuRobot()
        feishu_robot.run()
        task = loop.create_task(async_keep_alive())
        graceful_shutdown.feishu_robot = feishu_robot  # 保存引用供清理使用
        graceful_shutdown.task = task  # 保存引用供清理使用
        loop.run_until_complete(task)
    except (SigIntException, SigTermException, ShutdownSignalException, asyncio.CancelledError, Exception) as exc:
        single_exception(exc)
    finally:
        if not hasattr(graceful_shutdown, '_is_cleaning'):
            graceful_shutdown()  # 确保无论如何都会清理


