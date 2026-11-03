from typing import List,Dict,Any,Optional,AsyncIterator
import json
import httpx

from langchain_openai import ChatOpenAI
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_milvus import Milvus
from langchain_core.documents import Document# 文档类型提示
from langchain_core.messages import HumanMessage,AIMessage,SystemMessage# 消息类型提示
from langchain_classic.retrievers.multi_query import MultiQueryRetriever# 多查询检索器,LLM改写问题提升召回

from config.ai_config import (
    DASHSCOPE_API_KEY,DASHSCOPE_BASE_URL,CHAT_MODEL_NAME,
    CHAT_TEMPERATURE,CHAT_MAX_TOKENS,
    EMBEDDING_MODEL_NAME,EMBEDDING_MAX_RETRIES,
    MILVUS_URL,MILVUS_COLLECTION,RETRIEVE_TOP_K,
    CHAT_HISTORY_EXPIRE,CHAT_HISTORY_MAX_TURNS,RAG_SYSTEM_PROMPT,
    RERANK_ENABLED,RERANK_MODEL,RERANK_TOP_N,DASHSCOPE_RERANK_URL,# F3 重排
    CONDENSE_PROMPT,# F6 多轮改写
)
from config.chat_cache import get_chat_history,set_chat_history,clear_chat_history
from crud.chat import save_chat_messages,get_mysql_chat_history,clear_mysql_chat_history# F2 MySQL持久化
from schemas.chat import ChatSource,ChatReplyResponse# 对话引用来源与响应模型


async def _log_retrieval(user_id:Optional[int],question:str,rewritten:List[str],docs:List[Document],latency_ms:int)->None:
    """检索日志落库(RAG可观测性),失败不影响主流程"""
    try:
        from config.db_conf import AsyncSessionLocal
        from models.rag import RetrievalLog
        async with AsyncSessionLocal() as db:
            db.add(RetrievalLog(
                user_id=user_id,
                query=question[:500],
                rewritten_query=json.dumps(rewritten,ensure_ascii=False)[:1000] if rewritten else None,
                retrieved_news_ids=[d.metadata.get("news_id") for d in docs],
                scores=[],
                latency_ms=latency_ms,
            ))
            await db.commit()
    except Exception as e:
        print(f"检索日志记录失败:{e}")



#=====单例：LLM / Embeddings / 向量库=====
_llm:Optional[ChatOpenAI] = None
_embedding:Optional[DashScopeEmbeddings] = None
_vector_store:Optional[Milvus] = None

def get_llm() -> ChatOpenAI:
    """单例获取ChatOpenAI实例"""
    global _llm
    if _llm is None:
        if not DASHSCOPE_API_KEY:
            raise RuntimeError("DASHSCOPE_API_KEY未配置")
        _llm = ChatOpenAI(
            model = CHAT_MODEL_NAME,
            temperature = CHAT_TEMPERATURE,
            max_tokens = CHAT_MAX_TOKENS,
            api_key = DASHSCOPE_API_KEY,
            base_url = DASHSCOPE_BASE_URL,
            streaming = True,
        )
    return _llm

def get_embedding()->DashScopeEmbeddings:
    """单例获取Embeddings实例"""
    global _embedding
    if _embedding is None:
        _embedding = DashScopeEmbeddings(
            model = EMBEDDING_MODEL_NAME,
            max_retries = EMBEDDING_MAX_RETRIES,
            dashscope_api_key = DASHSCOPE_API_KEY,# 注意参数名是dashscope_api_key
        )
    return _embedding

def get_vector_store()->Milvus:
    """单例获取Milvus向量库实例(连接已经存在的collection),避免每次请求重复建连"""
    global _vector_store
    if _vector_store is None:
        _vector_store = Milvus(
            embedding_function = get_embedding(),
            collection_name = MILVUS_COLLECTION,
            connection_args = {"uri":MILVUS_URL},# 连接Milvus数据库的URI
        )
    return _vector_store

def _format_docs(docs:List[Document])->str:
    """把检索到的文档拼成context文本"""
    if not docs:
        return "（无相关新闻）"
    parts = []# 文档内容列表
    for i,d in enumerate(docs,1):
        title = d.metadata.get("title","未知标题")
        author = d.metadata.get("author","未知作者")
        parts.append(f"[{i}] 标题:{title} | 作者:{author}\n内容:{d.page_content}")
    return "\n\n".join(parts)#拼接文档内容

def _truncate_history(history:List[Dict[str,Any]])->List[Dict[str,Any]]:
    """截断聊天历史记录,保留n轮，一问一答算一轮"""
    max_items = CHAT_HISTORY_MAX_TURNS*2
    if len(history)<=max_items:
        return history
    return history[-max_items:]

def _history_to_text(history:List[Dict[str,Any]])->str:
    """把历史压缩成改写用的纯文本"""
    lines = []
    for item in history[-6:]:# 最多取最近3轮,够用且省token
        prefix = "用户" if item["role"]=="user" else "助手"
        lines.append(f"{prefix}: {item['content']}")
    return "\n".join(lines)

def _history_to_messages(history:List[Dict[str,Any]],context:str,question:str):
    """组装最终messages:system(含context)+history+human(当前问题)"""
    messages = [SystemMessage(content=RAG_SYSTEM_PROMPT.format(context=context))]
    for item in history:
        if item["role"] =="user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] =="assistant":
            messages.append(AIMessage(content=item["content"]))
    messages.append(HumanMessage(content=question))
    return messages

async def _condense_question(history:List[Dict[str,Any]],question:str)->str:
    """
    F6 多轮上下文改写:有历史时,把'那第二篇呢'这类指代性问题改写成独立完整的问题
    没有历史或改写失败时,原样返回
    """
    if not history:
        return question
    try:
        llm = get_llm()
        resp = await llm.ainvoke([HumanMessage(content=CONDENSE_PROMPT.format(
            history=_history_to_text(history),question=question))])
        rewritten = resp.content.strip()
        return rewritten or question
    except Exception as e:
        print(f"多轮改写失败,使用原始问题:{e}")
        return question

async def _rerank_docs(question:str,docs:List[Document])->List[Document]:
    """
    F3 检索重排:用DashScope gte-rerank对多查询召回的候选精排,失败时降级为原序截断
    """
    if not docs:
        return docs
    if not RERANK_ENABLED:
        return docs[:RERANK_TOP_N]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                DASHSCOPE_RERANK_URL,
                headers={"Authorization":f"Bearer {DASHSCOPE_API_KEY}"},
                json={
                    "model":RERANK_MODEL,
                    "input":{
                        "query":question,
                        "documents":[d.page_content[:500] for d in docs],# 截断,控制token
                    },
                    "parameters":{"return_documents":False,"top_n":RERANK_TOP_N},
                },
            )
            resp.raise_for_status()
            results = resp.json().get("output",{}).get("results",[])
            # results: [{index,score},...] 按相关性排序
            return [docs[r["index"]] for r in results if 0 <= r["index"] < len(docs)]
    except Exception as e:
        print(f"重排失败,降级为原序截断:{e}")
        return docs[:RERANK_TOP_N]

async def _retrieve_context(question:str,history:Optional[List[Dict[str,Any]]]=None,user_id:Optional[int]=None)->List[Document]:
    """
    完整检索链路: 多轮改写(F6) -> 多查询召回 -> 重排(F3),并落一条检索日志
    """
    import time
    from services.milvus_health import milvus_available# 延迟导入避免循环依赖
    start = time.time()
    if not milvus_available():# 降级:Milvus不可用时返回空,LLM会坦诚说无法回答
        print("Milvus不可用,跳过向量检索")
        await _log_retrieval(user_id,question,[],[],int((time.time()-start)*1000))
        return []
    try:
        # 1.多轮改写:结合历史把指代性问题变成独立问题
        standalone = await _condense_question(history or [],question)
        vs = get_vector_store()
        base_retriever = vs.as_retriever(search_type="similarity",search_kwargs={"k":RETRIEVE_TOP_K})
        # 2.多查询检索:提升召回多样性,include_original保留原问题防止改写偏离
        retriever = MultiQueryRetriever.from_llm(
            retriever = base_retriever,
            llm = get_llm(),
            include_original = True,
        )
        docs = await retriever.ainvoke(standalone)
        # 2.5 混合检索:BM25词面召回与向量召回RRF融合(补专有名词/编号类查询短板)
        from services.hybrid_retriever import hybrid_search
        docs = await hybrid_search(standalone,docs,final_top_n=max(RETRIEVE_TOP_K,RERANK_TOP_N))
        # 3.重排:精挑最相关的TOP N作为上下文
        docs = await _rerank_docs(standalone,docs)
        # 4.检索日志:记录改写结果/召回ID/耗时
        await _log_retrieval(user_id,question,[standalone],docs,int((time.time()-start)*1000))
        return docs
    except Exception as e:
        await _log_retrieval(user_id,question,[],[],int((time.time()-start)*1000))
        print(f"向量检索新闻失败:{e}")
        return []

def _docs_to_sources(docs:List[Document])->List[Dict[str,Any]]:
    """文档转引用来源结构(dict,便于JSON序列化)"""
    return [{"title":d.metadata.get("title"),"news_id":d.metadata.get("news_id")} for d in docs]

async def chat_with_rag(user_id:int,question:str,session_id:Optional[int]=None)->ChatReplyResponse:
    """非流式对话(已升级为LangGraph Agent):返回完整回复+引用来源;有session_id时消息归属该会话"""
    from services.chat_graph import run_chat# 延迟导入避免循环依赖
    r = await run_chat(user_id,question,session_id=session_id)
    return ChatReplyResponse(
        reply=r["reply"],sources=[ChatSource(**s) for s in r["sources"]],session_id=session_id)

async def chat_with_rag_stream(user_id:int,question:str,session_id:Optional[int]=None)->AsyncIterator[Dict[str,Any]]:
    """流式对话(已升级为LangGraph Agent):SSE事件流 sources -> content* -> done,协议不变"""
    from services.chat_graph import run_chat_stream# 延迟导入避免循环依赖
    async for event in run_chat_stream(user_id,question,session_id=session_id):
        yield event

async def get_history_merged(user_id:int)->List[Dict[str,Any]]:
    """对话历史:Redis优先(近期热数据),为空则回源MySQL(全量历史)"""
    history = await get_chat_history(user_id)
    if history:
        return history
    mysql_history = await get_mysql_chat_history(user_id,limit=CHAT_HISTORY_MAX_TURNS*2)
    if mysql_history:# 回源后回填Redis,下次直接走缓存
        await set_chat_history(user_id,mysql_history,expire=CHAT_HISTORY_EXPIRE)
    return mysql_history

async def reset_chat(user_id:int)->bool:
    """重置聊天历史记录(Redis+MySQL都清)"""
    redis_ok = await clear_chat_history(user_id)
    mysql_ok = await clear_mysql_chat_history(user_id)
    return redis_ok and mysql_ok
