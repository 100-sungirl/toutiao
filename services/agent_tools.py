"""Agent工具集(Function Calling):新闻语义检索/实时热搜/个人收藏,供LangGraph Agent调用"""
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from config.db_conf import AsyncSessionLocal
from models.news import News
from crud import favorite as favorite_crud
from config.cache_conf import redis_client


@tool
async def search_news(query:str,config:RunnableConfig)->str:
    """搜索新闻知识库。当用户询问新闻、时事、近期事件,或回答需要新闻事实支撑时调用。query应是一个独立完整的搜索问题。"""
    from services.rag_service import _retrieve_context,_format_docs,_docs_to_sources
    docs = await _retrieve_context(query,user_id=(config.get("configurable") or {}).get("user_id"))
    # 把召回结果同步给graph层(经config传递收集器),供前端渲染引用来源
    collector = (config.get("configurable") or {}).get("sources_collector")
    if collector is not None and docs:
        collector.extend(_docs_to_sources(docs))
    if not docs:
        return "新闻库中没有找到与该问题相关的新闻。请如实告知用户暂时没有相关新闻资料,不要编造。"
    return _format_docs(docs)


@tool
async def get_hot_news()->str:
    """获取当前实时热搜榜Top10。当用户问'最近什么新闻最热/热搜榜/大家都在看什么'时调用。"""
    try:
        items = await redis_client.zrevrange("news:hot",0,9,withscores=True)# ZSet按热度分数倒序
        if not items:
            return "当前暂无热搜数据。"
        ids = [int(nid) for nid,_ in items]
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(News.id,News.title).where(News.id.in_(ids)))
            title_map = dict(res.all())
        lines = [f"{i+1}. {title_map.get(nid,'(新闻已下架)')}" for i,nid in enumerate(ids)]
        return "当前热搜榜Top10:\n"+"\n".join(lines)
    except Exception as e:
        return f"热搜榜查询失败:{e}"


@tool
async def get_my_favorites(config:RunnableConfig)->str:
    """查询当前登录用户的收藏新闻列表。当用户问'我收藏了什么/我的收藏'时调用。"""
    user_id = (config.get("configurable") or {}).get("user_id")
    if not user_id:
        return "用户未登录,无法查询收藏。"
    try:
        async with AsyncSessionLocal() as db:
            rows,total = await favorite_crud.get_favorite_list(db,user_id,1,10)
        if not rows:
            return "你还没有收藏任何新闻。"
        lines = [f"- {n.title}" for n,_,_ in rows]
        return f"共{total}条收藏(最多显示10条):\n"+"\n".join(lines)
    except Exception as e:
        return f"收藏查询失败:{e}"


AGENT_TOOLS = [search_news,get_hot_news,get_my_favorites]
