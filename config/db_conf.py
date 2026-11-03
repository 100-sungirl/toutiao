#数据库配置
from sqlalchemy.ext.asyncio import async_sessionmaker,AsyncSession,create_async_engine
ASYNC_DATABASE_URL="mysql+aiomysql://root:123456@127.0.0.1:3306/news_app?charset=utf8mb4"

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise 
        finally:
            await session.close()
