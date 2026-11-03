from typing import List,Dict,Any,Optional
from pydantic import BaseModel,Field

class ChatMessageRequest(BaseModel):
    """对话请求模型"""
    message:str = Field(...,min_length=1,description="用户消息")
    session_id:Optional[int] = Field(None,description="会话ID,不传则自动新建会话")

class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    title:Optional[str] = Field(None,max_length=100,description="会话标题,默认'新会话'")

class FeedbackRequest(BaseModel):
    """对话反馈请求"""
    message_id:int = Field(...,description="被评价的assistant消息ID")
    rating:int = Field(...,description="评分:1赞/-1踩")
    reason:Optional[str] = Field(None,max_length=255,description="踩的原因,可选")

class ChatSource(BaseModel):
    """引用来源"""
    title:Optional[str] =None
    news_id:Optional[int] =None

class ChatMessage(BaseModel):
    """单条对话历史"""
    role:str=Field(...,description="角色:user/assistant")
    content:str=Field(...,description="消息内容")

class ChatReplyResponse(BaseModel):
    """对话回复模型"""
    reply:str=Field(...,description="回复内容")
    sources:List[ChatSource]=Field(default_factory=list,description="引用来源")
    session_id:Optional[int]=Field(None,description="本次对话所属会话ID,前端后续对话需回传")

class ChatHistoryResponse(BaseModel):
    """对话历史记录模型"""
    history:List[ChatMessage]=Field(default_factory=list,description="对话历史记录")#每个实例独立

    model_config = {"populate_by_name":True}
