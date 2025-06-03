from controllers.feishu_robot import FeishuRobot
from utils.logger import setup_logger, get_logger
import signal
import sys
import atexit


# 初始化日志
setup_logger()
logger = get_logger()

def graceful_shutdown(signum=None, frame=None):
    """处理优雅退出，支持信号和手动调用"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    # 执行清理逻辑（如关闭数据库连接等）
    if hasattr(graceful_shutdown, 'feishu_robot'):
        graceful_shutdown.feishu_robot.stop()
    logger.info("Service stopped.")
    sys.exit(0)


if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, graceful_shutdown)  # Ctrl+C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # kill
    # 注册atexit钩子（非信号触发的退出）
    atexit.register(graceful_shutdown)

    try:
        logger.info("Service starting...")
        feishu_robot = FeishuRobot()
        graceful_shutdown.feishu_robot = feishu_robot  # 保存引用供清理使用
        feishu_robot.start()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        graceful_shutdown()