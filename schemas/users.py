from pydantic import BaseModel,Field,ConfigDict#ConfigDict模块用于配置模型的行为,如是否自动转换为JSON编码后的字符串等
from typing import Optional# 可选类型

#用户请求模型
class UserRequest(BaseModel):
    username:str
    password:str

#用户信息基础数据模型
class UserInfoBase(BaseModel):
    nickname:Optional[str] = Field(None,max_length = 50,description="用户昵称")
    avatar:Optional[str] = Field(None,max_length = 255,description="用户头像URL")
    gender:Optional[str] = Field(None,max_length = 10 , description="用户性别")
    bio : Optional[str] = Field(None,max_length = 500, description="用户个人简介")

#用户信息响应模型
class UserInfoResponse(UserInfoBase):
    id:int
    username :str
    # 配置模型的行为
    model_config = ConfigDict(
        from_attributes=True,# 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
    )

#用户认证响应模型
class UserAuthResponse(BaseModel):
    token:str
    user_info:UserInfoResponse = Field(...,alias="userInfo")

    model_config = ConfigDict(
        populate_by_name = True,# 是否根据字段名填充模型,默认False,如果设置为True,则会根据字段名填充模型,而不是根据字段位置
        from_attributes=True,# 是否从模型的属性中获取值,默认False,如果设置为True,则会从模型的属性中获取值,而不是从模型的字段中获取值
    )

#更新用户信息
class UserUpdateRequest(BaseModel):
    nickname:str = None
    avatar:str = None
    gender:str = None
    bio:str = None
    phone:str = None


#用户修改密码请求模型
class UserChangePasswordRequest(BaseModel):
    old_password:str = Field(...,alias = "oldPassword",description="旧密码")
    new_password:str = Field(...,min_length = 6,alias = "newPassword",description="新密码")

    


