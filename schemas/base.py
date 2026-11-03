from datetime import datetime
from typing import Optional
from pydantic import BaseModel,Field,ConfigDict

#新闻项基础数据模型
class NewsItemBase(BaseModel):
    id:int
    title:str
    description:Optional[str]=None
    image:Optional[str]=None
    author:Optional[str]=None
    category_id:int=Field(alias="categoryId")
    views:int#新闻的点击量
    publish_time:Optional[datetime]=Field(None,alias="publishTime")#新闻的发布时间
    summary:Optional[str]=None#AI生成的摘要
    tags:Optional[str]=None#AI生成的标签,逗号分隔
    content:Optional[str]=None#新闻正文

    model_config = ConfigDict(
        from_attributes=True,
        # 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
        populate_by_name = True,
        # 是否根据字段名填充模型,默认False,如果设置为True,则会根据字段名填充模型,而不是根据字段位置
    )


