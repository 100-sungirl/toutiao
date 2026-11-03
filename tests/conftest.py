import pytest
from fastapi.testclient import TestClient

from main import app

@pytest.fixture(scope="session")
def client():
    """TestClient必须用with语法,才会触发lifespan(建表+定时任务)"""
    try:
        with TestClient(app) as c:
            yield c
    except Exception as e:
        pytest.skip(f"应用启动失败(检查MySQL/Redis是否运行): {e}")
