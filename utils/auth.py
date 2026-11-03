from fastapi import Header,Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config.db_conf import get_db
from crud.users import get_user_by_token

async def get_current_user(
    authorization:str = Header(...,alias="Authorization"),
    db:AsyncSession = Depends(get_db)
):
    token = authorization.replace("Bearer ","")
    user = await get_user_by_token(db,token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="未授权")
    return user
