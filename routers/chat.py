import json
from fastapi import APIRouter,Depends,HTTPException,status,Request
from fastapi.responses import StreamingResponse
from models.users import User
from schemas.chat import ChatMessageRequest,SessionCreateRequest,FeedbackRequest# 请求体校验
from utils.auth import get_current_user
from utils.response import success_response
from utils.limiter import limiter# F10 限流器
from config.ai_config import CHAT_RATE_LIMIT
from services import rag_service
import crud.chat as chat_crud


router = APIRouter(prefix="/api/chat",tags=["chat"])

async def _resolve_session(user:User,message:str,session_id:int|None)->int|None:
    """确定会话:传了session_id校验归属;没传则用消息前30字当标题自动新建"""
    if session_id is not None:
        if not await chat_crud.owns_session(user.id,session_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="会话不存在或无权访问")
        return session_id
    return await chat_crud.create_chat_session(user.id,title=message[:30])

@router.post("")
@limiter.limit(CHAT_RATE_LIMIT)# F10: AI接口限流,防刷token
async def rag_chat(
    request:Request,# slowapi限流需要request对象
    data:ChatMessageRequest,
    user:User=Depends(get_current_user)
):
    """非流式RAG对话，返回完整回复+引用新闻来源;不传session_id会自动新建会话"""
    try:
        session_id = await _resolve_session(user,data.message,data.session_id)
        result=await rag_service.chat_with_rag(user.id,data.message,session_id=session_id)
        return success_response(message="对话成功",data=result)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(detail=str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        print(f"RAG对话异常：{e}")
        raise HTTPException(detail="AI服务异常，请稍后重试",status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.post("/stream")
@limiter.limit(CHAT_RATE_LIMIT)# F10: AI接口限流
async def rag_chat_stream(
    request:Request,# slowapi限流需要request对象
    data:ChatMessageRequest,
    user:User=Depends(get_current_user)
):
    """流式RAG,SSE事件流:先发sources引用来源,再逐字发content,最后done"""
    session_id = await _resolve_session(user,data.message,data.session_id)# 在生成器外建会话,确保只建一次
    async def event_generator():
        try:
            # F7: 事件格式 {type: sources|content|done, data: ...}
            async for event in rag_service.chat_with_rag_stream(user.id,data.message,session_id=session_id):
                yield f"data:{json.dumps(event,ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data:{json.dumps({'type':'error','data':str(e)},ensure_ascii=False)}\n\n"
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers = {"Cache-Control":"no-cache","X-accel-Buffering":"no"}
    )

@router.get("/history",response_model=None)
async def get_history(session_id:int|None=None,user:User=Depends(get_current_user)):
    """获取对话历史;带session_id时返回该会话的MySQL消息,否则返回近期热历史(Redis回源MySQL)"""
    if session_id is not None:
        messages = await chat_crud.get_session_messages(user.id,session_id)
        return success_response(message="会话消息获取成功",data={"history":messages})
    history=await rag_service.get_history_merged(user.id)
    return success_response(message="对话历史获取成功",data={"history":history})

@router.delete("/reset")
async def reset_chat(user:User=Depends(get_current_user)):
    """清空当前对话历史(Redis+MySQL)"""
    ok= await rag_service.reset_chat(user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="清空对话历史失败")
    return success_response(message="对话历史清空成功")


# ===== 会话管理 =====

@router.post("/sessions")
async def create_session(data:SessionCreateRequest,user:User=Depends(get_current_user)):
    """创建新会话"""
    session_id = await chat_crud.create_chat_session(user.id,title=data.title or "新会话")
    if session_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="创建会话失败")
    return success_response(message="会话创建成功",data={"session_id":session_id,"title":data.title or "新会话"})

@router.get("/sessions")
async def list_sessions(user:User=Depends(get_current_user)):
    """列出我的会话(按活跃时间倒序)"""
    sessions = await chat_crud.list_chat_sessions(user.id)
    return success_response(message="会话列表获取成功",data={"sessions":sessions})

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id:int,user:User=Depends(get_current_user)):
    """拉取指定会话的全部消息(assistant消息附带当前用户的评分,用于前端回显)"""
    messages = await chat_crud.get_session_messages(user.id,session_id)
    if not messages and not await chat_crud.owns_session(user.id,session_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="会话不存在或无权访问")
    # 批量查该用户对这些assistant消息的评分,合并进消息(一次IN查询,不逐条查)
    assistant_ids = [m["id"] for m in messages if m["role"]=="assistant"]
    fmap = await chat_crud.get_user_feedback_map(user.id,assistant_ids)
    for m in messages:
        m["rating"] = fmap.get(m["id"],0) if m["role"]=="assistant" else 0
    return success_response(message="会话消息获取成功",data={"messages":messages})

@router.delete("/sessions/{session_id}")
async def delete_session(session_id:int,user:User=Depends(get_current_user)):
    """删除会话及其全部消息"""
    ok = await chat_crud.delete_chat_session(user.id,session_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="会话不存在或无权访问")
    return success_response(message="会话删除成功")


# ===== 反馈 =====

@router.post("/feedback")
async def submit_feedback(data:FeedbackRequest,user:User=Depends(get_current_user)):
    """对assistant回答点赞(1)/点踩(-1);重复提交走更新(upsert幂等),点踩可附原因"""
    if data.rating not in (1,-1):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,detail="rating只能是1或-1")
    # 校验消息归属:必须是自己的assistant消息,防止越权评价/评价不存在消息
    if not await chat_crud.is_feedback_target(user.id,data.message_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="消息不存在或不可评价")
    ok = await chat_crud.set_rag_feedback(user.id,data.message_id,data.rating,data.reason)
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="反馈保存失败")
    return success_response(message="反馈提交成功",data={"message_id":data.message_id,"rating":data.rating})

@router.delete("/feedback/{message_id}")
async def cancel_feedback(message_id:int,user:User=Depends(get_current_user)):
    """取消反馈:再次点击同一评分按钮时撤销,删除该条反馈记录"""
    existed = await chat_crud.cancel_rag_feedback(user.id,message_id)
    if not existed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="反馈不存在,无需取消")
    return success_response(message="反馈已取消",data={"message_id":message_id,"rating":0})

@router.get("/feedback/stats")
async def feedback_stats(user:User=Depends(get_current_user)):
    """反馈统计:赞/踩总量与好评率(RAG质量分析)"""
    stats = await chat_crud.get_feedback_stats()
    return success_response(message="反馈统计获取成功",data=stats)

@router.get("/feedback/list")
async def feedback_list(
    page:int = 1,
    page_size:int = 10,
    rating:int|None = None,# 不传查全部,1只看赞,-1只看踩(bad case)
    user:User = Depends(get_current_user),
):
    """反馈明细(bad case分析):每条反馈关联出用户问题+AI回答+点踩原因
    用法:先看踩的明细定位回答质量问题,再用question去retrieval_logs查当次召回,判断是检索问题还是生成问题
    """
    if rating not in (None,1,-1):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,detail="rating只能是1、-1或不传")
    data = await chat_crud.get_feedback_details(page=page,page_size=page_size,rating=rating)
    return success_response(message="反馈明细获取成功",data=data)
