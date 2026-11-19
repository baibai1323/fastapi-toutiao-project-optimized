"""接口级冒烟测试：覆盖最容易回归的契约与鉴权。"""

from __future__ import annotations

import uuid


async def test_news_list_and_detail_use_camel_case(client, seed_data):
    response = await client.get(
        "/api/v1/news/list",
        params={"categoryId": seed_data["category_id"], "page": 1, "pageSize": 10},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 200
    assert body["data"]["total"] == 1

    item = body["data"]["list"][0]
    # 前端 NewsItem.vue 读的是 publishTime；不能再出现 ORM 的 publish_time。
    assert item["publishTime"]
    assert "publish_time" not in item

    detail = await client.get(
        "/api/v1/news/detail", params={"id": seed_data["news_id"]}
    )
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["id"] == seed_data["news_id"]
    assert detail_data["content"] == "测试新闻正文内容"
    assert detail_data["relatedNews"] == []


async def test_view_is_post_and_increments(client, seed_data):
    before = await client.get(
        "/api/v1/news/detail", params={"id": seed_data["news_id"]}
    )
    assert before.json()["data"]["views"] == 1

    response = await client.post(f"/api/v1/news/{seed_data['news_id']}/view")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["views"] == 2

    after = await client.get(
        "/api/v1/news/detail", params={"id": seed_data["news_id"]}
    )
    assert after.json()["data"]["views"] == 2


async def test_register_login_and_duplicate_username(client):
    username = f"user_{uuid.uuid4().hex[:10]}"
    payload = {"username": username, "password": "Passw0rd!"}

    register = await client.post("/api/v1/user/register", json=payload)
    assert register.status_code == 200, register.text
    assert register.json()["data"]["userInfo"]["username"] == username

    duplicate = await client.post("/api/v1/user/register", json=payload)
    assert duplicate.status_code == 409, duplicate.text
    assert "用户名已存在" in duplicate.json()["message"]

    wrong = await client.post(
        "/api/v1/user/login",
        json={"username": username, "password": "wrong-password"},
    )
    assert wrong.status_code == 401

    no_token = await client.get("/api/v1/user/info")
    assert no_token.status_code == 401


async def test_logout_revokes_token(client, auth_headers):
    logout = await client.post("/api/v1/user/logout", headers=auth_headers)
    assert logout.status_code == 200, logout.text

    info = await client.get("/api/v1/user/info", headers=auth_headers)
    assert info.status_code == 401


async def test_favorite_list_returns_required_fields(client, seed_data, auth_headers):
    add = await client.post(
        "/api/v1/favorite/add",
        json={"newsId": seed_data["news_id"]},
        headers=auth_headers,
    )
    assert add.status_code == 200, add.text

    # 原项目这里必 500：先 model_validate(news)，favoriteId/favoriteTime 还没赋值。
    listing = await client.get("/api/v1/favorite/list", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    data = listing.json()["data"]
    assert data["total"] == 1
    item = data["list"][0]
    assert item["favoriteId"] > 0
    assert item["favoriteTime"]
    assert item["publishTime"]

    duplicate = await client.post(
        "/api/v1/favorite/add",
        json={"newsId": seed_data["news_id"]},
        headers=auth_headers,
    )
    assert duplicate.status_code == 409


async def test_history_upsert_and_delete(client, seed_data, auth_headers):
    add = await client.post(
        "/api/v1/history/add",
        json={"newsId": seed_data["news_id"]},
        headers=auth_headers,
    )
    assert add.status_code == 200, add.text

    # 同一用户同一新闻再次浏览应更新时间，而不是插入重复行。
    again = await client.post(
        "/api/v1/history/add",
        json={"newsId": seed_data["news_id"]},
        headers=auth_headers,
    )
    assert again.status_code == 200, again.text

    listing = await client.get("/api/v1/history/list", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    data = listing.json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["historyId"] > 0
    assert data["list"][0]["viewTime"]

    deleted = await client.delete(
        f"/api/v1/history/{seed_data['news_id']}", headers=auth_headers
    )
    assert deleted.status_code == 200, deleted.text


async def test_ai_chat_requires_login_and_whitelists_model(client, auth_headers):
    unauthorized = await client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "你好"}]},
    )
    assert unauthorized.status_code == 401

    bad_model = await client.post(
        "/api/v1/ai/chat",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "你好"}],
        },
        headers=auth_headers,
    )
    assert bad_model.status_code == 422
