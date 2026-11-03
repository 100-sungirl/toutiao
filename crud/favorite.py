from sqlalchemy import select,delete,func
from sqlalchemy.ext.asyncio import AsyncSession
from models.favorite import Favorite
from models.news import News


async def is_news_favorite(
    db: AsyncSession,
    user_id: int,
    news_id: int,
):
    query = select(Favorite).where(
        Favorite.user_id==user_id,
        Favorite.news_id==news_id#查询用户是否收藏了新闻
    )
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None#如果查询结果不为空,则返回True,否则返回False

#添加收藏
async def add_news_favorite(
    db:AsyncSession,
    user_id: int,
    news_id: int,
):
    favorite = Favorite(user_id=user_id,news_id=news_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite

#取消收藏
async def remove_news_favorite(
    db:AsyncSession,
    user_id: int,
    news_id: int,
):
    stmt = delete(Favorite).where(
        Favorite.user_id==user_id,
        Favorite.news_id==news_id#删除用户收藏的新闻
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount>0#如果删除的行数大于0,则返回True,否则返回False

#获取收藏列表，获取的是某个用户的收藏列表+分页功能
async def get_favorite_list(
    db:AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
):
    count_query = select(func.count()).where(Favorite.user_id==user_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page-1)*page_size

    query=(
        select(News,Favorite.created_at.label("favorite_time"),Favorite.id.label("favorite_id"))
        .join(Favorite,News.id==Favorite.news_id)
        .where(Favorite.user_id==user_id)
        .order_by(Favorite.created_at.desc())#根据收藏时间降序排序
        .offset(offset)
        .limit(page_size)
        )
    result = await db.execute(query)
    rows = result.all()
    return rows,total#返回收藏列表和收藏总数

#清空收藏列表
async def remove_all_favorite(
    db:AsyncSession,
    user_id: int,
):
    stmt = delete(Favorite).where(Favorite.user_id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
    #如果删除的行数大于0,则返回删除的行数,否则返回0


    


