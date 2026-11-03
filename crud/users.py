from sqlalchemy import select#导入select方法，用于构建SQL查询语句
from sqlalchemy.ext.asyncio import AsyncSession#导入AsyncSession类，用于异步数据库会话
from models.users import User#导入用户模型
from schemas.users import UserRequest#导入用户创建请求模型
from utils import security
from datetime import datetime,timedelta
from models.users import UserToken
from uuid import uuid4



async def get_user_by_username(db:AsyncSession,username:str):
    """
    根据用户名查询用户
    :param db: 数据库会话
    :param username: 用户名
    :return: 用户对象
    """
    query = select(User).where(User.username==username)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_user(db:AsyncSession,user_data:UserRequest):
    """
    创建用户
    :param db: 数据库会话
    :param user_data: 用户创建请求模型
    :return: 创建的用户对象
    """
    hashed_password = security.get_hash_password(user_data.password)#对密码进行哈希处理
    user = User(username=user_data.username,password=hashed_password)#User方法来自models/users.py中的User模型，参数为用户名和哈希后的密码
    db.add(user)#将用户对象添加到数据库会话中,db来自crud.py中的create_user函数
    await db.commit()#提交数据库会话，将用户对象保存到数据库中
    await db.refresh(user)#刷新数据库会话中的用户对象，确保返回的是最新的用户信息
    return user#返回创建的用户对象

async def create_token(db:AsyncSession,user_id:int):
    """
    创建用户访问令牌
    :param db: 数据库会话
    :param user_id: 用户ID
    :return: 用户访问令牌
    """
    token = str(uuid4())#生成一个随机的UUID字符串作为用户访问令牌
    expire_at = datetime.now() + timedelta(days=7)#设置令牌过期时间为7天

    query = select(UserToken).where(UserToken.user_id==user_id)#根据用户ID查询用户访问令牌
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()

    if user_token:
        user_token.token = token
        user_token.expire_at = expire_at
        await db.commit()#提交数据库会话，将用户访问令牌保存到数据库中
    else:
        user_token = UserToken(user_id=user_id,token=token,expire_at=expire_at)
        db.add(user_token)#将用户访问令牌对象添加到数据库会话中,db来自crud.py中的create_token函数
        await db.commit()#提交数据库会话，将用户访问令牌对象保存到数据库中
    return token#返回用户访问令牌

#认证用户
async def authenticate_user(db:AsyncSession,username:str,password:str):
    user = await get_user_by_username(db,username)
    if not user:#如果用户不存在
        return None
    if not security.verify_password(password,user.password):#验证密码是否正确
        return None
    return user

#获取用户信息,根据用户token查询用户信息
async def get_user_by_token(db:AsyncSession,token:str):
    query = select(UserToken).where(UserToken.token==token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()
    if not db_token or db_token.expire_at <datetime.now():#如果令牌不存在或过期时间早于当前时间
        return None
    query = select(User).where(User.id==db_token.user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

#修改密码:验证旧密码>新密码加密>修改密码
async def change_password(
    db:AsyncSession,
    user:User,
    old_password:str,
    new_password:str
):
    if not security.verify_password(old_password,user.password):#verify_password方法来自security.py中的verify_password函数
        return False
    
    hashed_new_pwd = security.get_hash_password(new_password)#对新密码进行哈希处理
    user.password = hashed_new_pwd#将用户对象的密码属性设置为哈希后的新密码
    
    db.add(user)
    await db.commit()              
    await db.refresh(user)#刷新数据库会话中的用户对象，确保返回的是最新的用户信息
    return True
    








