import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
# 项目根目录的.env优先(用户常编辑demo1/.env),toutiao_backend/.env兜底
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")

# ===== LLM 配置 =====
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-370bd008fe2d45afbb1de595fa20f50f")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
CHAT_MODEL_NAME = os.getenv("CHAT_MODEL_NAME", "deepseek-v4-flash-0731")
CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.7"))
CHAT_MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "2048"))

# ===== Embedding 配置 =====
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "qwen3.7-text-embedding-flash")
EMBEDDING_MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))

# ===== Milvus 配置 =====
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
MILVUS_URL=MILVUS_URI
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "news_rag")
RETRIEVE_TOP_K = int(os.getenv("RETRIEVE_TOP_K", "3"))

# ===== 对话历史配置 =====
CHAT_HISTORY_EXPIRE = int(os.getenv("CHAT_HISTORY_EXPIRE", "3600"))
CHAT_HISTORY_MAX_TURNS = int(os.getenv("CHAT_HISTORY_MAX_TURNS", "10"))

# ===== RAG 系统提示词 =====
RAG_SYSTEM_PROMPT = """你是『头条新闻小助手』，必须严格遵守：

1. 只能基于下面提供的【新闻上下文】回答用户问题，不要编造新闻内容。

2. 如果上下文中没有相关信息，请坦诚说"抱歉，根据现有新闻库我无法回答这个问题"。

3. 回答时请引用新闻标题或来源，让用户知道信息出处。

4. 用简洁清晰的中文回答。

【新闻上下文】：
{context}
"""

# ===== LangGraph Agent 系统提示词 =====
AGENT_SYSTEM_PROMPT = """你是『头条新闻小助手』,一个接入新闻业务数据的智能助手。

工具使用原则:
1. search_news:用户询问新闻/时事/具体事件,或回答需要新闻事实支撑时调用;输入一个独立完整的搜索问题。
2. get_hot_news:用户问"最近什么新闻最热/热搜榜/大家都在看什么"时调用。
3. get_my_favorites:用户问"我收藏了什么/我的收藏"时调用。

回答规范:
- 基于工具返回的新闻内容回答,引用新闻标题作为出处,不要编造新闻。
- 工具查不到相关资料时坦诚告知,不要硬答。
- 闲聊、常识性通用问题(如"你是谁""帮我写周报")不必调用工具,直接回答。
- 用简洁清晰的中文回答。"""

# ===== Dify平台集成(方式A:FastAPI调用Dify工作流) =====
DIFY_API_BASE = os.getenv("DIFY_API_BASE","http://localhost/v1")# Dify服务API地址
DIFY_DAILY_REPORT_KEY = os.getenv("DIFY_DAILY_REPORT_KEY","")# 日报工作流的API Key(Dify应用页面获取)
DIFY_TIMEOUT = int(os.getenv("DIFY_TIMEOUT","60"))# 工作流超时(秒)

# ===== 检索重排(Rerank)配置 F3 =====
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANK_MODEL = os.getenv("RERANK_MODEL", "qwen3.7-text-rerank")
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))
DASHSCOPE_RERANK_URL = os.getenv(
    "DASHSCOPE_RERANK_URL",
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
)

# ===== 多轮上下文改写 F6 =====
CONDENSE_PROMPT = """根据下面的对话历史,把用户的最新问题改写成一个不依赖上下文、可以独立理解的完整问题。
只输出改写后的问题本身,不要任何解释。如果问题本身已经完整,原样输出即可。

【对话历史】:
{history}

【最新问题】: {question}
改写后的问题:"""

# ===== 新闻自动摘要/标签 F4 =====
NEWS_SUMMARY_PROMPT = """请阅读下面的新闻,输出严格的JSON(不要markdown代码块,不要解释),格式:
{{"summary":"50字以内的新闻摘要","tags":["标签1","标签2","标签3"]}}

【新闻】:
{text}"""

# ===== 定时任务 F8 =====
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "30"))  # 向量补同步周期,sync_interval_minutes
SUMMARY_BACKFILL_MINUTES = int(os.getenv("SUMMARY_BACKFILL_MINUTES", "60"))  # 摘要回填周期,summary_backfill_minutes

# ===== 新闻持续抓取 =====
NEWS_FETCH_MINUTES = int(os.getenv("NEWS_FETCH_MINUTES", "30"))  # RSS抓取周期,news_fetch

# ===== 接口限流 F10 =====
CHAT_RATE_LIMIT = os.getenv("CHAT_RATE_LIMIT", "10/minute")
SEARCH_RATE_LIMIT = os.getenv("SEARCH_RATE_LIMIT", "30/minute")
CREATE_RATE_LIMIT = os.getenv("CREATE_RATE_LIMIT", "10/minute")
