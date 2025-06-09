import signal
import sys

from controllers.feishu_robot import FeishuRobot
from utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger()

def graceful_shutdown(signum=None, frame=None):
    """信号驱动的优雅退出"""
    if hasattr(graceful_shutdown, "_is_cleaning"):  # 防止重复调用
        return
    graceful_shutdown._is_cleaning = True  # 加标记
    logger.warning(f"Received signal {signum or 'exception'}, shutting down...")
    # 执行非异步的清理逻辑（如关闭文件、数据库连接等）
    if hasattr(graceful_shutdown, 'feishu_robot'):
        logger.warning("Releasing Feishu resources...")
        # 直接释放关键资源（根据实际需求调整）
        graceful_shutdown.feishu_robot.terminate()
        del graceful_shutdown.feishu_robot
    exit_code = 0 if signum in (signal.SIGINT, signal.SIGTERM) else 1
    logger.info(f"Service terminated, will exit with code {exit_code}.")
    sys.exit(exit_code)

# 注册信号处理
signal.signal(signal.SIGINT, graceful_shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, graceful_shutdown)  # kill

if __name__ == "__main__":
    try:
        logger.info("Service starting...")
        feishu_robot = FeishuRobot()
        graceful_shutdown.feishu_robot = feishu_robot  # 保存引用供清理使用
        feishu_robot.run()
    except Exception as e:
        logger.error(f"Service fatal error: {str(e)}", exc_info=True)
        graceful_shutdown()
    finally:
        if not hasattr(graceful_shutdown, '_is_cleaning'):
            graceful_shutdown()  # 确保无论如何都会清理

