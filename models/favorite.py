from datetime import datetime
from sqlalchemy import UniqueConstraint,Index,Integer,ForeignKey,DateTime
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from models.news import News
from models.users import User

class Base(DeclarativeBase):
    pass

#收藏表ORM模型
class Favorite(Base):
    __tablename__ = 'favorite'
    __table_args__ = (
        UniqueConstraint('user_id','news_id',name = 'user_news_unique'),#创建唯一约束，确保每个用户只能收藏一次新闻
        Index('fk_favorite_user_id','user_id'),#创建索引，用于快速查询收藏的用户
        Index('fk_favorite_news_id','news_id')#创建索引，用于快速查询收藏的新闻
       )
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True,comment='收藏ID')#autoincrement=True表示自增
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey(User.id),nullable=False,comment='用户ID')#外键，引用用户表的ID
    news_id: Mapped[int] = mapped_column(Integer,ForeignKey(News.id),nullable=False,comment='新闻ID')#外键，引用新闻表的ID
    created_at: Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,nullable=False,comment='创建时间')#utcnow()表示默认值为UTC时间
    def __repr__(self):
        """收藏记录表ORM模型的字符串表示"""
        return f"Favorite(id={self.id},user_id={self.user_id},news_id={self.news_id},created_at={self.created_at})"






