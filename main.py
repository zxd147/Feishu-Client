import signal
import sys

from controllers.feishu_robot import FeishuRobot
from utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger()

def graceful_shutdown(signum=None, frame=None):
    """信号驱动的优雅退出，无需依赖.stop()方法"""
    logger.warning(f"Received signal {signum or 'manual'}, shutting down...")
    # 执行非异步的清理逻辑（如关闭文件、数据库连接等）
    # 示例：手动释放资源（替代.stop()）
    if hasattr(graceful_shutdown, 'feishu_robot'):
        logger.warning("Releasing Feishu resources...")
        # 直接释放关键资源（根据实际需求调整）
        graceful_shutdown.feishu_robot.stop()  # 假设FeishuRobot有stop方法
        del graceful_shutdown.feishu_robot
    logger.info("Service stopped.")
    sys.exit(0)

if __name__ == "__main__":
    # 注册信号处理
    signal.signal(signal.SIGINT, graceful_shutdown)  # Ctrl+C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # kill
    try:
        feishu_robot = FeishuRobot()
        graceful_shutdown.feishu_robot = feishu_robot  # 保存引用供清理使用
        logger.info("Service starting...")
        feishu_robot.start()
    except KeyboardInterrupt:
        logger.warning("Service stoping...")
        graceful_shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        graceful_shutdown()

