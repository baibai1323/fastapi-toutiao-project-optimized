"""缓存层使用的 Pydantic 模型。

[优化] 原代码缓存命中后执行 `[News(**item) for item in cached_list]`，
把字典重新塞回 ORM 实体。ORM 实体依赖 Session，字段名/别名一变就报
TypeError，而且把缓存层和数据库层耦合死了。
这里直接复用接口 Schema，缓存进出都是纯数据对象。
"""

from schemas.news import CategoryResponse, NewsDetailResponse, NewsItemBase, RelatedNewsResponse

CachedCategory = CategoryResponse
CachedNewsItem = NewsItemBase
CachedNewsDetail = NewsDetailResponse
CachedRelatedNews = RelatedNewsResponse
