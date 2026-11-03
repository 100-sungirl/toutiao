"""对话记录MySQL持久化(F2):Redis存近期热数据,MySQL存全量历史;会话/反馈管理"""
import json
from typing import List,Dict,Any,Optional
from datetime import datetime,timezone
from sqlalchemy import select,delete,update,text,func
from sqlalchemy.dialects.mysql import insert as mysql_insert# MySQL特有upsert语法

from config.db_conf import AsyncSessionLocal
from models.chat import ChatMessageRecord,ChatSession
from models.rag import RagFeedback

async def save_chat_messages(user_id:int,user_content:str,assistant_content:str,sources:Optional[List[Dict[str,Any]]]=None,session_id:Optional[int]=None)->bool:
    """保存一轮对话(user+assistant)到MySQL,自带会话,失败不影响主流程"""
    try:
        async with AsyncSessionLocal() as db:
            db.add(ChatMessageRecord(user_id=user_id,session_id=session_id,role="user",content=user_content))
            db.add(ChatMessageRecord(
                user_id=user_id,session_id=session_id,role="assistant",content=assistant_content,
                sources=json.dumps(sources,ensure_ascii=False) if sources else None,
            ))
            if session_id:# 有会话时刷新会话活跃时间
                await db.execute(update(ChatSession).where(ChatSession.id==session_id).values(updated_at=datetime.now(timezone.utc)))
            await db.commit()
        return True
    except Exception as e:
        print(f"对话记录保存MySQL失败:{e}")
        return False

async def get_mysql_chat_history(user_id:int,limit:int=20)->List[Dict[str,Any]]:
    """从MySQL拉取最近N条对话,按时间正序返回"""
    try:
        async with AsyncSessionLocal() as db:
            stmt=(select(ChatMessageRecord)
                  .where(ChatMessageRecord.user_id==user_id)
                  .order_by(ChatMessageRecord.created_at.desc(),ChatMessageRecord.id.desc())
                  .limit(limit))
            result = await db.execute(stmt)
            rows = list(result.scalars().all())
        rows.reverse()# 正序返回,方便直接拼进上下文
        return [{"role":r.role,"content":r.content,"sources":json.loads(r.sources) if r.sources else None} for r in rows]
    except Exception as e:
        print(f"读取MySQL对话历史失败:{e}")
        return []

async def clear_mysql_chat_history(user_id:int)->bool:
    """清空用户在MySQL中的全部对话记录"""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ChatMessageRecord).where(ChatMessageRecord.user_id==user_id))
            await db.commit()
        return True
    except Exception as e:
        print(f"清空MySQL对话历史失败:{e}")
        return False


# ===== 会话管理 =====

async def create_chat_session(user_id:int,title:str="新会话")->Optional[int]:
    """创建对话会话,返回会话ID;失败返回None"""
    try:
        async with AsyncSessionLocal() as db:
            session = ChatSession(user_id=user_id,title=title[:100])
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session.id
    except Exception as e:
        print(f"创建会话失败:{e}")
        return None

async def list_chat_sessions(user_id:int,limit:int=50)->List[Dict[str,Any]]:
    """列出用户的会话(按活跃时间倒序)"""
    try:
        async with AsyncSessionLocal() as db:
            stmt=(select(ChatSession)
                  .where(ChatSession.user_id==user_id)
                  .order_by(ChatSession.updated_at.desc())
                  .limit(limit))
            result = await db.execute(stmt)
            rows = result.scalars().all()
        return [{
            "session_id":s.id,"title":s.title,
            "created_at":s.created_at.isoformat() if s.created_at else None,#isoformat()将datetime转换为ISO格式字符串
            "updated_at":s.updated_at.isoformat() if s.updated_at else None,#isoformat()将datetime转换为ISO格式字符串,iso格式包含时区信息
        } for s in rows]
    except Exception as e:
        print(f"查询会话列表失败:{e}")
        return []

async def owns_session(user_id:int,session_id:int)->bool:
    """校验会话归属(防越权往别人会话里写消息)"""
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(ChatSession.id).where(
                ChatSession.id==session_id,ChatSession.user_id==user_id))
            return res.scalar_one_or_none() is not None
    except Exception as e:
        print(f"校验会话归属失败:{e}")
        return False

async def delete_chat_session(user_id:int,session_id:int)->bool:
    """删除会话及其全部消息(校验归属,防越权删别人的)"""
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(ChatSession).where(
                ChatSession.id==session_id,ChatSession.user_id==user_id))
            if not res.scalar_one_or_none():
                return False
            await db.execute(delete(ChatMessageRecord).where(ChatMessageRecord.session_id==session_id))
            await db.execute(delete(ChatSession).where(ChatSession.id==session_id))
            await db.commit()
        return True
    except Exception as e:
        print(f"删除会话失败:{e}")
        return False

async def get_session_messages(user_id:int,session_id:int,limit:int=100)->List[Dict[str,Any]]:
    """拉取指定会话的消息(校验归属)"""
    try:
        async with AsyncSessionLocal() as db:
            own = await db.execute(select(ChatSession).where(
                ChatSession.id==session_id,ChatSession.user_id==user_id))
            if not own.scalar_one_or_none():
                return []
            stmt=(select(ChatMessageRecord)
                  .where(ChatMessageRecord.session_id==session_id)
                  .order_by(ChatMessageRecord.created_at.desc(),ChatMessageRecord.id.desc())
                  .limit(limit))
            result = await db.execute(stmt)
            rows = list(result.scalars().all())
        rows.reverse()
        return [{"id":r.id,"role":r.role,"content":r.content,
                 "sources":json.loads(r.sources) if r.sources else None,
                 "created_at":r.created_at.isoformat() if r.created_at else None} for r in rows]
    except Exception as e:
        print(f"查询会话消息失败:{e}")
        return []


# ===== 反馈 =====

async def is_feedback_target(user_id:int,message_id:int)->bool:
    """校验反馈目标合法性:消息存在、是assistant消息、且属于该用户(防越权/防给user消息打分)"""
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(ChatMessageRecord.id).where(
                ChatMessageRecord.id==message_id,
                ChatMessageRecord.user_id==user_id,
                ChatMessageRecord.role=="assistant"))
            return res.scalar_one_or_none() is not None
    except Exception as e:
        print(f"校验反馈目标失败:{e}")
        return False

async def set_rag_feedback(user_id:int,message_id:int,rating:int,reason:Optional[str]=None)->bool:
    """设置反馈(upsert幂等):同一用户对同一消息只保留一条,改评分/原因走更新"""
    try:
        async with AsyncSessionLocal() as db:
            stmt = mysql_insert(RagFeedback).values(
                user_id=user_id,message_id=message_id,rating=rating,reason=reason)
            # 命中(user_id,message_id)唯一约束时改为更新,updated_at由ON UPDATE自动刷新
            stmt = stmt.on_duplicate_key_update(
                rating=stmt.inserted.rating,reason=stmt.inserted.reason)
            await db.execute(stmt)
            await db.commit()
        return True
    except Exception as e:
        print(f"保存反馈失败:{e}")
        return False

async def cancel_rag_feedback(user_id:int,message_id:int)->bool:
    """取消反馈:删除该用户对该消息的反馈,返回是否存在过"""
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(delete(RagFeedback).where(
                RagFeedback.user_id==user_id,RagFeedback.message_id==message_id))
            await db.commit()
        return res.rowcount > 0
    except Exception as e:
        print(f"取消反馈失败:{e}")
        return False

async def get_user_feedback_map(user_id:int,message_ids:List[int])->Dict[int,int]:
    """批量查询用户对一组消息的评分(会话消息回显点赞状态用),返回{message_id:rating}"""
    if not message_ids:
        return {}
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(RagFeedback.message_id,RagFeedback.rating).where(
                    RagFeedback.user_id==user_id,
                    RagFeedback.message_id.in_(message_ids)))
            return {mid:rating for mid,rating in res.all()}
    except Exception as e:
        print(f"查询反馈状态失败:{e}")
        return {}

async def get_feedback_stats()->Dict[str,Any]:
    """反馈统计:总量/赞/踩/好评率(RAG质量分析用)"""
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(RagFeedback.rating,func.count(RagFeedback.id)).group_by(RagFeedback.rating))
            counts = dict(res.all())
        likes, dislikes = counts.get(1,0), counts.get(-1,0)
        total = likes + dislikes
        return {"total":total,"likes":likes,"dislikes":dislikes,
                "like_rate":round(likes/total*100,1) if total else 0.0}
    except Exception as e:
        print(f"统计反馈失败:{e}")
        return {"total":0,"likes":0,"dislikes":0,"like_rate":0.0}

async def get_feedback_details(page:int=1,page_size:int=20,rating:Optional[int]=None)->Dict[str,Any]:
    """反馈明细(bad case分析):关联出被评价的回答、对应的用户问题、点踩原因"""
    offset = (page-1)*page_size
    # 同会话中时间早于该回答的最近一条user消息 = 触发这条回答的问题
    question_sql = text("""(
        SELECT q.content FROM chat_messages q
        WHERE q.session_id = m.session_id AND q.role = 'user'
              AND q.created_at <= m.created_at
        ORDER BY q.created_at DESC, q.id DESC LIMIT 1
    )""")
    cond = "WHERE f.rating = :rating" if rating is not None else ""
    params:Dict[str,Any] = {"limit":page_size,"offset":offset}
    if rating is not None:
        params["rating"] = rating
    try:
        async with AsyncSessionLocal() as db:
            list_sql = text(f"""SELECT f.id AS feedback_id, f.rating, f.reason, f.created_at,
                m.id AS message_id, m.content AS answer, m.session_id,
                {question_sql} AS question
                FROM rag_feedback f JOIN chat_messages m ON f.message_id = m.id
                {cond} ORDER BY f.created_at DESC, f.id DESC LIMIT :limit OFFSET :offset""")
            rows = (await db.execute(list_sql,params)).mappings().all()
            count_sql = text(f"SELECT COUNT(*) FROM rag_feedback f {cond}")
            cparams = {"rating":rating} if rating is not None else {}
            total = (await db.execute(count_sql,cparams)).scalar()
        items = []
        for r in rows:
            items.append({
                "feedback_id":r["feedback_id"],"rating":r["rating"],
                "reason":r["reason"],
                "created_at":r["created_at"].isoformat() if r["created_at"] else None,
                "message_id":r["message_id"],"session_id":r["session_id"],
                "question":r["question"],"answer":r["answer"],
            })
        return {"list":items,"total":total,"page":page,"page_size":page_size}
    except Exception as e:
        print(f"查询反馈明细失败:{e}")
        return {"list":[],"total":0,"page":page,"page_size":page_size}
