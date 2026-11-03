from fastapi import APIRouter,Depends,Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.db_conf import get_db
from models.users import User
from schemas.favorite import FavoriteCheckResponse,FavoriteAddRequest,FavoriteListResponse

from utils.auth import get_current_user
from utils.response import success_response
from crud import favorite

from fastapi import HTTPException,status



router = APIRouter(prefix = "/api/favorite",tags = ["favorite"])

#查看收藏状态
@router.get("/check",response_model=FavoriteCheckResponse)
async def check_favorite(
    news_id:int = Query(...,alias='newsId'),
    user:User = Depends(get_current_user),#depends(get_current_user)表示从依赖项中获取当前用户信息
    db:AsyncSession = Depends(get_db),#depends(get_db)表示从依赖项中获取数据库会话
):
    is_favorited = await favorite.is_news_favorite(db,user.id,news_id)
    return success_response(
        message="查看收藏状态成功",
        data = FavoriteCheckResponse(is_favorite=is_favorited)#返回收藏状态
    )

#添加收藏
@router.post("/add",response_model=FavoriteCheckResponse)
async def add_favorite(
    data:FavoriteAddRequest,
    user:User = Depends(get_current_user),#depends(get_current_user)表示从依赖项中获取当前用户信息
    db:AsyncSession = Depends(get_db),#depends(get_db)表示从依赖项中获取数据库会话
):
    result = await favorite.add_news_favorite(db,user.id,data.news_id)
    return success_response(message="添加收藏成功",data=result)

#取消收藏
@router.delete("/remove",response_model=FavoriteCheckResponse)
async def remove_favorite(
    news_id:int = Query(...,alias='newsId'),
    user:User = Depends(get_current_user),#depends(get_current_user)表示从依赖项中获取当前用户信息
    db:AsyncSession = Depends(get_db),#depends(get_db)表示从依赖项中获取数据库会话
):
    result = await favorite.remove_news_favorite(db,user.id,news_id)
    if not result:#如果取消收藏失败,则抛出404异常
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="用户未收藏该新闻")

    return success_response(message="取消收藏成功",data={"news_id":news_id,"status":"removed"})

#获取收藏列表
@router.get("/list",response_model=FavoriteListResponse)
async def get_favorite_list(
    page:int =Query(1,ge=1,description="页码"),#页码,默认值为1,ge=1表示页码不能小于1
    page_size:int = Query(10,ge=1,le=100,alias="pageSize"),#每页数量,默认值为10,ge=1表示每页数量不能小于1,le=100表示每页数量不能大于100
    user:User=Depends(get_current_user),#depends(get_current_user)表示从依赖项中获取当前用户信息
    db:AsyncSession = Depends(get_db),#depends(get_db)表示从依赖项中获取数据库会话
):
    rows,total = await favorite.get_favorite_list(db,user.id,page,page_size)
    favorite_list=[{
        **news.__dict__,
        "favorite_time":favorite_time,
        "favorite_id":favorite_id,
    }for news,favorite_time,favorite_id in rows]

    has_more = total>page*page_size#判断是否有还有更多数据
    data = FavoriteListResponse(list=favorite_list,total=total,has_more=has_more)
    return success_response(message="获取收藏列表成功",data=data)

#清空收藏列表:当前用户的收藏列表
@router.delete("/clear")
async def clear_favorite(
    user:User = Depends(get_current_user),
    db:AsyncSession = Depends(get_db),
):
    count = await favorite.remove_all_favorite(db,user.id)
    return success_response(message=f"清空收藏列表成功,删除了{count}条收藏")







