from typing import List,Dict,Any
from config.cache_conf import get_json_cache,set_cache,redis_client# 项目配置文件是cache_conf.py

Chat_HISTORY_KEY = "chat:history:"# 聊天历史缓存键

async def get_chat_history(user_id:int)->List[Dict[str,Any]]:
    """获取用户聊天历史"""
    key = f"{Chat_HISTORY_KEY}{user_id}"
    return await get_json_cache(key) or []# 从缓存中获取聊天历史，若不存在则返回空列表

async def set_chat_history(user_id:int,history:List[Dict[str,Any]],expire:int=300)->bool:
    """设置用户聊天历史"""
    key = f"{Chat_HISTORY_KEY}{user_id}"
    return await set_cache(key,history,expire)

async def clear_chat_history(user_id:int)->bool:
    """清除用户聊天历史"""
    key = f"{Chat_HISTORY_KEY}{user_id}"
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        print(f"清除用户聊天历史失败: {e}")
        return False
