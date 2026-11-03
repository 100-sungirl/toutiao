import traceback
from fastapi import HTTPException,Request
from fastapi.responses import JSONResponse
# 导入SQLAlchemy异常类,用于捕获数据库操作异常,IntegrityError表示完整性约束异常,SQLAlchemyError表示SQLAlchemy异常
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
# 导入starlette.status模块,用于获取HTTP状态码
from starlette import status

#开发模式：在开发环境下，返回详细的异常信息
#生产模式：在生产环境下，返回通用的错误信息
DEBUG_MODE = True  # 开发模式
async def http_exception_handler(
    request:Request,
    exc:HTTPException
):
    """
    定义HTTP异常处理函数,用于处理FastAPI中的HTTP异常
    :param request: FastAPI请求对象
    :param exc: HTTP异常对象
    :return: JSON响应对象,包含错误信息和状态码
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code":exc.status_code,# 错误状态码
            "message":exc.detail,# 错误信息
            "data":None
        }
    )

async def integrity_error_handler(request:Request,exc:IntegrityError):
    """
    处理数据库完整性约束错误
    """
    error_msg = str(getattr(exc,'orig',exc))# 获取原始异常信息,即数据库错误信息

    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        #Duplicate entry表示重复数据,用户名或手机号已存在
        detail = "用户名或手机号已存在"
    elif "FOREIGN KEY" in error_msg:
        detail = "关联数据不存在"
    else:
        detail = "数据约束冲突，请检查输入"
    
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type":"IntegrityError",
            "error_message":error_msg,
            "path":str(request.url)
        }
    return JSONResponse(
        status_code = status.HTTP_400_BAD_REQUEST,
        content={
            "code":400,
            "message":detail,
            "data":error_data
        }
    )

async def sqlalchemy_error_handler(request:Request,exc:SQLAlchemyError):
    """
    处理SQLAlchemy异常
    """
    error_msg = str(getattr(exc,'orig',exc))# 获取原始异常信息,即SQLAlchemy错误信息
    detail = "SQLAlchemy异常,请检查数据库操作"
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type":"SQLAlchemyError",
            "error_message":error_msg,
            "path":str(request.url)
        }
    return JSONResponse(
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code":500,
            "message":detail,
            "data":error_data
        }
    )

async def general_error_handler(request:Request,exc:Exception):
    """
    处理其他异常
    """
    error_msg = str(exc)# 获取原始异常信息
    detail = "未知错误，请联系管理员"
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type":"GeneralError",
            "error_message":error_msg,
            "path":str(request.url)
        }
    return JSONResponse(
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code":500,
            "message":detail,
            "data":error_data
        }
    )

def register_exception_handlers(app):
    """
    注册全局异常处理函数到FastAPI应用
    :param app: FastAPI应用实例
    """
    # 注册HTTP异常处理函数
    app.add_exception_handler(HTTPException,http_exception_handler)
    # 注册数据库完整性约束异常处理函数
    app.add_exception_handler(IntegrityError,integrity_error_handler)
    # 注册SQLAlchemy异常处理函数
    app.add_exception_handler(SQLAlchemyError,sqlalchemy_error_handler)
    # 注册通用异常处理函数,捕获其他所有异常
    app.add_exception_handler(Exception,general_error_handler)





