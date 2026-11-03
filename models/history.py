from datetime import datetime
from sqlalchemy import Integer,DateTime,ForeignKey,Index,text
from sqlalchemy.orm import Mapped,mapped_column

from models.users import User
from models.news import News
from models.favorite import Base#导入基础模型



class History(Base):
    """用户历史表ORM模型"""
    __tablename__ = "history"
    __table_args__ = (
        Index('fk_history_user_idx','user_id'),#创建索引，用于快速查询用户的历史记录
        Index('fk_history_news_idx','news_id'),#创建索引，用于快速查询新闻的历史记录
        Index('idx_view_time','view_time'),#view_time索引，用于快速查询用户最近查看的新闻列表
    )

    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True,comment="历史ID")
    user_id:Mapped[int] = mapped_column(Integer,ForeignKey(User.id),nullable=False,comment="用户ID")
    news_id:Mapped[int] = mapped_column(Integer,ForeignKey(News.id),nullable=False,comment="新闻ID")
    view_time:Mapped[datetime] = mapped_column(DateTime,server_default=text("CURRENT_TIMESTAMP"),nullable=False,comment="查看时间")

    def __repr__(self):
        return f"History(id={self.id},user_id={self.user_id},news_id={self.news_id},view_time={self.view_time})"
