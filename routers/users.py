from fastapi import APIRouter#导入APIRouter类,用于创建路由对象
from fastapi.params import Depends#导入Depends类,用于依赖依赖项
from sqlalchemy.ext.asyncio import AsyncSession#导入AsyncSession类,用于异步数据库会话
from config.db_conf import get_db#导入get_db函数,用于获取数据库会话
from schemas.users import UserRequest,UserAuthResponse,UserInfoResponse,UserUpdateRequest,UserChangePasswordRequest
from crud import users#导入users模块,用于调用CRUD操作
from common.result import Result#导入Result类,用于封装API响应的格式,包括状态码、消息、数据等
from utils.auth import get_current_user#导入get_current_user函数,用于获取当前登录用户

from utils.response import success_response#导入success_response函数,用于返回成功响应
from fastapi import HTTPException,status#导入HTTPException类,用于抛出HTTP异常,导入status用于HTTP状态码





router = APIRouter(prefix = "/api/users",tags=["users"])#创建路由对象,用于定义路由

@router.post("/register")#注册用户
async def register(
    user_data:UserRequest,#用户请求模型
    db:AsyncSession = Depends(get_db)#依赖数据库会话,用于执行数据库操作
):
    #根据用户名查询用户是否存在
    db_user = await users.get_user_by_username(db,user_data.username)#调用CRUD操作中的get_user_by_username函数,根据用户名查询用户
    if db_user:
        return Result.error(message="用户名已存在",code=400)

    #创建用户
    user = await users.create_user(db,user_data)#调用CRUD操作中的create_user函数,创建用户

    #创建用户访问令牌
    token = await users.create_token(db,user.id)#调用CRUD操作中的create_token函数,创建用户访问令牌

    #返回注册成功响应
    '''
    return{
        "code":200,
        "msg":"注册成功",
        "data":{
            "token":token,#用户访问令牌
            "userInfo":{
                "id":user.id,#来自create_user函数,用户ID
                "username":user_data.username,
                "bio":user.bio,#来自create_user函数,用户简介
                "avatar":user.avatar,#来自create_user函数,用户头像
            }
        }
    }
    '''
    response_data = UserAuthResponse(
        token = token,
        userInfo = UserInfoResponse.model_validate(user)
        #userinforesponse方法来自schemas/users.py中的UserInfoResponse类
        #model_validate方法用于将数据库查询结果转换为UserInfoResponse模型实例,来自schemas/users.py中的UserInfoResponse类
        )
    return success_response(data=response_data)

#登录用户
@router.post("/login")
async def login(user_data:UserRequest,db:AsyncSession = Depends(get_db)):
    user = await users.authenticate_user(db,user_data.username,user_data.password)
    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "用户名或密码错误"
        )
    token = await users.create_token(db,user.id)
    response_data = UserAuthResponse(#userinforesponse方法来自schemas/users.py中的UserInfoResponse类
        #model_validate方法用于将数据库查询结果转换为UserInfoResponse模型实例,来自schemas/users.py中的UserInfoResponse类
        token = token,
        user_info = UserInfoResponse.model_validate(user)
    )
    return success_response(data=response_data)

#查Token,封装crud，整合为一个工具函数，路由导入使用：依赖注入
@router.get("/info")
async def get_user_info(user:users = Depends(get_current_user)):
    return success_response(
        message="获取用户信息成功",
        data = UserInfoResponse.model_validate(user)
    )

@router.put("/password")
async def update_password(
    password_data:UserChangePasswordRequest,
    user:users = Depends(get_current_user),
    db:AsyncSession = Depends(get_db)
):
    #调用CRUD操作中的change_password函数,修改用户密码
    res_change_pwd = await users.change_password(
        db,
        user,
        password_data.old_password,
        password_data.new_password
    )

    if not res_change_pwd:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = "修改密码失败,请检查旧密码"
        )
    return success_response(message="修改密码成功")


    

