from datetime import datetime
from typing import Optional
from sqlalchemy import Integer,DateTime,String,Index,text,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column

from models.favorite import Base


class NewsSource(Base):
    """新闻源配置表(RSS订阅源,可扩展API源)"""
    __tablename__ = "news_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="源ID")
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="源名称,如36氪")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rss", comment="类型:rss/api")
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="订阅地址或API地址")
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="抓取新闻归入的分类ID")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="是否启用:1是0否")
    last_fetch_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最近一次抓取时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"
    )
    def __repr__(self):
        return f"<NewsSource(id={self.id},name={self.name},enabled={self.enabled})>"


class NewsFetchLog(Base):
    """新闻抓取日志表,记录每次抓取的结果用于监控"""
    __tablename__ = "news_fetch_logs"
    __table_args__ = (Index("idx_log_source_time", "source_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="新闻源ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="状态:success/failed")
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="抓取条数")
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新插入条数")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="去重跳过条数")
    message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注/错误信息")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="耗时(毫秒)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"
    )
    def __repr__(self):
        return f"<NewsFetchLog(id={self.id},source_id={self.source_id},status={self.status})>"
