import logging
import sys
import os
from logging.handlers import RotatingFileHandler

# 日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class ColorFormatter(logging.Formatter):
    """
    带颜色和图标的日志格式化器
    """
    # 颜色代码
    grey = "\x1b[38;20m"
    cyan = "\x1b[36;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    # 图标映射
    ICONS = {
        logging.DEBUG: "🐞",
        logging.INFO: "ℹ️ ",
        logging.WARNING: "⚠️ ",
        logging.ERROR: "❌",
        logging.CRITICAL: "🚨"
    }

    def __init__(self, datefmt=None):
        super().__init__(datefmt=datefmt)
        
        # 基础格式
        base_fmt = "%(asctime)s {color}{icon} %(levelname)-8s{reset} - {color}[%(filename)s:%(lineno)d]{reset} - %(message)s"
        
        self.FORMATS = {
            logging.DEBUG: base_fmt.format(color=self.cyan, icon=self.ICONS[logging.DEBUG], reset=self.reset),
            logging.INFO: base_fmt.format(color=self.green, icon=self.ICONS[logging.INFO], reset=self.reset),
            logging.WARNING: base_fmt.format(color=self.yellow, icon=self.ICONS[logging.WARNING], reset=self.reset),
            logging.ERROR: base_fmt.format(color=self.red, icon=self.ICONS[logging.ERROR], reset=self.reset),
            logging.CRITICAL: base_fmt.format(color=self.bold_red, icon=self.ICONS[logging.CRITICAL], reset=self.reset)
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, self.datefmt)
        return formatter.format(record)

def setup_logging(level=logging.DEBUG):
    """
    配置全局日志
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 移除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    # 使用自定义的颜色格式化器
    console_handler.setFormatter(ColorFormatter(DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # 移除文件日志处理器，直接输出到控制台
    # log_dir = "logs"
    # if not os.path.exists(log_dir):
    #     os.makedirs(log_dir)
    # 
    # file_handler = RotatingFileHandler(
    #     os.path.join(log_dir, "app.log"),
    #     maxBytes=10*1024*1024,  # 10MB
    #     backupCount=5,
    #     encoding="utf-8"
    # )
    # file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    # root_logger.addHandler(file_handler)

    # 降低一些嘈杂库的日志级别
    logging.getLogger("jira.resilientsession").setLevel(logging.ERROR)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def get_logger(name: str):
    """
    获取指定名称的日志记录器
    """
    return logging.getLogger(name)
