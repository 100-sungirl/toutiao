from datetime import datetime
from typing import List

from sqlalchemy import select,delete,func
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import History
from models.news import News

async def add_history(
    db:AsyncSession,
    user_id:int,
    news_id:int,
):
    query = select(History).where(History.user_id == user_id,History.news_id == news_id)
    result = await db.execute(query)
    existing_history = result.scalar_one_or_none()# 查询历史记录是否存在,如果存在则返回历史记录对象,否则返回None

    if existing_history:# 如果历史记录存在,更新查看时间
        existing_history.view_time = datetime.now()# 更新查看时间为当前时间
        await db.commit()# 提交事务,将更新后的数据写入数据库
        await db.refresh(existing_history)# 刷新数据库中的数据,确保返回的是最新的数据
        return existing_history
    else:# 如果历史记录不存在,创建新的历史记录
        history = History(user_id=user_id,news_id=news_id)# 创建新的历史记录对象
        db.add(history)
        await db.commit()
        await db.refresh(history)
        return history

# 获取历史记录列表:分页+联表查询新闻详情+按浏览时间倒序
async def get_history_list(
    db:AsyncSession,
    user_id:int,
    page:int=1,
    page_size:int=10,
):
    offset = (page-1)*page_size# 计算偏移量,用于分页查询
    count_query=select(func.count(History.id)).where(History.user_id == user_id)# 查询历史记录总数
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()# scalar_one()方法返回查询结果的第一个值,如果查询结果为空,则返回None
    
    query = (select(News,History.view_time.label("view_time"),History.id.label("history_id"))
        .join(History,History.news_id == News.id)
        .where(History.user_id == user_id)
        .order_by(History.view_time.desc())
        .offset(offset)
        .limit(page_size)
    )# 查询历史记录列表,返回新闻详情和查看时间,按查看时间倒序,分页查询
    result = await db.execute(query)
    rows = result.all()# all()方法返回查询结果的所有行,如果查询结果为空,则返回空列表
    return rows,total

#删除单条历史记录
async def delete_history(
    db:AsyncSession,
    user_id:int,
    news_id:int,
):
    query = delete(History).where(History.user_id == user_id,History.news_id == news_id)
    result = await db.execute(query)
    await db.commit()# 提交事务,将删除后的数据写入数据库
    return result.rowcount>0# 返回删除的行数,如果删除的行数为0,则表示删除失败

#清空用户历史记录
async def clear_history(
    db:AsyncSession,
    user_id:int,
):
    query = delete(History).where(History.user_id == user_id)
    result = await db.execute(query)
    await db.commit()

    return result.rowcount or 0# 返回删除的行数,如果删除的行数为0,则表示删除失败

# 获取用户最近浏览的新闻(个性化推荐F5用)
async def get_recent_viewed(
    db:AsyncSession,
    user_id:int,
    limit:int=10,
)->List[tuple[int,str,str]]:
    """返回[(news_id,title,description),...]按浏览时间倒序"""
    query = (select(News.id,News.title,News.description)
        .join(History,History.news_id == News.id)
        .where(History.user_id == user_id)
        .order_by(History.view_time.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return result.all()







