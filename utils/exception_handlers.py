"""注册全局异常处理器。"""

# 全局异常处理器（exception handler）：请求处理过程中抛出的任何异常，
# FastAPI 都会交给这里登记的函数，由它转成统一的 JSON 响应。
# 不在这一层统一处理的话，异常会变成默认的纯文本 500 加一大段堆栈，
# 前端拿到的就不是 {code, message, data} 这套固定结构了。
# 为什么单独放一个模块：main.py 里只留一行 register_exception_handlers(app)，
# 注册细节和具体怎么处理错误分开，改错误文案不用动启动代码。

from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.exception import (
    general_exception_handler,
    http_exception_handler,
    integrity_error_handler,
    sqlalchemy_error_handler,
    validation_exception_handler,
)


def register_exception_handlers(app):
    """给 FastAPI 应用挂上全部异常处理器。

    参数：
        app: FastAPI 应用实例，提供 add_exception_handler 方法。
    返回：
        没有返回值；副作用是把 5 个处理器登记到 app 上。
    """
    # [优化] 原来只注册 FastAPI 的 HTTPException，路由 404/405 等
    # StarletteHTTPException 不会被统一包裹；这里改为注册父类。
    # 之所以注册父类就能覆盖子类：匹配异常时是看“这个类是某处理器类型的子类吗”，
    # 注册 Starlette 的 HTTPException，FastAPI 的 HTTPException 自然也被它接住。
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    # 参数校验失败（必填字段缺失、类型不对等）走这里，统一成 422。
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # 数据库约束冲突（唯一键、外键）单独处理，才能给出“已收藏过”这类业务提示。
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    # 其他数据库错误（连接断开、SQL 语法错）统一成 500，并记完整堆栈。
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    # 兜底：以上都没匹配到的异常，也不能把堆栈直接扔给客户端。
    app.add_exception_handler(Exception, general_exception_handler)
