from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware# 跨域中间件
from slowapi import _rate_limit_exceeded_handler# F10 限流异常处理
from slowapi.errors import RateLimitExceeded
from utils.exception import register_exception_handlers# 引入异常处理函数注册函数
from utils.limiter import limiter# F10 限流器
from routers import news,users,favorite,history,chat# 引入新闻路由,用户路由,收藏路由,历史路由,聊天路由

# 导入所有模型模块,确保表结构注册到metadata(启动时补建缺失的表,如chat_messages)
import models.chat# noqa: F401
import models.favorite# noqa: F401
import models.history# noqa: F401
import models.news# noqa: F401
import models.users# noqa: F401
import models.news_source# noqa: F401
import models.rag# noqa: F401
from models.favorite import Base
from config.db_conf import async_engine
from services.scheduler import start_scheduler,stop_scheduler# F8 定时任务

@asynccontextmanager
async def lifespan(app:FastAPI):
    """应用生命周期:启动时补建缺失数据表+种入默认RSS源+启动定时任务,关闭时停掉定时任务"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)# 只创建不存在的表,不影响已有表
    try:
        from services.news_fetcher import seed_default_sources
        added = await seed_default_sources()
        if added:
            print(f"已种入{added}个默认RSS新闻源")
    except Exception as e:
        print(f"种入默认新闻源失败(不影响启动):{e}")
    start_scheduler()
    yield
    stop_scheduler()

app  = FastAPI(lifespan=lifespan)

# F10: 注册限流器与429异常处理
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler)

# 注册全局异常处理函数
register_exception_handlers(app)

#挂载新闻路由
app.include_router(news.router)
#挂载注册路由
app.include_router(users.router)
#挂载收藏路由
app.include_router(favorite.router)
#挂载历史路由
app.include_router(history.router)
#挂载聊天路由
app.include_router(chat.router)



app.add_middleware(
    CORSMiddleware,#allow_origins=["http://localhost:3000"]表示允许的来源，*表示所有来源
    allow_origins=["*"],# 允许所有来源
    allow_credentials=True,# 允许跨域请求携带凭证
    allow_methods=["*"],# 允许所有HTTP方法
    allow_headers=["*"],# 允许所有HTTP头
)

# 挂载前端静态资源(必须在所有API路由之后,/api/*优先匹配)
from fastapi.staticfiles import StaticFiles# 静态文件服务
app.mount("/",StaticFiles(directory="static",html=True),name="frontend")
