import logging
from logging.handlers import RotatingFileHandler

# 创建日志记录器
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

# 创建日志格式
formatter = logging.Formatter(
    '%(asctime)s-%(name)s-%(filename)s-%(funcName)s-%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建文件处理器
file_handler = RotatingFileHandler('app.log', maxBytes=1024 * 1024, backupCount=5)  # 每个文件最大 1MB，保留 5 个备份
file_handler.setFormatter(formatter)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 添加处理器到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)