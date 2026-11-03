"""slowapi限流器(F10):独立模块避免main<->routers循环导入"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)# 按客户端IP限流
