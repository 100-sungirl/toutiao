from datetime import datetime
from typing import Optional
from sqlalchemy import Integer,DateTime,String,Text,Index,text
from sqlalchemy.orm import Mapped,mapped_column

from models.favorite import Base# 复用项目已有的声明基类

class ChatMessageRecord(Base):
    """用户AI对话记录表(MySQL持久化,Redis只存近期热数据)"""
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index('idx_chat_user_time','user_id','created_at'),# 联合索引,加速按用户+时间查询
        Index('idx_msg_session','session_id'),# 按会话查消息
    )
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True,comment="消息ID")
    user_id:Mapped[int]=mapped_column(Integer,nullable=False,comment="用户ID")
    session_id:Mapped[Optional[int]]=mapped_column(Integer,nullable=True,comment="所属会话ID,空为历史遗留消息")
    role:Mapped[str]=mapped_column(String(20),nullable=False,comment="角色:user/assistant")
    content:Mapped[str]=mapped_column(Text,nullable=False,comment="消息内容")
    sources:Mapped[Optional[str]]=mapped_column(Text,nullable=True,comment="引用来源JSON,仅assistant消息有")
    created_at:Mapped[datetime]=mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="创建时间"
    )
    def __repr__(self):
        return f"<ChatMessageRecord(id={self.id},user_id={self.user_id},role={self.role})>"


class ChatSession(Base):
    """AI对话会话表(一个用户可建多个会话,类似ChatGPT的会话列表)"""
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index('idx_session_user','user_id','updated_at'),
    )
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True,comment="会话ID")
    user_id:Mapped[int]=mapped_column(Integer,nullable=False,comment="用户ID")
    title:Mapped[str]=mapped_column(String(100),nullable=False,default="新会话",comment="会话标题")
    created_at:Mapped[datetime]=mapped_column(
        DateTime,server_default=text("CURRENT_TIMESTAMP"),nullable=False,comment="创建时间"
    )
    updated_at:Mapped[datetime]=mapped_column(
        DateTime,server_default=text("CURRENT_TIMESTAMP"),onupdate=datetime.now,nullable=False,comment="最后活跃时间"
    )
    def __repr__(self):
        return f"<ChatSession(id={self.id},user_id={self.user_id},title={self.title})>"
