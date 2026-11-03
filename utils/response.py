from typing import Any
from fastapi.encoders import jsonable_encoder#导入jsonable_encoder函数,用于将Python对象转换为JSON编码后的字符串
from starlette.responses import JSONResponse#导入JSONResponse类,用于创建JSON响应

#成功响应函数
def success_response(message:str = "success",data:Any = None):
    content = {#为什么用content?因为JSONResponse类需要一个字典作为参数,用于封装响应内容
        "code":200,
        "message":message,
        "data":data#将data转换为JSON编码后的字符串
    }
    #返回JSONResponse对象,用于返回成功响应
    return JSONResponse(content=jsonable_encoder(content))


