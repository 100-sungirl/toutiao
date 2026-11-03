from typing import Any,Dict,List,Optional
from config.cache_conf import get_json_cache,set_cache

CATEGORIES_KEY = "news:categories"
NEWS_LIST_KEY = "news_list:"
NEWS_DETAIL_KEY = "news:detail:"
RELATED_NEWS_KEY = "news:related:"

# 读取新闻分类缓存
async def get_cached_categories():
    return await get_json_cache(CATEGORIES_KEY)
# 写入新闻分类缓存
async def set_cache_categories(data:List[Dict[str,Any]],expire:int=7200):
    return await set_cache(CATEGORIES_KEY,data,expire)


# 读取新闻列表缓存
async def get_cached_news_list(category_id:Optional[int],page:int,size:int,expire:int=1800):
    category_part = category_id if category_id is not None else -1
    key = f"{NEWS_LIST_KEY}{category_part}_{page}_{size}"
    return await get_json_cache(key)
# 写入新闻列表缓存
async def set_cache_news_list(category_id : Optional[int], page:int,size:int,news_list:List[Dict[str,Any]],expire:int=1800):
    category_part = category_id if category_id is not None else -1
    key = f"{NEWS_LIST_KEY}{category_part}_{page}_{size}"
    return await set_cache(key,news_list,expire)


#读取新闻详情缓存
async def get_cached_news_detail(news_id:int)->Optional[Dict[str,Any]]:
    key = f"{NEWS_DETAIL_KEY}{news_id}"
    return await get_json_cache(key)
# 写入新闻详情缓存
async def set_cache_news_detail(news_id:int,news_data:Dict[str,Any],expire:int=300)->bool:
    key = f"{NEWS_DETAIL_KEY}{news_id}"
    return await set_cache(key,news_data,expire)


#读取相关新闻缓存
async def get_cached_related_news(news_id:int,category_id:int)->Optional[List[Dict[str,Any]]]:
    key = f"{RELATED_NEWS_KEY}{news_id}_{category_id}"
    return await get_json_cache(key)
# 写入相关新闻缓存
async def set_cache_related_news(news_id:int,category_id:int,related_news:List[Dict[str,Any]],expire:int=300)->bool:
    key = f"{RELATED_NEWS_KEY}{news_id}_{category_id}"
    return await set_cache(key,related_news,expire)







