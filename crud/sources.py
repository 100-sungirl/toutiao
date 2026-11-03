"""新闻源配置CRUD:源的增删查+抓取日志记录"""
from typing import List,Dict,Any,Optional
from datetime import datetime
from sqlalchemy import select,delete,update

from config.db_conf import AsyncSessionLocal
from models.news_source import NewsSource,NewsFetchLog

async def list_sources(enabled_only:bool=False)->List[Dict[str,Any]]:
    """列出新闻源配置"""
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(NewsSource)
            if enabled_only:
                stmt = stmt.where(NewsSource.enabled==1)
            stmt = stmt.order_by(NewsSource.id)
            result = await db.execute(stmt)
            rows = result.scalars().all()
        return [{
            "id":s.id,"name":s.name,"source_type":s.source_type,"url":s.url,
            "category_id":s.category_id,"enabled":bool(s.enabled),
            "last_fetch_at":s.last_fetch_at.isoformat() if s.last_fetch_at else None,
        } for s in rows]
    except Exception as e:
        print(f"查询新闻源失败:{e}")
        return []

async def create_source(name:str,url:str,category_id:int,source_type:str="rss")->Optional[int]:
    """新增新闻源,重名返回None"""
    try:
        async with AsyncSessionLocal() as db:
            exists = await db.execute(select(NewsSource).where(NewsSource.name==name))
            if exists.scalar_one_or_none():
                return None
            src = NewsSource(name=name,url=url,category_id=category_id,source_type=source_type)
            db.add(src)
            await db.commit()
            await db.refresh(src)
            return src.id
    except Exception as e:
        print(f"新增新闻源失败:{e}")
        return None

async def delete_source(source_id:int)->bool:
    """删除新闻源(日志保留用于审计)"""
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(delete(NewsSource).where(NewsSource.id==source_id))
            await db.commit()
            return res.rowcount > 0
    except Exception as e:
        print(f"删除新闻源失败:{e}")
        return False

async def get_source(source_id:int)->Optional[Dict[str,Any]]:
    """获取单个源配置"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(NewsSource).where(NewsSource.id==source_id))
            s = result.scalar_one_or_none()
        if not s:
            return None
        return {"id":s.id,"name":s.name,"source_type":s.source_type,"url":s.url,
                "category_id":s.category_id,"enabled":bool(s.enabled),
                "last_fetch_at":s.last_fetch_at.isoformat() if s.last_fetch_at else None}
    except Exception as e:
        print(f"查询新闻源失败:{e}")
        return None

async def touch_source(source_id:int)->None:
    """更新源的最近抓取时间"""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(update(NewsSource).where(NewsSource.id==source_id).values(last_fetch_at=datetime.now()))
            await db.commit()
    except Exception as e:
        print(f"更新源抓取时间失败:{e}")

async def save_fetch_log(source_id:int,status:str,fetched:int,inserted:int,skipped:int,message:str,duration_ms:int)->None:
    """记录一次抓取日志,失败不影响主流程"""
    try:
        async with AsyncSessionLocal() as db:
            db.add(NewsFetchLog(
                source_id=source_id,status=status,fetched_count=fetched,
                inserted_count=inserted,skipped_count=skipped,
                message=message[:500],duration_ms=duration_ms,
            ))
            await db.commit()
    except Exception as e:
        print(f"记录抓取日志失败:{e}")

async def seed_default_sources(defaults:List[Dict[str,Any]])->int:
    """启动时种入默认RSS源(name不存在才插),返回新增数量"""
    added = 0
    for d in defaults:
        if await create_source(name=d["name"],url=d["url"],category_id=d["category_id"],source_type="rss"):
            added += 1
    return added
