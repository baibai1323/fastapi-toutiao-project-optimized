"""日志配置。

[优化] 原项目用 print 输出缓存/浏览量错误，生产环境无法采集、无法关联请求。
修复：统一 logging，格式包含时间、级别、logger、request_id（由中间件写入日志行）。
"""

from __future__ import annotations

import logging
import sys

from config.settings import DEBUG


def setup_logging() -> None:
    """在应用启动时配置一遍全局日志。

    参数：
        无。日志级别、输出位置都从配置和代码里定死，不需要调用方传参。
    返回：
        没有返回值；副作用是改掉根 logger（root logger）的级别和输出目标。
    """
    # 日志级别（level）：DEBUG < INFO < WARNING < ERROR，设成某级就只输出该级及以上。
    # 开发时用 DEBUG 看细节，生产用 INFO，避免日志被大量调试信息刷屏。
    level = logging.DEBUG if DEBUG else logging.INFO
    # handler（处理器）：决定日志往哪里写。这里写标准输出，
    # 因为容器/云平台默认就是采集 stdout，写文件反而要自己处理切割和权限。
    handler = logging.StreamHandler(sys.stdout)
    # formatter（格式器）：每行日志长什么样。
    # %(asctime)s 时间、%(levelname)-8s 级别（左对齐补到 8 字符）、
    # %(name)s 是打日志的模块名、%(message)s 是正文。
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # 根 logger 是所有 logger 的祖先：子 logger 没单独配置时都往这里冒泡，
    # 所以只配它一处，全项目生效。
    root = logging.getLogger()
    # 先清掉已有 handler：在 uvicorn --reload 或测试里，模块可能被导入多次，
    # 不清就会叠加多个 handler，同一行日志打两遍、三遍。
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 降低第三方库噪音
    # 原因是 httpx 每次请求、sqlalchemy 每条 SQL 都会打 INFO，
    # 级别提到 WARNING 后只保留真正值得注意的告警。
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
