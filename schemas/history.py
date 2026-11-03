from datetime import datetime
from pydantic import BaseModel,Field,ConfigDict#ConfigDict模块用于配置模型的行为,如是否自动转换为JSON编码后的字符串等
from schemas.base import NewsItemBase# 引入新闻项基础数据模型,用于继承和扩展


#添加历史记录请求
class HistoryAddRequest(BaseModel):
    news_id:int = Field(...,alias="newsId")

class HistoryNewsItemResponse(NewsItemBase):
    """
    浏览历史列表中的新闻项响应
    """
    history_id:int=Field(alias="historyId")
    view_time:datetime=Field(alias="viewTime")# 查看时间

    # 配置模型的行为
    model_config = ConfigDict(
        populate_by_name = True,# 是否根据字段名填充模型,默认False,如果设置为True,则会根据字段名填充模型,而不是根据字段位置
        from_attributes=True,# 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
    )

class HistoryListResponse(BaseModel):
    list:list[HistoryNewsItemResponse]# 浏览历史列表
    total:int
    has_more:bool=Field(alias="hasMore")# 是否还有更多数据

    model_config = ConfigDict(
        populate_by_name = True,# 是否根据字段名填充模型,默认False,如果设置为True,则会根据字段名填充模型,而不是根据字段位置
        from_attributes=True,# 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
    )

