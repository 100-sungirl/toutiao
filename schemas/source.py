from typing import Optional
from pydantic import BaseModel,Field

class SourceCreateRequest(BaseModel):
    """新增新闻源请求"""
    name:str = Field(...,min_length=1,max_length=50,description="源名称,如36氪")
    url:str = Field(...,min_length=1,max_length=500,description="RSS订阅地址或API地址")
    category_id:int = Field(...,description="抓取的新闻归入的分类ID")
    source_type:str = Field("rss",description="源类型:rss/api,默认rss")
