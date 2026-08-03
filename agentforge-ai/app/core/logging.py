"""统一日志格式：时间 - 级别 - 名称 - 消息（Docker 环境下以 JSON 行输出可选）。"""
import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:  # 幂等：避免 uvicorn --reload 重复注册
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    root.setLevel(level)
    root.addHandler(handler)
