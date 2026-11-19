"""日志配置。

[优化] 原项目用 print 输出缓存/浏览量错误，生产环境无法采集、无法关联请求。
修复：统一 logging，格式包含时间、级别、logger、request_id（由中间件写入日志行）。
"""

from __future__ import annotations

import logging
import sys

from config.settings import DEBUG


def setup_logging() -> None:
    level = logging.DEBUG if DEBUG else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 降低第三方库噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
