"""新闻向量库服务:增量同步 / 语义搜索(F1) / 个性化推荐(F5)"""
import asyncio
from typing import Dict,Any,List,Optional
from langchain_core.documents import Document

from config.cache_conf import redis_client
from services.milvus_health import milvus_available# 快速探活,避免Milvus掉线时长时间卡住
from services.rag_service import get_vector_store,get_embedding

VECTOR_SYNCED_KEY = "news:vector:synced"# 已同步到向量库的新闻ID集合

async def add_news_dict_to_vector(payload:Dict[str,Any]):
    """
    把单条新闻增量写入Milvus向量库(供后台任务/定时任务调用)
    :param payload: 新闻字段字典,需包含 id/title/description/content/author/category_id
    """
    if not milvus_available():# Milvus未启动,直接放弃本次同步(定时任务稍后会兜底重试)
        print(f"Milvus不可用,跳过同步: id={payload.get('id')}")
        return
    try:
        content = f"标题:{payload.get('title')}\n描述:{payload.get('description')}\n正文:{payload.get('content')}"
        doc = Document(
            page_content=content,
            metadata={
                "news_id":payload.get("id"),
                "title":payload.get("title"),
                "author":payload.get("author"),
                "category_id":payload.get("category_id"),
            },
        )
        vs = get_vector_store()
        # add_documents内部要调用embedding API,是同步阻塞操作,放线程池执行避免卡住事件循环
        await asyncio.to_thread(vs.add_documents,[doc])
        # 标记已同步,供定时任务兜底补同步时跳过(F8)
        try:
            await redis_client.sadd(VECTOR_SYNCED_KEY,payload.get("id"))
        except Exception:
            pass
        print(f"新闻已增量同步到向量库: id={payload.get('id')} title={payload.get('title')}")
    except Exception as e:
        print(f"新闻同步到向量库失败: {e}")

async def add_news_batch_to_vector(payloads:List[Dict[str,Any]]):
    """
    把多条新闻批量写入Milvus向量库(抓取任务调用,单次请求比逐条快)
    :param payloads: 新闻字段字典列表
    """
    if not payloads:
        return
    if not milvus_available():
        print(f"Milvus不可用,批量同步跳过{len(payloads)}条")
        return
    try:
        docs = [
            Document(
                page_content=f"标题:{p.get('title')}\n描述:{p.get('description')}\n正文:{p.get('content')}",
                metadata={
                    "news_id":p.get("id"),
                    "title":p.get("title"),
                    "author":p.get("author"),
                    "category_id":p.get("category_id"),
                },
            ) for p in payloads
        ]
        vs = get_vector_store()
        await asyncio.to_thread(vs.add_documents,docs)
        try:
            await redis_client.sadd(VECTOR_SYNCED_KEY,*[p.get("id") for p in payloads if p.get("id")])
        except Exception:
            pass
        print(f"批量同步到向量库完成:{len(docs)}条")
    except Exception as e:
        print(f"批量同步向量库失败: {e}")

def _doc_to_result(d:Document,score:Optional[float]=None)->Dict[str,Any]:
    """Milvus文档转接口返回结构"""
    item = {
        "news_id":d.metadata.get("news_id"),
        "title":d.metadata.get("title"),
        "author":d.metadata.get("author"),
        "category_id":d.metadata.get("category_id"),
    }
    if score is not None:
        item["score"] = float(score)
    return item

async def search_news(query:str,limit:int=5)->List[Dict[str,Any]]:
    """
    F1 语义搜索:纯向量检索,不走LLM,快且省token
    :param query: 搜索词
    :param limit: 返回条数
    """
    if not milvus_available():# 降级:Milvus不可用时返回空列表而非卡住
        return []
    try:
        vs = get_vector_store()
        docs = await asyncio.to_thread(vs.similarity_search_with_score,query,k=limit)
        return [_doc_to_result(d,score=s) for d,s in docs]
    except Exception as e:
        print(f"语义搜索失败:{e}")
        return []

async def recommend_similar(texts:List[str],exclude_ids:List[int],limit:int=5)->List[Dict[str,Any]]:
    """
    F5 个性化推荐:把用户近期浏览新闻的向量求均值作为兴趣画像,检索相似新闻
    :param texts: 用户近期浏览新闻的文本列表
    :param exclude_ids: 需要排除的新闻ID(已看过的不再推荐)
    :param limit: 返回条数
    """
    if not milvus_available():# 降级:Milvus不可用时返回空列表
        return []
    try:
        emb = get_embedding()
        vectors = await asyncio.to_thread(emb.embed_documents,texts)
        if not vectors:
            return []
        dim = len(vectors[0])
        avg = [sum(v[i] for v in vectors)/len(vectors) for i in range(dim)]# 兴趣均值向量
        vs = get_vector_store()
        docs = await asyncio.to_thread(vs.similarity_search_by_vector,avg,k=limit+len(exclude_ids))
        results:List[Dict[str,Any]] = []
        seen = set(exclude_ids)
        for d in docs:
            nid = d.metadata.get("news_id")
            if nid in seen:# 已浏览过的不重复推荐
                continue
            seen.add(nid)
            results.append(_doc_to_result(d))
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print(f"个性化推荐失败:{e}")
        return []
