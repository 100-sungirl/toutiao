from datetime import datetime#导入datetime类,用于表示日期时间
from typing import Optional#导入Optional类型,用于表示可选类型
from sqlalchemy import Index,Integer,String,Enum,DateTime,ForeignKey#导入索引,整数,字符串,枚举,日期时间,外键
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
#导入DeclarativeBase类,用于创建声明式模型,导入Mapped类型,用于表示映射字段,导入mapped_column函数,用于创建映射字段 

class Base(DeclarativeBase):
    pass
class User(Base):
    """
    用户信息表ORM模型
    """
    __tablename__ = "users"
    __table_args__ = (
        Index('username_UNIQUE','username'),#大写索引名,用于唯一索引
        Index('phone_UNIQUE','phone'),#大写索引名,用于唯一索引
    )
    id: Mapped[int] = mapped_column(Integer,primary_key = True,autoincrement = True,comment = "用户ID")#autoincrement=True,自增
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码（加密存储）")
    nickname: Mapped[Optional[str]] = mapped_column(String(50), comment="昵称")
    avatar: Mapped[Optional[str]] = mapped_column(String(255), comment="头像URL",
                                                  default='https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg')
    gender: Mapped[Optional[str]] = mapped_column(Enum('male', 'female', 'unknown'), comment="性别", default='unknown')
    bio: Mapped[Optional[str]] = mapped_column(String(500), comment="个人简介", default='这个人很懒，什么都没留下')
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, comment="手机号")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now(),
                                                 comment="更新时间")
    def __repr__(self):
        """用户信息表ORM模型的字符串表示"""
        return f"User(id={self.id}, username={self.username}, password={self.password}, nickname={self.nickname}, avatar={self.avatar}, gender={self.gender}, bio={self.bio}, phone={self.phone}, created_at={self.created_at}, updated_at={self.updated_at})"

class UserToken(Base):
    """用户令牌表ORM模型"""
    __tablename__ = "user_tokens"
    __table_args__ = (
        Index('token_UNIQUE','token'),
        Index('fk_user_tokens_user_id','user_id'),#外键索引,用于快速查询用户令牌
    )
    id: Mapped[int]=mapped_column(Integer,primary_key = True,autoincrement = True,comment = "用户令牌ID")#autoincrement=True,自增
    token: Mapped[str]=mapped_column(String(255),unique=True,nullable=False,comment="用户令牌值")#用户令牌
    user_id: Mapped[int]=mapped_column(Integer,ForeignKey("users.id"),nullable=False,comment="用户ID")#用户ID,外键,引用users表的id字段
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now(), comment="创建时间")#创建时间
    expire_at:Mapped[datetime]=mapped_column(DateTime,nullable=False, comment="过期时间")#过期时间
    def __repr__(self):
        """用户令牌表ORM模型的字符串表示"""
        return f"UserToken(id={self.id}, token={self.token}, user_id={self.user_id}, created_at={self.created_at}, expire_at={self.expire_at})"



