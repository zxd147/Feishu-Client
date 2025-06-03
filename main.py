from controllers.feishu_robot import FeishuRobot
from utils.logger import setup_logger, get_loger


if __name__ == "__main__":
    setup_logger()
    logger = get_loger()
    logger.info("Service starting...")
    feishu_robot = FeishuRobot()
    feishu_robot.start()



