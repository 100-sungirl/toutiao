from typing import Any# 任意类型
from pydantic import BaseModel# 基础模型
from fastapi.encoders import jsonable_encoder# JSON编码器

class Result(BaseModel):# 自定义响应模型，功能是封装API响应的格式，包括状态码、消息、数据等
    code:int=200
    message:str="success"
    data:Any=None
    @classmethod# 类方法，作用是创建成功响应对象
    def success(cls,data:Any=None,message:str="success"):
        return cls(
            code=200,
            message=message,
            data = jsonable_encoder(data)#语法结构：jsonable_encoder(data)是将data转换为JSON编码后的字符串
        )
    @classmethod# 类方法，作用是创建错误响应对象
    def error(cls,message:str="error",code:int=500,data:Any=None):
        return cls(
            code=code,# 错误码，默认500表示服务器内部错误
            message=message,
            data = jsonable_encoder(data)
        )


