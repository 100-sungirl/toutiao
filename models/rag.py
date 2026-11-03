from datetime import datetime,timezone
from typing import Optional
from sqlalchemy import Integer,DateTime,String,JSON,Index,UniqueConstraint,text
from sqlalchemy.orm import Mapped,mapped_column

from models.favorite import Base


class RagFeedback(Base):
    """AI对话反馈表(用户对回答点赞/点踩,用于质量分析)"""
    __tablename__ = "rag_feedback"
    # 同一用户对同一条消息只有一条反馈(改评分走更新,不重复插入)
    __table_args__ = (
        Index("idx_feedback_user", "user_id", "created_at"),
        UniqueConstraint("user_id", "message_id", name="uq_feedback_user_message"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="反馈ID")
    message_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="被评价的assistant消息ID")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="用户ID")
    rating: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分:1赞/-1踩")
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="踩的原因,可选")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        nullable=False, comment="更新时间(改评分/原因时刷新)",
    )
    def __repr__(self):
        return f"<RagFeedback(id={self.id},message_id={self.message_id},rating={self.rating})>"


class RetrievalLog(Base):
    """RAG检索日志表(记录每次检索的问题/召回/耗时,用于质量优化)"""
    __tablename__ = "retrieval_logs"
    __table_args__ = (Index("idx_retrieval_time", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="用户ID,匿名可空")
    query: Mapped[str] = mapped_column(String(500), nullable=False, comment="用户原始问题")
    rewritten_query: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, comment="改写后的问题,JSON数组")
    retrieved_news_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="召回的新闻ID列表")
    scores: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="对应相似度分数列表")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="检索耗时(毫秒)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"
    )
    def __repr__(self):
        return f"<RetrievalLog(id={self.id},query={self.query[:20]})>"
