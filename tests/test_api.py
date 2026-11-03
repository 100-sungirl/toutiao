"""接口回归测试(F11): python -m pytest tests -v
依赖本地MySQL/Redis运行;涉及Milvus/DashScope的接口做了优雅降级断言"""
import random
import string
import pytest

API_KEY_HEADER = {"Authorization": "Bearer invalid-token-for-test"}


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["message"] == "Hello World"


def test_categories(client):
    r = client.get("/api/news/categories")
    assert r.status_code == 200
    assert r.json()["code"] == 200


def test_news_list(client):
    cats = client.get("/api/news/categories").json()["data"]
    if not cats:
        pytest.skip("无分类数据,跳过列表测试")
    r = client.get("/api/news/list", params={"categoryId": cats[0]["id"], "page": 1, "pageSize": 5})
    assert r.status_code == 200
    assert "list" in r.json()["data"]


def test_news_detail(client):
    cats = client.get("/api/news/categories").json()["data"]
    if not cats:
        pytest.skip("无分类数据,跳过详情测试")
    items = client.get("/api/news/list", params={"categoryId": cats[0]["id"], "pageSize": 1}).json()["data"]
    list_data = items.get("list")
    if not list_data:
        pytest.skip("无新闻数据,跳过详情测试")
    r = client.get("/api/news/detail", params={"id": list_data[0]["id"]})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    # F4: 详情响应包含摘要/标签字段(允许为null)
    assert "summary" in body["data"]
    assert "tags" in body["data"]


def test_hot(client):
    """F9 热搜榜:Redis空时走浏览量兜底,也应返回200"""
    r = client.get("/api/news/hot", params={"limit": 5})
    assert r.status_code == 200
    assert r.json()["code"] == 200


def test_semantic_search(client):
    """F1 语义搜索:Milvus不可用时返回空列表而非报错(服务内降级)"""
    r = client.get("/api/news/search", params={"q": "科技新闻", "limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    assert isinstance(body["data"], list)
    if body["data"]:
        assert "title" in body["data"][0]


def test_recommend_requires_auth(client):
    """F5 推荐接口必须登录(带无效token应401)"""
    r = client.get("/api/news/recommend", headers=API_KEY_HEADER)
    assert r.status_code == 401


def test_register_login_and_recommend(client):
    """注册->登录->带token访问推荐(F5冷启动走热点兜底)"""
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    username = f"pytest_{suffix}"
    reg = client.post("/api/users/register", json={
        "username": username, "password": "abc12345",
    })
    assert reg.status_code == 200, reg.text

    login = client.post("/api/users/login", json={"username": username, "password": "abc12345"})
    assert login.status_code == 200, login.text
    token = login.json()["data"]["token"]

    r = client.get("/api/news/recommend", params={"limit": 3},
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["code"] == 200  # 无浏览记录 -> 热点兜底


def test_chat_history_unauthorized(client):
    """F2 对话历史接口必须登录(带无效token应401)"""
    r = client.get("/api/chat/history", headers=API_KEY_HEADER)
    assert r.status_code == 401


def test_chat_reset_unauthorized(client):
    r = client.request("DELETE", "/api/chat/reset", headers=API_KEY_HEADER)
    assert r.status_code == 401
