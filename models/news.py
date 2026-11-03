from datetime import datetime
from typing import Optional

# 导入SQLAlchemy的类型
from sqlalchemy import DateTime,Integer,Text,String,Index,ForeignKey

# 导入SQLAlchemy的映射函数,DeclarativeBase
from sqlalchemy.orm import Mapped,mapped_column,DeclarativeBase

class Base(DeclarativeBase):
    pass

class Category(Base):
    """
    新闻分类表模型
    对应数据库中的news_category表
    """
    __tablename__="news_category"
    id:Mapped[int]=mapped_column(#mapped_column()是SQLAlchemy的映射函数，用于将数据库中的列映射到Python中的属性
        Integer,
        primary_key=True,
        autoincrement=True,# 自动递增，用于唯一标识分类ID
        comment="分类ID"
    )
    name:Mapped[str]=mapped_column(
        String(50),
        unique = True,
        nullable = False,
        comment = "分类名称"
    )
    sort_order:Mapped[int]=mapped_column(
        Integer,# 整数类型
        default=0,# 默认值为0，表示分类在列表中的位置为第一个
        nullable = False,
        comment = "排序顺序"
    )
    def __repr__(self):# 重写__repr__方法，用于在控制台打印对象时显示分类名称
        """新闻分类表ORM模型的字符串表示"""
        return f"<Category(id={self.id}, name={self.name}, sort_order={self.sort_order})>"
class News(Base):
    __tablename__="news"
    __table_args__= (
        Index('fk_news_category_idx','category_id'),# 外键索引，用于快速查询新闻分类
        Index('idx_publish_time','publish_time')# 索引，用于快速查询按发布时间时间排序的新闻
    )
    id:Mapped[int]=mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="新闻ID"
    )
    title:Mapped[str]=mapped_column(
        String(255),
        nullable = False,
        comment = "新闻标题"
    )
    description:Mapped[str]=mapped_column(
        String(255),
        nullable = False,
        comment = "新闻描述"
    )
    content:Mapped[str]=mapped_column(
        Text,
        nullable = False,
        comment = "新闻内容"
    )
    image:Mapped[str]=mapped_column(
        String(255),
        nullable = False,
        comment = "新闻图片"
    )
    author:Mapped[str]=mapped_column(
        String(50),
        nullable = False,
        comment = "新闻作者"
    )
    category_id:Mapped[int]=mapped_column(
        Integer,
        nullable = False,
        comment = "分类ID"
    )
    views:Mapped[int]=mapped_column(
        Integer,
        default=0,
        nullable = False,
        comment = "新闻点击量"
    )
    publish_time:Mapped[datetime]=mapped_column(
        DateTime,# 日期时间类型，用于存储新闻发布时间时间
        default=datetime.now,# 默认值为当前时间
        nullable = False,# 不能为空，因为发布时间不能为空
        comment = "发布时间"
    )
    summary:Mapped[Optional[str]]=mapped_column(
        Text,
        nullable=True,# 允许为空,由AI后台任务填充
        comment="AI生成的新闻摘要"
    )
    tags:Mapped[Optional[str]]=mapped_column(
        String(255),
        nullable=True,# 允许为空,由AI后台任务填充
        comment="AI生成的标签,逗号分隔"
    )
    def __repr__(self):# 重写__repr__方法，用于在控制台打印对象时显示新闻标题
        """新闻表ORM模型的字符串表示"""
        return f"<News(id={self.id}, title={self.title},views={self.views})>"# 显示新闻ID、标题和点击量
