"""Milvus可用性探活:TCP快速检测+熔断,避免Milvus未启动时请求长时间卡在重试上"""
import socket
import time
from urllib.parse import urlparse

from config.ai_config import MILVUS_URL

_probe_fail_until = 0.0  # 熔断截止时间(单调时钟)
BREAK_SECONDS = 30  # 探活失败后的熔断时长,期间直接判定不可用

def milvus_available()->bool:
    """Milvus是否可连;失败后30秒内不再重复探测(熔断),接口走降级逻辑"""
    global _probe_fail_until
    now = time.monotonic()
    if now < _probe_fail_until:
        return False
    try:
        parsed = urlparse(MILVUS_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 19530
        sock = socket.create_connection((host, port), timeout=1)# 1秒快速探测
        sock.close()
        return True
    except Exception:
        _probe_fail_until = now + BREAK_SECONDS
        print(f"Milvus探活失败({host}:{port}),{BREAK_SECONDS}秒内走降级逻辑")
        return False
