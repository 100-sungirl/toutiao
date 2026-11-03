from pydantic import BaseModel
from typing import Any
from fastapi.encoders import jsonable_encoder

class PageResult(BaseModel):
    code:int=200
    message:str="success"
    data:Any=None
    @classmethod
    def page(cls,list_data:Any=None,total:int=0,has_more:bool=False):
        """
        分页列表响应
        :param list_data: 列表数据
        :param total: 总条数
        :param has_more: 是否还有更多数据
        :return: 统一分页响应对象
        """
        return cls(
            code=200,
            message="success",
            data = jsonable_encoder(# 将list_data转换为JSON编码后的字符串
                {
                "list":jsonable_encoder(list_data),
                "total":total,
                "has_more":has_more
            }
            )
        )

