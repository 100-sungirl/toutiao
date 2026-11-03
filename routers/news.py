from fastapi import APIRouter,BackgroundTasks,Depends,Query,Request
from common.result import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from crud import news,history as history_crud
from config.db_conf import get_db
from common.page_result import PageResult
from services import vector_service# 向量库服务(增量同步/语义搜索/推荐)
from services.news_ai_service import generate_news_summary# F4 摘要标签后台任务
from models.users import User
from models.news import News
from utils.auth import get_current_user
from utils.limiter import limiter# F10 限流器
from config.ai_config import SEARCH_RATE_LIMIT,CREATE_RATE_LIMIT
from config.cache_conf import redis_client

router = APIRouter(prefix="/api/news",tags=["news"])#api/news是路由前缀，tags是路由标签,加不加api/news都可以
@router.get("/categories",response_model=Result)#获取分类
async def get_categories(db: AsyncSession = Depends(get_db),skip:int=0,limit:int=100):
    """
    获取新闻分类列表
    :param db: 数据库会话
    :param skip: 跳过数量，默认0
    :param limit: 限制数量，默认100
    :return: 新闻分类列表
    """
    categories = await news.get_categories(db,skip,limit)
    return Result.success(categories)

@router.get("/list",response_model = PageResult)#获取新闻列表
async def get_news_list(
    category_id:int=Query(...,alias="categoryId"),
    page:int = 1,
    page_size:int =Query(10,alias="pageSize",le=100),# 限制数量，默认10，最大100
    db:AsyncSession = Depends(get_db)
):
    """
    获取新闻列表
    :param category_id: 分类ID
    :param page: 页码，默认1
    :param page_size: 每页数量，默认10，最大100
    :param db: 数据库异步会话
    :return: 新闻列表
    """
    offset = (page-1)*page_size# 计算偏移量,从第page页开始,每页page_size条记录
    news_list = await news.get_news_list(db,page,page_size,category_id)
    total = await news.get_news_count(db,category_id)
    has_more = (offset+len(news_list))<total# 计算是否有还有更多数据,如果偏移量+当前页数量小于总数量,则还有更多数据
    return PageResult.page(#page方法是PageResult的类方法,用于创建分页结果对象
        list_data=news_list,# 新闻列表
        has_more=has_more,# 是否还有更多数据
        total=total,# 总数量
    )


@router.get("/detail",response_model=Result)
async def get_news_detail(
    news_id:int=Query(...,alias="id"),
    db:AsyncSession = Depends(get_db)
):
    """
    获取新闻详情,增加浏览量,记录热搜榜,返回相关推荐新闻和AI摘要
    :param news_id: 新闻ID
    :param db: 数据库异步会话
    :return: 新闻详情
    """
    news_detail=await news.get_news_detail(db,news_id)
    if news_detail is None:
        return Result.error(code=404,message="新闻不存在")

    #浏览量加1
    news_res = await news.increase_news_view(db,news_id)
    if not news_res:
        return Result.error(code=404,message="增加浏览量失败")

    # F9: 实时热搜榜,浏览一次计1分(ZSet按分数排序),失败不影响主流程
    try:
        await redis_client.zincrby("news:hot",1,news_id)#
        await redis_client.expire("news:hot",7*24*3600)# 7天过期
    except Exception as e:
        print(f"热搜榜记录失败:{e}")

    #相关推荐
    related_news = await news.get_related_news(db,news_id,news_detail["category_id"])
    data = {
        "id": news_id,
        "title": news_detail["title"],
        "description": news_detail["description"],
        "image": news_detail["image"],
        "author": news_detail["author"],
        "category_id": news_detail["category_id"],
        "views": news_detail["views"]+1,
        "publish_time": news_detail["publish_time"],
        "summary": news_detail.get("summary"),# F4: AI摘要
        "tags": news_detail.get("tags"),# F4: AI标签,逗号分隔
        "content": news_detail.get("content"),# 正文内容
        "related_news": related_news
    }
    return Result.success(data)#返回新闻详情


@router.get("/search",response_model=Result)
@limiter.limit(SEARCH_RATE_LIMIT)# F10: 搜索限流
async def search_news(
    request:Request,# slowapi限流需要request对象
    q:str=Query(...,min_length=1,max_length=100,description="搜索词"),
    limit:int=Query(5,ge=1,le=20),
    db:AsyncSession = Depends(get_db)
):
    """
    F1 语义搜索:基于Milvus向量的语义检索,不走LLM,快且省token
    :param q: 搜索词,支持自然语言描述
    :param limit: 返回条数,默认5
    """
    results = await vector_service.search_news(q,limit)
    return Result.success(results,message="搜索成功")


@router.get("/recommend",response_model=Result)
@limiter.limit(SEARCH_RATE_LIMIT)# F10: 限流
async def recommend_news(
    request:Request,# slowapi限流需要request对象
    limit:int=Query(5,ge=1,le=20),
    db:AsyncSession = Depends(get_db),
    user:User=Depends(get_current_user),# 个性化推荐必须登录
):
    """
    F5 个性化推荐:基于用户近期浏览历史的向量兴趣画像推荐新闻
    冷启动(无浏览记录)时返回热点新闻兜底
    """
    viewed = await history_crud.get_recent_viewed(db,user.id,limit=10)# 最近浏览的10条
    if not viewed:
        fallback = await news.get_hot_news(db,limit)# 冷启动:热点兜底
        return Result.success(fallback,message="暂无浏览记录,为您推荐热点新闻")
    texts = [f"标题:{t}\n描述:{d or ''}" for _,t,d in viewed]
    exclude_ids = [nid for nid,_,_ in viewed]
    results = await vector_service.recommend_similar(texts,exclude_ids,limit)
    return Result.success(results,message="推荐成功")


@router.get("/hot",response_model=Result)
async def hot_news(
    limit:int=Query(10,ge=1,le=50),
    db:AsyncSession = Depends(get_db)
):
    """
    F9 实时热搜榜:Redis ZSet按浏览行为实时排序,榜空时按浏览量兜底
    """
    try:
        raw = await redis_client.zrevrange("news:hot",0,limit-1,withscores=True)
        ids = [int(i) for i,_ in raw]
    except Exception as e:
        print(f"热搜榜读取失败:{e}")
        ids = []
    if ids:
        items = await news.get_news_by_ids(db,ids)# 保持榜单顺序
        items = [{**it,"heat":dict(raw).get(it["id"])} for it in items]
        return Result.success(items,message="热搜榜获取成功")
    fallback = await news.get_hot_news(db,limit)# 兜底:按总浏览量
    return Result.success(fallback,message="热搜榜为空,返回浏览量排行")


@router.post("/create",response_model=Result)
@limiter.limit(CREATE_RATE_LIMIT)# F10: 限流
async def create_news(
    request:Request,# slowapi限流需要request对象
    news_data:dict,
    background_tasks:BackgroundTasks,# 后台任务,用于异步同步向量库
    db:AsyncSession = Depends(get_db)
):
    """
    新增新闻,并在后台增量同步到Milvus向量库+生成AI摘要标签
    :param news_data: 新闻数据,字段需包含 title/description/content/image/author/category_id
    :return: 新增新闻的id和标题
    """
    obj = await news.create_news(db,news_data)
    # 提取字段为普通字典,避免后台任务执行时ORM会话已关闭
    payload = {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "content": obj.content,
        "author": obj.author,
        "category_id": obj.category_id,
    }
    # 后台任务1:增量同步向量库(不阻塞响应)
    background_tasks.add_task(vector_service.add_news_dict_to_vector,payload)
    # 后台任务2:F4 自动生成摘要和标签
    background_tasks.add_task(generate_news_summary,payload)
    return Result.success({"id":obj.id,"title":obj.title},message="新增新闻成功")


# ===== 新闻源管理(RSS持续抓取) =====

import crud.sources as sources_crud
from schemas.source import SourceCreateRequest

@router.get("/sources",response_model=Result)
async def list_news_sources(enabled_only:bool=False,user:User=Depends(get_current_user)):
    """列出新闻源配置及最近抓取状态"""
    sources = await sources_crud.list_sources(enabled_only)
    return Result.success(sources,message="新闻源列表获取成功")

@router.post("/sources",response_model=Result)
async def add_news_source(data:SourceCreateRequest,user:User=Depends(get_current_user)):
    """新增RSS新闻源,重名返回错误"""
    source_id = await sources_crud.create_source(data.name,data.url,data.category_id,data.source_type)
    if source_id is None:
        return Result.error(code=400,message="源名称已存在")
    return Result.success({"id":source_id},message="新闻源添加成功")

@router.delete("/sources/{source_id}",response_model=Result)
async def remove_news_source(source_id:int,user:User=Depends(get_current_user)):
    """删除新闻源(历史抓取日志保留)"""
    ok = await sources_crud.delete_source(source_id)
    if not ok:
        return Result.error(code=404,message="新闻源不存在")
    return Result.success(message="新闻源删除成功")

@router.post("/sources/{source_id}/fetch",response_model=Result)
async def fetch_source_now(source_id:int,user:User=Depends(get_current_user)):
    """手动触发一次抓取(拉RSS→去重→入库→同步向量库),返回统计结果"""
    from services.news_fetcher import fetch_source
    result = await fetch_source(source_id)
    if not result.get("ok"):
        return Result.error(code=500,message=f"抓取失败:{result.get('message','未知错误')}")
    return Result.success(result,message="抓取完成")

@router.get("/daily-report")
async def get_daily_report_api():
    """新闻日报(Dify工作流优先,本地LLM兜底):当日结果缓存48h,重复请求不重复生成"""
    from services.daily_report_service import get_daily_report
    data = await get_daily_report()
    return success_response(message="新闻日报获取成功",data=data)
