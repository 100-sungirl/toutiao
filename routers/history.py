from fastapi import APIRouter,Depends,Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status


from config.db_conf import get_db
from models.users import User
from schemas.history import HistoryAddRequest,HistoryListResponse,HistoryNewsItemResponse
from utils.auth import get_current_user
from crud import history
from utils.response import success_response


router = APIRouter(prefix="/api/history",tags=["history"])#api/history是路由前缀，tags是路由标签,加不加api/history都可以



@router.post("/add")
async def add_history(
    data : HistoryAddRequest,
    user:User = Depends(get_current_user),
    db:AsyncSession = Depends(get_db),
):
    """添加用户历史记录"""
    result = await history.add_history(db,user.id,data.news_id)
    return success_response(message="添加成功",data=result)

@router.get("/list")
async def get_history_list(
    page:int=Query(1,ge=1),# 页码,默认第一页
    page_size:int=Query(10,ge=1,le=100,alias="pageSize"),# 每页数量,默认10条
    user:User = Depends(get_current_user),
    db:AsyncSession = Depends(get_db),
):
    """获取用户历史记录列表"""
    rows,total = await history.get_history_list(db,user.id,page,page_size)# 获取历史记录列表,返回新闻详情和查看时间,按查看时间倒序,分页查询
    has_more = total > page*page_size# 是否还有更多数据

    history_list = [HistoryNewsItemResponse.model_validate({
        **news.__dict__,# 从新闻项模型中获取所有属性
        "history_id":history_id,# 添加历史记录ID属性
        "view_time":view_time,# 添加查看时间属性
    })for news,view_time,history_id in rows]

    data = HistoryListResponse(
        list=history_list,
        has_more=has_more,
        total=total,
    )
    return success_response(message="获取成功",data=data)

@router.delete("/delete/{news_id}")
async def delete_history(
    news_id:int,
    user:User = Depends(get_current_user),
    db:AsyncSession = Depends(get_db),
):
    """删除用户历史记录"""
    result = await history.delete_history(db,user.id,news_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="历史记录不存在")
    return success_response(message="删除成功",data=result)

@router.delete("/clear")
async def clear_history(
    user:User = Depends(get_current_user),
    db:AsyncSession = Depends(get_db),
):
    """清空用户历史记录"""
    result = await history.clear_history(db,user.id)
    return success_response(message="删除成功",data=result)

