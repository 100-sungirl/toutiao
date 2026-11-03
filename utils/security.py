from passlib.context import CryptContext#导入passlib.context模块，用于密码加密

#创建一个密码上下文对象，用于密码加密,deprecated="auto"表示自动选择最新的密码加密算法,schemes=["bcrypt"]表示使用bcrypt密码加密算法
pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

# 定义一个函数，用于获取密码的哈希值
def get_hash_password(password:str):
    return pwd_context.hash(password)#返回密码的哈希值

# 定义一个函数，用于验证密码是否正确
def verify_password(plain_password,hashed_password):
    return pwd_context.verify(plain_password,hashed_password)#返回密码是否正确,如果密码正确,返回True,否则返回False
    


