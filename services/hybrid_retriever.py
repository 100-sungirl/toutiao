"""混合检索:BM25稀疏召回 + 向量稠密召回 RRF融合
专有名词/编号类查询(如"C919")纯向量召回差,BM25词面匹配补位;RRF融合两路排名后再交给Rerank精排
BM25索引基于MySQL近期新闻构建,内存缓存TTL刷新(新闻量千级,内存BM25足够快)
"""
import time
from typing import List,Tuple,Optional
import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from langchain_core.documents import Document

from config.db_conf import AsyncSessionLocal
from models.news import News

BM25_TTL_SECONDS = 300  # 索引缓存5分钟,兼顾新鲜度与性能
_bm25_cache:Optional[dict] = None  # {"corpus":[doc], "bm25":BM25Okapi, "built_at":float}

def _tokenize(text:str)->List[str]:
    return [w for w in jieba.lcut(text) if w.strip()]

async def _get_bm25_index(force:bool=False)->Optional[dict]:
    """懒加载+TTL刷新BM25索引:标题重复3次加权(标题是新闻核心信号)"""
    global _bm25_cache
    now = time.time()
    if not force and _bm25_cache and now-_bm25_cache["built_at"] < BM25_TTL_SECONDS:
        return _bm25_cache
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(News.id,News.title,News.content,News.author)
                .order_by(News.id.desc()).limit(1000))  # 近1000条
            rows = res.all()
        if not rows:
            return None
        docs = [Document(
            page_content=f"{title} {content or description}",
            metadata={"news_id":nid,"title":title,"author":author or "未知作者"},
        ) for nid,title,content,author in rows]
        corpus = [_tokenize(f"{d.metadata['title']} "*3 + d.page_content) for d in docs]
        _bm25_cache = {"corpus":docs,"bm25":BM25Okapi(corpus),"built_at":now}
        return _bm25_cache
    except Exception as e:
        print(f"BM25索引构建失败:{e}")
        return None

async def bm25_search(query:str,top_k:int=10)->List[Document]:
    """BM25词面召回top_k文档"""
    index = await _get_bm25_index()
    if not index:
        return []
    try:
        scores = index["bm25"].get_scores(_tokenize(query))
        ranked = sorted(enumerate(scores),key=lambda x:x[1],reverse=True)[:top_k]
        return [index["corpus"][i] for i,s in ranked if s > 0]
    except Exception as e:
        print(f"BM25检索失败:{e}")
        return []

def rrf_fuse(*result_lists:List[Document],k:int=60,top_n:int=10)->List[Document]:
    """Reciprocal Rank Fusion: score=Σ 1/(k+rank),按news_id去重合并多路召回"""
    fused:dict = {}
    docs_by_id:dict = {}
    for results in result_lists:
        for rank,doc in enumerate(results,1):
            nid = doc.metadata.get("news_id")
            if nid is None:
                continue
            fused[nid] = fused.get(nid,0.0) + 1.0/(k+rank)
            docs_by_id.setdefault(nid,doc)
    ordered_ids = sorted(fused,key=lambda nid:fused[nid],reverse=True)[:top_n]
    return [docs_by_id[nid] for nid in ordered_ids]

async def hybrid_search(query:str,top_k_vec:List[Document],final_top_n:int=10)->List[Document]:
    """混合检索主入口:向量召回(外部传入) + BM25召回 -> RRF融合"""
    bm25_docs = await bm25_search(query,top_k=10)
    if not bm25_docs:# BM25不可用时退化为纯向量结果
        return top_k_vec[:final_top_n]
    return rrf_fuse(top_k_vec,bm25_docs,top_n=final_top_n)
