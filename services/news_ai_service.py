"""新闻AI增强服务(F4):自动摘要与标签,后台任务调用"""
import asyncio
import json
import re
from typing import Dict,Any

from sqlalchemy import update
from langchain_core.messages import HumanMessage

from config.db_conf import AsyncSessionLocal
from config.ai_config import NEWS_SUMMARY_PROMPT
from models.news import News
from services.rag_service import get_llm

async def generate_news_summary(payload:Dict[str,Any]):
    """
    后台任务:调用LLM为新闻生成摘要和标签并写回MySQL
    :param payload: 需包含 id/title,可选content
    """
    news_id = payload.get("id")
    if not news_id:
        return
    try:
        llm = get_llm()
        text = f"标题:{payload.get('title')}\n内容:{payload.get('content') or payload.get('description') or ''}"
        resp = await llm.ainvoke([HumanMessage(content=NEWS_SUMMARY_PROMPT.format(text=text))])
        raw = resp.content.strip()
        # 容错:剥掉LLM可能带上的markdown代码块包裹
        raw = re.sub(r"^```(json)?\s*|\s*```$","",raw,flags=re.MULTILINE).strip()
        data = json.loads(raw)
        summary = str(data.get("summary","")).strip()[:500]
        tags = ",".join([str(t).strip() for t in data.get("tags",[]) if str(t).strip()][:5])
        if summary or tags:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(News).where(News.id==news_id).values(summary=summary or None,tags=tags or None)
                )
                await db.commit()
            print(f"新闻摘要生成完成: id={news_id} tags={tags}")
    except Exception as e:
        print(f"新闻摘要生成失败: id={news_id} {e}")
