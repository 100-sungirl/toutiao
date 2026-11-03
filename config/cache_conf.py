#redis配置
import json
from typing import Any
import redis.asyncio as redis

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
# 如果本地Redis未设置密码，保持空字符串即可；设置了密码就填在这里
REDIS_PASSWORD = ""  # 例如：REDIS_PASSWORD = "123456"

# 创建一个redis客户端对象，用于操作redis数据库
redis_client = redis.Redis(
    host=REDIS_HOST,           # redis主机地址
    port=REDIS_PORT,           # redis端口号
    db=REDIS_DB,               # redis数据库索引,0~15,默认0
    password=REDIS_PASSWORD or None,  # redis密码，为空则不认证
    decode_responses=True,     # 是否将redis返回的字符串解码为python对象
)

# 定义一个函数，用于获取缓存数据,读取字符串
async def get_cache(key:str):
    #return await redis_client.get(key)
    try:
        return await redis_client.get(key)
    except Exception as e:
        print(f"获取缓存失败:{e}")
        return None

# 定义一个函数，用于获取json格式的缓存数据，读取列表或字典
async def get_json_cache(key:str):
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"获取json缓存失败:{e}")
        return None

#设置缓存setex(key,expire,value)#设置缓存,expire表示过期时间,单位秒,value表示缓存值
async def set_cache(key:str,value:Any,expire:int = 3600):
    try:
        # 如果缓存值是字典或列表,则将其转换为json字符串
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        # 无论是什么类型（str/int/float/bool 或已转成的json字符串）都写入缓存
        await redis_client.setex(key, expire, value)
        return True
    except Exception as e:
        print(f"设置缓存失败:{e}")
        return False


