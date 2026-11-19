# XWZX News API · 优化版

> GitHub：<https://github.com/baibai1323/fastapi-toutiao-project-optimized>

一个基于 **FastAPI + SQLAlchemy 2.0 Async + MySQL + Redis** 的新闻资讯后端，配套 Vue 3 移动端。
本仓库是原 `fastapi-toutiao-project` 的重构版：保留原有业务与目录风格，逐项修复了原项目中的契约、安全、缓存、索引和事务问题，并在代码中用中文注释标出 **原代码 / 问题 / 修复**。

> 原项目保持只读、未被修改；本仓库是独立副本。

---

## 1. 技术栈

| 层 | 技术 |
|---|---|
| Web | FastAPI、Pydantic v2、Uvicorn |
| 数据 | SQLAlchemy 2.0 Async、aiomysql、MySQL 8 |
| 缓存 | Redis（redis.asyncio），Cache-Aside |
| 鉴权 | Bearer Token，服务端只存 SHA-256 摘要 |
| AI | 阿里云百炼 DashScope，OpenAI 兼容接口，SSE 流式转发 |
| 前端 | Vue 3、Vite、Pinia、Vant、vue-i18n |
| 质量 | pytest + httpx ASGITransport、Ruff |

---

## 2. 快速启动

### 2.1 准备

- Python 3.11+
- MySQL 8.0+
- Redis 6+
- Node.js 18+（前端）

### 2.2 后端

```bash
# 1) 建库并导入表结构与示例数据
mysql -u root -p < 02-数据库sql文件/database.sql

# 2) 创建虚拟环境并安装依赖
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
pip install -r requirements.txt

# 3) 配置环境变量
copy env.example .env        # Windows
cp env.example .env          # macOS / Linux
# 编辑 .env：DATABASE_URL、REDIS_URL、DASHSCOPE_API_KEY

# 4) 启动
uvicorn main:app --reload --port 8000
```

- Swagger：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

> 旧库升级：先备份，再执行 `02-数据库sql文件/migration_v2.sql`。
> **新库不要执行 migration**，`database.sql` 已包含全部索引与唯一约束。

### 2.3 前端

```bash
cd 03-前端项目代码/xwzx-news
npm install
copy env.example .env.local   # 可选：VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

开发环境默认走 Vite 代理 `/api → http://127.0.0.1:8000`；生产环境把 `VITE_API_BASE_URL` 指向后端地址。

### 2.4 Docker（仅后端 + MySQL + Redis）

```bash
copy env.example .env
# 至少设置 MYSQL_ROOT_PASSWORD、DASHSCOPE_API_KEY
docker compose up -d --build
```

`docker-compose.yml` 会在 MySQL 首次初始化时自动执行 `database.sql`。

---

## 3. 目录结构

```text
.
├─ main.py                     # 应用入口：lifespan、CORS、GZip、请求日志、health
├─ config/
│  ├─ settings.py              # 环境变量集中配置
│  ├─ db_conf.py               # 异步引擎/会话（不自动 commit）
│  └─ cache_conf.py            # Redis 连接、超时、TTL 抖动
├─ models/                     # 统一 Base；User/News/Favorite/History
├─ schemas/                    # Pydantic v2；CamelModel 统一 camelCase
├─ crud/                       # 数据访问与事务
├─ cache/                      # 新闻缓存（Pydantic 进出，不重建 ORM）
├─ routers/                    # 5 个业务路由，统一 /api/v1
├─ utils/                      # 鉴权、密码、响应、异常、限流、日志
├─ tests/                      # 接口级回归测试（SQLite）
├─ 02-数据库sql文件/            # database.sql / migration_v2.sql
└─ 03-前端项目代码/xwzx-news/   # Vue 3 前端
```

---

## 4. 接口一览

统一前缀 `/api/v1`，统一响应：

```json
{ "code": 200, "message": "success", "data": {} }
```

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/` | - | 服务信息 |
| GET | `/health` | - | DB + Redis 健康检查 |
| POST | `/api/v1/user/register` | - | 注册（用户名/密码校验） |
| POST | `/api/v1/user/login` | - | 登录（5 次/5 分钟限流） |
| POST | `/api/v1/user/logout` | ✅ | 吊销当前 Token |
| GET | `/api/v1/user/info` | ✅ | 当前用户 |
| PUT | `/api/v1/user/update` | ✅ | 修改资料 |
| PUT | `/api/v1/user/password` | ✅ | 改密并吊销全部 Token |
| GET | `/api/v1/news/categories` | - | 分类列表 |
| GET | `/api/v1/news/list` | - | 分页列表，`categoryId/page/pageSize` |
| GET | `/api/v1/news/detail` | - | 详情（只读，不写浏览量） |
| POST | `/api/v1/news/{id}/view` | - | 浏览计数（IP 限流 30/60s） |
| GET | `/api/v1/favorite/check` | ✅ | 是否已收藏 |
| POST | `/api/v1/favorite/add` | ✅ | 收藏 |
| DELETE | `/api/v1/favorite/remove` | ✅ | 取消收藏 |
| GET | `/api/v1/favorite/list` | ✅ | 收藏列表 |
| DELETE | `/api/v1/favorite/clear` | ✅ | 清空收藏 |
| POST | `/api/v1/history/add` | ✅ | 写历史（幂等 upsert） |
| GET | `/api/v1/history/list` | ✅ | 历史列表 |
| DELETE | `/api/v1/history/{newsId}` | ✅ | 删除单条 |
| DELETE | `/api/v1/history/clear` | ✅ | 清空历史 |
| POST | `/api/v1/ai/chat` | ✅ | AI 对话，SSE 流式 |

---

## 5. 主要优化（原问题 → 修复）

### 5.1 正确性

1. **收藏列表必 500**
   原代码 `model_validate(news)` 发生在 `favorite_id/favorite_time` 赋值之前，而这两个字段是必填。
   现在先用完整 dict 构造响应对象，再交给 `response_model`。
2. **列表/详情字段契约不一致**
   原列表直接返回 ORM，输出 `publish_time`；详情手写 `publishTime`；Pydantic alias 还拼成了 `publishedTime`。
   现在统一 `CamelModel(alias_generator=to_camel)` + `response_model`，全链路 camelCase。
3. **历史重复**
   原表没有 `(user_id, news_id)` 唯一约束，靠“先查全部再循环删”。
   现在补唯一索引，CRUD 用 `INSERT ... ON DUPLICATE KEY UPDATE`（SQLite 测试走兼容分支）。
4. **异常误报**
   原代码只要错误串含 `Duplicate entry` 就返回“用户名已存在”。
   现在按约束名映射：用户名、手机号、收藏、历史、Token 分别返回 409/400。
5. **时区**
   原项目 `utcnow` 与 `now` 混用，MySQL `TIMESTAMP` 再转换一次，前端差 8 小时。
   现在统一 UTC naive 存储，序列化输出带 `Z` 的 ISO 8601。

### 5.2 安全

1. **Token**
   原 Token 是 UUID4 明文入库、固定 7 天、无注销。
   现在 `secrets.token_urlsafe(32)`，只存 SHA-256；支持 logout 吊销、改密吊销全部 Token、TTL 可配。
2. **AI 代理**
   原 `/api/ai/chat` 无鉴权、模型任意、无限额，且“假流式”（先缓冲完整响应再包成 SSE）。
   现在必须登录、模型白名单、按用户限流；`httpx` 以 `stream=True` 读取，`StreamingResponse` 逐块转发，上游非 200 返回 502。
3. **DEBUG 泄露**
   原 `DEBUG_MODE=True` 把 traceback/SQL/URL 返回客户端。现在由 `DEBUG` 环境变量控制，默认关闭。
4. **CORS**
   原 `allow_origins=["*"] + allow_credentials=True`。现在白名单来自 `CORS_ORIGINS`，只有显式 `*` 才关闭 credentials。
5. **输入校验**
   注册密码 8–128、用户名 3–50 且限制字符；资料字段限长；分页 `page>=1`、`pageSize` 1–100；AI 消息 1–20 条、单条 1–8000 字。

### 5.3 性能

1. **缓存 key 忽略分页**
   原分类列表只用一个 key，第一次请求的 `skip/limit` 被缓存 2 小时。
   现在 key 带 `category/page/size`，分类不分页；空列表短缓存 120s，count 缓存 300s。
2. **缓存穿透/雪崩**
   TTL 加 ±10% 抖动；空结果缓存；Redis 故障 fail-open 回退数据库，并记录日志。
3. **索引**
   `news(category_id, publish_time DESC, id DESC)`、`news(category_id, views DESC, publish_time DESC)`、`favorite(user_id, created_at DESC)`、`history(user_id, view_time DESC)`；消除列表 `filesort`。
4. **列表不取正文**
   `content` 是 TEXT，列表只 `load_only` 需要的列；详情才取正文。
5. **GET 不再写库**
   浏览量改为 `POST /news/{id}/view`，按 IP 限流；避免爬虫/预取把 views 刷高。
6. **密码哈希不阻塞事件循环**
   `passlib` 的 CPU 计算放到 `anyio.to_thread.run_sync`。

### 5.4 工程化

- `config/settings.py` 集中配置，`.env.example` 模板；`.env` 永不入库。
- 统一 `Base`、统一 `TimestampMixin`，避免多份 `DeclarativeBase` 导致 Alembic/`create_all` 漏表。
- 统一异常处理：HTTP / 参数校验 / 完整性约束 / SQLAlchemy / 兜底。
- 请求 ID + 耗时日志；`/health` 同时检查 DB 与 Redis。
- pytest 接口回归：7 个用例覆盖契约、鉴权、收藏、历史、AI。
- `requirements.txt` 只列直接依赖；开发依赖拆到 `requirements-dev.txt`。

---

## 6. 测试与构建

```bash
# 后端
pip install -r requirements-dev.txt
pytest

# 前端
cd 03-前端项目代码/xwzx-news
npm run build
```

本仓库当前验证结果：

- 后端：`7 passed`（SQLite 测试库，无需本地 MySQL/Redis）。
- 前端：`npm run build` 成功，414 modules transformed。
- OpenAPI：22 个 path，`/docs` 可直接调试。

> 测试使用 `tests/conftest.py` 中的 SQLite 临时库；生产仍走 MySQL。SQLite 与 MySQL 的 upsert 语法差异已在 CRUD 内做分支。

---

## 7. 可写进简历的表述（只写已实现）

- 基于 FastAPI + SQLAlchemy 2.0 Async 重构新闻资讯后端，按 `router → crud → model/schema` 分层，统一 `/api/v1` 契约与 `{code,message,data}` 响应。
- 设计 Redis Cache-Aside：分类/列表/详情/相关新闻分级 TTL，key 带分页维度，空值缓存 + TTL 抖动 + 故障降级，解决原项目缓存串页与雪崩风险。
- 将 Token 改为“随机值 + SHA-256 摘要入库”，支持注销/改密吊销与登录、AI、浏览计数限流。
- 用 `httpx.stream` + `StreamingResponse` 实现真正的 SSE 透传，替代原项目“缓冲后伪装 SSE”。
- 通过复合索引与 `load_only` 优化列表查询，`EXPLAIN` 验证消除 filesort；浏览量改为独立 POST，GET 保持幂等。
- 补 pytest 接口回归与 GitHub Actions/本地构建校验，覆盖收藏 500、camelCase 契约、历史 upsert 等回归点。

> 面试时请只讲你实际跑过的数字；不要背“QPS 提升 300%”这类未测量指标。

---

## 8. 已知边界

- 未引入 Alembic：当前用 `database.sql` + `migration_v2.sql` 管理 schema；后续可接 Alembic。
- 限流基于单 Redis 实例，多实例部署时共享计数；Redis 故障时 fail-open。
- AI 代理只做转发与限额，不保存对话记录；`ai_chat` 表仍未启用。
- 前端 Token 存在 localStorage，已有 401 自动清理；更高安全要求可改 HttpOnly Cookie + CSRF。
- 原始项目 `.env` 因安全策略未复制到本仓库，请按 `env.example` 重新配置。

---

## 9. 原项目对照

| 原项目 | 优化版 |
|---|---|
| `GET /api/favorite/list` 500 | 完整构造响应，测试覆盖 |
| `publish_time` / `publishedTime` / `publishTime` 混用 | 统一 camelCase |
| AI 无鉴权、假流式 | 登录 + 白名单 + 真 SSE |
| UUID Token 明文、无注销 | 随机 Token + SHA-256 + 吊销 |
| 缓存 key 忽略分页 | key 带分页 + 空值缓存 |
| history 无唯一约束 | UNIQUE + upsert |
| 单列索引 filesort | 复合索引 + EXPLAIN |
| 请求结束自动 commit | 事务由业务层显式控制 |
| `DEBUG_MODE=True` | 环境变量控制，默认关闭 |
