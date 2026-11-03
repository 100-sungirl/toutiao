"""把MySQL中的新闻数据灌入Milvus，构建向量索引（仅执行一次）"""
import os
import sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))# 把项目根目录加入path,支持直接运行

import asyncio
from sqlalchemy import select#select用于查询数据库中的新闻数据
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_community.embeddings import DashScopeEmbeddings

from config.db_conf import AsyncSessionLocal# 项目数据库配置文件是db_conf.py
from models.news import News
from config.ai_config import (
    DASHSCOPE_API_KEY,EMBEDDING_MODEL_NAME,EMBEDDING_MAX_RETRIES,
    MILVUS_URL,MILVUS_COLLECTION
)

async def build():
    """1.从MySQL中查询所有新闻"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(News))
        news_list=result.scalars().all()#scalars()用于将查询结果转换为Python对象列表
    print (f"从MySQL中查询到{len(news_list)}条新闻数据")

    """2.转换为langchain文档对象Document"""
    docs=[]
    for n in news_list:
        content = f"标题:{n.title}\n描述:{n.description}\n正文:{n.content}"
        docs.append(
            Document(# 必须用Document构造,不能直接把字段传给list.append
                page_content=content,
                metadata={
                    "news_id":n.id,
                    "title":n.title,
                    "author":n.author,
                    "category_id":n.category_id,
                },
            )
        )

    """3.初始化embedding"""
    embeddings = DashScopeEmbeddings(
        model = EMBEDDING_MODEL_NAME,
        max_retries = EMBEDDING_MAX_RETRIES,
        dashscope_api_key = DASHSCOPE_API_KEY,
    )

    """4.初始化Milvus并分批灌入(DashScope embedding单批上限25条,取20保险)"""
    print(f"开始向Milvus中灌入数据(collection={MILVUS_COLLECTION})...")
    batch_size = 20
    store = None
    for i in range(0, len(docs), batch_size):
        chunk = docs[i:i+batch_size]
        if store is None:
            # 首批建collection,drop_old清掉旧数据保证干净重建
            store = Milvus.from_documents(
                documents=chunk,
                embedding=embeddings,
                collection_name=MILVUS_COLLECTION,
                connection_args={"uri":MILVUS_URL},
                drop_old=True,
            )
        else:
            await asyncio.to_thread(store.add_documents, chunk)
        print(f"已灌入 {min(i+batch_size, len(docs))}/{len(docs)} 条")
    print(f"数据灌入完成,共灌入{len(docs)}条数据")

    """5.把全部新闻ID标记为已同步,防止定时补同步任务(F8)重复灌入"""
    from config.cache_conf import redis_client
    try:
        ids = [n.id for n in news_list]
        if ids:
            await redis_client.sadd("news:vector:synced", *ids)#*ids表示展开列表,把每个元素作为参数传给sadd
            print(f"已标记{len(ids)}条新闻ID为已同步")
    except Exception as e:
        print(f"标记已同步ID失败(不影响灌库,但定时任务可能重复灌入):{e}")

if __name__ == "__main__":
    asyncio.run(build())
