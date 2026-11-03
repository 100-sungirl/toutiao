"""新闻持续抓取服务:RSS源抓取 -> 去重 -> MySQL入库 -> Milvus向量同步 -> 日志"""
import time
from typing import Dict,Any,List,Optional
from datetime import datetime

import feedparser
from sqlalchemy import select

from config.db_conf import AsyncSessionLocal
from models.news import News
import crud.sources as sources_crud

# 默认RSS源(name, url),category_id启动时按分类名查库填充
# 注:源地址会随时间失效,news_sources表里enabled=0的源调度器会自动跳过
DEFAULT_SOURCES = [
    {"name":"IT之家","url":"https://www.ithome.com/rss","category":"科技"},
    {"name":"少数派","url":"https://sspai.com/feed","category":"科技"},
    {"name":"Solidot","url":"https://www.solidot.org/index.rss","category":"科技"},
]


async def seed_default_sources()->int:
    """启动时把默认RSS源写入news_sources(按分类名找category_id),返回新增数"""
    from crud.sources import seed_default_sources as _seed
    prepared = await _resolve_categories()
    added = await _seed(prepared)
    return added

async def _resolve_categories()->List[Dict[str,Any]]:
    """把默认源配置中的分类名解析成category_id"""
    from models.news import Category
    prepared = []
    async with AsyncSessionLocal() as db:
        for d in DEFAULT_SOURCES:
            result = await db.execute(select(Category).where(Category.name == d["category"]))
            cat = result.scalar_one_or_none()
            if cat:
                prepared.append({"name":d["name"],"url":d["url"],"category_id":cat.id})
            else:
                print(f"种子源跳过:{d['name']} 分类'{d['category']}'不存在")
    return prepared


def _parse_entry(entry: Any, source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """RSS条目转新闻字典;缺标题的丢弃"""
    title = (entry.get("title") or "").strip()
    if not title:
        return None
    summary = (entry.get("summary") or "").strip()
    # content字段优先(比summary完整)
    content = summary
    if entry.get("content") and isinstance(entry.get("content"), list) and entry["content"]:
        content = (entry["content"][0].get("value") or summary).strip()
    if not content:
        content = title
    # 发布时间
    published = datetime.now()
    if entry.get("published_parsed"):
        try:
            published = datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    # 图片(RSS里有media/enclosure就用,没有留空串)
    image = ""
    enclosures = entry.get("media_content") or entry.get("links") or []
    for enc in enclosures:
        if isinstance(enc, dict) and (enc.get("type") or "").startswith("image"):
            image = enc.get("href") or enc.get("url") or ""
            break
    return {
        "title": title[:255],
        "description": summary[:255] if summary else title[:255],
        "content": content[:20000],
        "image": image[:255],
        "author": ((entry.get("author") or "").strip() or source["name"])[:50],
        "category_id": source["category_id"],
        "publish_time": published,
    }


async def _filter_existing(titles: List[str]) -> set:
    """查库返回已存在的标题集合(标题全等去重)"""
    if not titles:
        return set()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(News.title).where(News.title.in_(titles)))
        return {r[0] for r in result.fetchall()}


async def fetch_source(source_id: int) -> Dict[str, Any]:
    """
    抓取单个源:拉RSS -> 去重 -> 入库MySQL -> 批量同步Milvus -> 写日志
    返回统计字典,全程不抛异常(失败进日志)
    """
    from services.vector_service import add_news_batch_to_vector
    src = await sources_crud.get_source(source_id)
    if not src:
        return {"ok": False, "message": f"源{source_id}不存在"}
    start = time.time()
    try:
        feed = feedparser.parse(src["url"])
        if feed.bozo and not feed.entries:# 解析完全失败
            raise ValueError(f"RSS解析失败:{getattr(feed,'bozo_exception','未知错误')}")
        candidates = []
        for entry in feed.entries[:50]:# 每次最多处理50条,防大feed拖慢
            item = _parse_entry(entry, src)
            if item:
                candidates.append(item)
        existing = await _filter_existing([c["title"] for c in candidates])
        new_items = [c for c in candidates if c["title"] not in existing]
        inserted = 0
        for item in new_items:
            try:
                async with AsyncSessionLocal() as db:
                    news = News(**item)
                    db.add(news)
                    await db.commit()
                    await db.refresh(news)
                # 入库即同步向量库(单条,失败只打日志)
                await add_news_batch_to_vector([{
                    "id": news.id, "title": news.title, "description": news.description,
                    "content": news.content, "author": news.author, "category_id": news.category_id,
                }])
                inserted += 1
            except Exception as e:
                print(f"插入新闻失败({item['title'][:20]}):{e}")
        duration = int((time.time() - start) * 1000)
        status = "success"
        await sources_crud.save_fetch_log(
            source_id, status, len(feed.entries), inserted,
            len(candidates) - len(new_items), "ok", duration)
        await sources_crud.touch_source(source_id)
        return {"ok": True, "fetched": len(feed.entries), "inserted": inserted,
                "skipped": len(candidates) - len(new_items), "duration_ms": duration}
    except Exception as e:
        duration = int((time.time() - start) * 1000)
        await sources_crud.save_fetch_log(source_id, "failed", 0, 0, 0, str(e), duration)
        return {"ok": False, "message": str(e)}


async def fetch_all_enabled() -> List[Dict[str, Any]]:
    """定时任务入口:抓取所有启用的源"""
    results = []
    for src in await sources_crud.list_sources(enabled_only=True):
        r = await fetch_source(src["id"])
        results.append({"source": src["name"], **r})
        print(f"[抓取] {src['name']}: {'插入%d条' % r['inserted'] if r.get('ok') else r.get('message')}")
    return results
