"""导入所有模型，确保它们注册到同一个 Base.metadata。

[优化] 原项目没有这个文件，Alembic/`create_all` 只导入某个模型时，
其余表不会被注册，autogenerate 会误判为“需要删表”。
"""

from models.base import Base
from models.favorite import Favorite
from models.history import History
from models.news import Category, News
from models.users import User, UserToken

__all__ = ["Base", "Category", "Favorite", "History", "News", "User", "UserToken"]
