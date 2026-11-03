"""定时任务(F8):向量库补同步兜底 + 摘要回填 + RSS新闻持续抓取"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from config.cache_conf import redis_client
from config.db_conf import AsyncSessionLocal
from config.ai_config import SYNC_INTERVAL_MINUTES,SUMMARY_BACKFILL_MINUTES,NEWS_FETCH_MINUTES
from models.news import News
from services.vector_service import VECTOR_SYNCED_KEY

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

async def sync_unsynced_news():
    """兜底任务:把还没进向量库的新闻补同步(比如服务重启期间新增的新闻)"""
    try:
        from services.vector_service import add_news_dict_to_vector
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(News).order_by(News.id.desc()).limit(500))
            rows = result.scalars().all()
        for n in rows:
            try:
                if await redis_client.sismember(VECTOR_SYNCED_KEY,n.id):
                    continue# 已同步过,跳过
            except Exception:
                pass# Redis不可用时不阻断同步
            await add_news_dict_to_vector({
                "id":n.id,"title":n.title,"description":n.description,
                "content":n.content,"author":n.author,"category_id":n.category_id,
            })
    except Exception as e:
        print(f"定时向量同步失败:{e}")

async def backfill_summaries():
    """兜底任务:为缺少摘要的近期新闻补生成(每次最多20条)"""
    try:
        from services.news_ai_service import generate_news_summary
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(News).where(News.summary.is_(None)).order_by(News.id.desc()).limit(20)
            )
            rows = result.scalars().all()
        for n in rows:
            await generate_news_summary({"id":n.id,"title":n.title,"content":n.content})
    except Exception as e:
        print(f"定时摘要回填失败:{e}")

def start_scheduler():
    scheduler.add_job(sync_unsynced_news,"interval",minutes=SYNC_INTERVAL_MINUTES,id="sync_vector")
    scheduler.add_job(backfill_summaries,"interval",minutes=SUMMARY_BACKFILL_MINUTES,id="backfill_summary")
    scheduler.add_job(fetch_news_job,"interval",minutes=NEWS_FETCH_MINUTES,id="fetch_news")
    scheduler.add_job(generate_daily_report_job,"cron",hour=8,minute=0,id="daily_report")# 每天早上8点生成日报
    scheduler.start()
    print(f"定时任务已启动: 向量补同步每{SYNC_INTERVAL_MINUTES}分钟 / 摘要回填每{SUMMARY_BACKFILL_MINUTES}分钟 / RSS抓取每{NEWS_FETCH_MINUTES}分钟 / 新闻日报每天08:00")

async def generate_daily_report_job():
    """定时生成新闻日报(Dify工作流优先,本地LLM兜底,结果缓存供当日请求秒回)"""
    try:
        from services.daily_report_service import get_daily_report
        data = await get_daily_report()
        print(f"定时日报已生成({data['source']}): {data['date']}")
    except Exception as e:
        print(f"定时生成日报失败:{e}")

async def fetch_news_job():
    """定时抓取所有启用的RSS源(异常自兜底,不会中断调度器)"""
    try:
        from services.news_fetcher import fetch_all_enabled
        await fetch_all_enabled()
    except Exception as e:
        print(f"定时抓取新闻失败:{e}")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
