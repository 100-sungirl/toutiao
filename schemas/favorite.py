from pydantic import BaseModel,Field,ConfigDict
from schemas.base import NewsItemBase
from datetime import datetime



#查看收藏状态响应模型
class FavoriteCheckResponse(BaseModel):
    is_favorite: bool = Field(...,alias='is_favorite')

#添加收藏
class FavoriteAddRequest(BaseModel):
    news_id: int = Field(...,alias='newsId')


class FavoriteNewsItemResponse(NewsItemBase):
    favorite_id:int=Field(alias="favoriteId")#收藏项的ID,用于唯一标识收藏收藏项
    favorite_time:datetime=Field(alias="favoriteTime")#收藏时间,用于记录收藏项的创建时间

    model_config = ConfigDict(
        populate_by_name=True,# 是否根据字段名填充模型,默认False,如果设置为True,则会根据字段名填充模型,而不是根据字段位置
        from_attributes=True,# 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
    )




#收藏列表接口响应模型类
class FavoriteListResponse(BaseModel):
    list:list[FavoriteNewsItemResponse]#收藏列表,每个收藏项包含新闻项的基础数据和收藏状态信息
    total:int#收藏总数,总数为收藏列表中所有收藏项的总数
    has_more:bool=Field(alias="hasMore")#是否有还有更多收藏项

    model_config=ConfigDict(
        populate_by_name=True,# 是否根据字段名填充模型,默认False,如果设置为True,则会根据字段名填充模型,而不是根据字段位置
        from_attributes=True,# 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
    )

