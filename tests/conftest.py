"""pytest 共享 fixture。

用 SQLite + aiosqlite 跑集成测试，不依赖本地 MySQL/Redis。
必须在 import app 之前设置 DATABASE_URL，因为 config.db_conf 在导入时创建 engine。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_news.db"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/15"
os.environ["DEBUG"] = "true"

from httpx import ASGITransport, AsyncClient  # noqa: E402

import models  # noqa: F401,E402  确保所有表注册到 Base.metadata
from config.db_conf import AsyncSessionLocal, async_engine  # noqa: E402
from main import app  # noqa: E402
from models.base import Base  # noqa: E402
from models.news import Category, News  # noqa: E402
from utils.time import utcnow  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seed_data():
    async with AsyncSessionLocal() as session:
        category = Category(name="头条", sort_order=1)
        session.add(category)
        await session.flush()

        news = News(
            title="测试新闻标题",
            description="测试新闻简介",
            content="测试新闻正文内容",
            image="https://example.com/cover.jpg",
            author="测试作者",
            category_id=category.id,
            views=1,
            publish_time=utcnow(),
        )
        session.add(news)
        await session.commit()
        await session.refresh(news)
        return {"category_id": category.id, "news_id": news.id}


@pytest_asyncio.fixture
async def auth_headers(client):
    import uuid

    username = f"user_{uuid.uuid4().hex[:10]}"
    response = await client.post(
        "/api/v1/user/register",
        json={"username": username, "password": "Passw0rd!"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}
