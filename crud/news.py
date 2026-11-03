from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select
from models.news import Category,News# 导入Category模型,News模型
from sqlalchemy import func,update# 导入func函数,用于统计数量,update函数,用于更新数据库记录
from config.news_cache import (
    get_cached_categories,
    set_cache_categories,
    get_cached_news_list,
    set_cache_news_list,
    get_cached_news_detail,
    set_cache_news_detail,
    get_cached_related_news,
    set_cache_related_news,
)
from fastapi.encoders import jsonable_encoder# JSON编码器
from schemas.base import NewsItemBase



async def get_categories(db: AsyncSession,skip:int=0,limit:int=100):
    """
    获取新闻分类列表
    :param db: 数据库会话
    :param skip: 跳过数量，默认0
    :param limit: 限制数量，默认100
    :return: 新闻分类列表
    """
    # 先从缓存中获取分类列表
    cached_categories = await get_cached_categories()
    if cached_categories:
        return cached_categories# 如果缓存中存在分类列表,则返回缓存中的分类列表
    #offset: 跳过数量
    #limit: 限制数量
    stmt = select(Category).offset(skip).limit(limit)# 构建查询语句,根据skip和limit分页查询分类列表
    result = await db.execute(stmt)# 执行查询语句
    categories = result.scalars().all()#scalars()取出category模型的所有字段,all()将结果转换为列表格式
    
    if categories:# 如果分类列表不为空
        categories = jsonable_encoder(categories)# 转换为JSON可序列化格式
        await set_cache_categories(categories)# 缓存分类列表,过期时间为7200秒
    return categories# 返回分类列表


# 获取新闻列表
async def get_news_list(
    db: AsyncSession,
    page:int=0,# 页码，默认0
    size:int=100,# 每页数量，默认100
    category_id:int=None# 分类ID，默认None
):
    cached_list = await get_cached_news_list(category_id,page,size)
    if cached_list:
        return cached_list# 返回缓存中的新闻列表,每个元素都是NewsItemBase模型的实例


    # 查询指定分类下的所有新闻
    stmt = select(News).where(News.category_id==category_id).offset(page*size).limit(size)
    result = await db.execute(stmt)
    news_list = result.scalars().all()#scalars()取出news模型的所有字段,all()将结果转换为列表格式

    news_data=[]
    if news_list:# 如果新闻列表不为空
        news_data=[
            NewsItemBase.model_validate(item).model_dump(mode = "json",by_alias=False)
            for item in news_list
        ]
        await set_cache_news_list(category_id,page,size,news_data)# 缓存新闻列表,过期时间为7200秒
    return news_data# 返回新闻列表,每个元素都是NewsItemBase模型的实例
    


# 获取新闻总数量
async def get_news_count(
    db: AsyncSession,
    category_id:int=None# 分类ID，默认None
):
    # 构建查询语句,根据分类ID查询新闻数量,count()函数用于统计符合条件的记录数
    stmt = select(func.count(News.id)).where(News.category_id==category_id)
    result = await db.execute(stmt)
    return result.scalar()#scalar()取出结果的第一个值


# 获取新闻详情
async def get_news_detail(
    db: AsyncSession,
    news_id:int# 新闻ID
):

    cached_detail = await get_cached_news_detail(news_id)
    if cached_detail:
        return cached_detail# 返回缓存中的新闻详情,每个元素都是NewsItemBase模型的实例

    # 构建查询语句,根据新闻ID查询新闻详情
    stmt = select(News).where(News.id==news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()#scalar_one_or_none()取出结果的第一个值,如果结果为空则返回None

    news_data = None
    if news:
        news_data=NewsItemBase.model_validate(news).model_dump(mode = "json",by_alias=False)
        await set_cache_news_detail(news_id,news_data)# 缓存新闻详情,过期时间为300秒

    return news_data# 返回新闻详情,每个元素都是NewsItemBase模型的实例


# 新闻浏览量加1
async def increase_news_view(db: AsyncSession,news_id:int):#db: 数据库异步会话,news_id: 新闻ID
    """
    新闻浏览量加1
    :param db: 数据库异步会话
    :param news_id: 新闻ID
    :return: 
    """
    stmt = update(News).where(News.id==news_id).values(views=News.views+1)#values()方法用于更新字段的值
    result = await db.execute(stmt)
    await db.commit()

    return result.rowcount>0#rowcount返回受影响的行数,如果大于0,说明更新成功


# 获取相关推荐新闻
async def get_related_news(
    db:AsyncSession,
    news_id:int,
    category_id:int,
    limit:int=5# 限制数量，默认5
):
    cached_related = await get_cached_related_news(news_id,category_id)
    if cached_related:
        return cached_related# 返回缓存中的相关推荐新闻,每个元素都是字典

    """
    新闻详情，相关推荐
    """
    stmt=(select(News)
    .where(News.id != news_id,News.category_id == category_id)
    .order_by(News.views.desc(),News.publish_time.desc())# desc()方法用于按降序排序,按浏览量降序,按发布时间降序
    .limit(limit))# limit()方法用于限制返回的记录数
    result = await db.execute(stmt)
    related_news = result.scalars().all()#scalars()取出news模型的所有字段,all()将结果转换为列表格式
    related_list = [
        {
        "id": news.id,
        "title": news.title,
        "description": news.description,
        "image": news.image,
        "author": news.author,
        "category_id": news.category_id,
        "views": news.views,
        "publish_time": news.publish_time
        }
        for news in related_news# 遍历related_news列表,将每个新闻对象转换为字典
    ]# 列表推导式，将related_news列表转换为字典列表

    if related_list:
        await set_cache_related_news(news_id,category_id,related_list)# 缓存相关推荐新闻,过期时间为300秒
    return related_list#返回到调用者


# 新增新闻
async def create_news(db: AsyncSession, news_data: dict):
    """
    新增新闻
    :param db: 数据库异步会话
    :param news_data: 新闻数据字典,需包含 title/description/content/image/author/category_id
    :return: 新增后的新闻ORM对象
    """
    # 只取News模型已知字段,避免多余key导致构造失败
    allowed = ("title","description","content","image","author","category_id")
    data = {k: news_data[k] for k in allowed if k in news_data}
    obj = News(**data)# 根据字典字段构造News对象
    db.add(obj)
    await db.commit()
    await db.refresh(obj)# 刷新对象,获取数据库自增生成的id等字段
    return obj


# 热点新闻(回退方案:按浏览量排序)
async def get_hot_news(db: AsyncSession, limit:int=10):
    """
    获取热点新闻,当Redis热搜榜为空时按浏览量兜底
    :param db: 数据库异步会话
    :param limit: 数量,默认10
    """
    stmt=(select(News)
          .order_by(News.views.desc(),News.publish_time.desc())
          .limit(limit))
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {"id":n.id,"title":n.title,"description":n.description,"image":n.image,
         "author":n.author,"category_id":n.category_id,"views":n.views}
        for n in rows
    ]


# 按ID批量获取新闻(热搜榜用,保持榜单顺序)
async def get_news_by_ids(db: AsyncSession, ids:list):
    """按ID列表查新闻,返回dict列表"""
    if not ids:
        return []
    stmt = select(News).where(News.id.in_(ids))
    result = await db.execute(stmt)
    rows = result.scalars().all()
    row_map = {n.id:n for n in rows}
    return [
        {"id":i,"title":row_map[i].title,"description":row_map[i].description,
         "image":row_map[i].image,"author":row_map[i].author,
         "category_id":row_map[i].category_id,"views":row_map[i].views}
        for i in ids if i in row_map
    ]



