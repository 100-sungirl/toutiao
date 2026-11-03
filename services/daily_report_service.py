"""新闻日报生成(Dify集成 方式A):
优先调用Dify工作流(平台编排,提示词可视化可改),Dify未配置/失败时降级本地LLM兜底
日报按日期缓存到Redis,当日重复请求不重复生成
"""
from datetime import datetime,date
from typing import Optional,Dict,Any
import httpx

from config.ai_config import DIFY_API_BASE,DIFY_DAILY_REPORT_KEY,DIFY_TIMEOUT
from config.cache_conf import redis_client
from config.db_conf import AsyncSessionLocal
from sqlalchemy import select
from models.news import News

DAILY_REPORT_KEY_PREFIX = "news:daily_report:"  # + 日期,如 news:daily_report:2026-09-23


async def _get_hot_news_text(top_n:int=10)->str:
    """取当日热点新闻(Redis ZSet热度榜 -> MySQL补全标题/摘要),拼成给工作流的素材文本"""
    items = await redis_client.zrevrange("news:hot",0,top_n-1,withscores=True)
    if not items:
        return ""
    ids = [int(nid) for nid,_ in items]
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(News.id,News.title,News.description).where(News.id.in_(ids)))
        news_map = {nid:(title,desc) for nid,title,desc in res.all()}
    lines = []
    for rank,nid in enumerate(ids,1):
        title,desc = news_map.get(nid,("(新闻已下架)",""))
        line = f"{rank}. {title}" + (f":{desc[:80]}" if desc else "")
        lines.append(line)
    return "\n".join(lines)


async def _call_dify_workflow(date_str:str,hot_news:str)->Optional[str]:
    """调用Dify日报工作流(blocking模式);未配置Key或调用失败返回None,由上层降级"""
    if not DIFY_DAILY_REPORT_KEY:
        print("Dify日报Key未配置,使用本地LLM兜底")
        return None
    try:
        async with httpx.AsyncClient(timeout=DIFY_TIMEOUT) as client:
            resp = await client.post(
                f"{DIFY_API_BASE}/workflows/run",
                headers={"Authorization":f"Bearer {DIFY_DAILY_REPORT_KEY}"},
                json={
                    "inputs":{"date":date_str,"hot_news":hot_news},
                    "response_mode":"blocking",# 同步等结果,日报场景无需流式
                    "user":"toutiao-backend",
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data",{})
            if data.get("status") == "failed":# Dify工作流执行失败
                print(f"Dify日报工作流执行失败:{data.get('error')}")
                return None
            outputs = data.get("outputs") or {}
            # 结束节点变量名由Dify工作流决定,常见为text/result,兜底取第一个非空值
            for key in ("text","result","output"):
                if outputs.get(key):
                    return outputs[key]
            return next((v for v in outputs.values() if isinstance(v,str) and v.strip()),None)
    except Exception as e:
        print(f"调用Dify日报工作流失败,降级本地LLM:{e}")
        return None


async def _local_fallback(date_str:str,hot_news:str)->str:
    """本地LLM兜底:复用项目内模型直接生成日报(保证Dify不可用时功能不中断)"""
    from langchain_core.messages import HumanMessage
    from services.rag_service import get_llm
    if not hot_news:
        return "今日暂无热点新闻,无法生成日报。"
    resp = await get_llm().ainvoke([HumanMessage(content=(
        f"请根据以下{date_str}的热点新闻,生成一份新闻日报,要求:按板块分类(如科技/财经/社会),"
        f"每条一句话概述,结尾附一段50字以内的今日综述。\n\n热点新闻:\n{hot_news}") )])
    return resp.content if isinstance(resp.content,str) else str(resp.content)


async def get_daily_report(target:Optional[date]=None)->Dict[str,Any]:
    """获取(或生成)指定日期的日报;当日结果缓存Redis 48h,重复请求秒回"""
    d = target or date.today()
    date_str = d.isoformat()
    key = DAILY_REPORT_KEY_PREFIX + date_str
    cached = await redis_client.get(key)
    if cached:
        return {"date":date_str,"report":cached,"source":"cache"}
    hot_news = await _get_hot_news_text()
    report = await _call_dify_workflow(date_str,hot_news)
    source = "dify"
    if not report:# Dify未配置或失败 -> 本地兜底
        report = await _local_fallback(date_str,hot_news)
        source = "local_llm"
    await redis_client.setex(key,60*60*48,report)# 缓存48小时
    return {"date":date_str,"report":report,"source":source}
