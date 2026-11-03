"""执行AI功能迁移(幂等,可重复运行):news表补列 + chat_messages建表 + rag_feedback表升级"""
import os
import sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))# 把项目根目录加入path,支持直接运行

import pymysql
from config.db_conf import ASYNC_DATABASE_URL

def _parse_url(url:str)->dict:
    """mysql+aiomysql://user:pwd@host:port/dbname?charset=utf8mb4 -> 连接参数"""
    body = url.split("://",1)[1]
    auth_host, dbname_q = body.split("/",1)
    dbname = dbname_q.split("?")[0]
    auth, host_port = auth_host.split("@",1)
    user, pwd = auth.split(":",1)
    host, port = host_port.split(":",1)
    return dict(host=host, port=int(port), user=user, password=pwd, database=dbname)

def column_exists(cur, table:str, column:str)->bool:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (table, column),
    )
    return cur.fetchone()[0] > 0

def index_exists(cur, table:str, name:str)->bool:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s",
        (table, name),
    )
    return cur.fetchone()[0] > 0

def run():
    conf = _parse_url(ASYNC_DATABASE_URL)
    conn = pymysql.connect(**conf)#字典解包
    try:
        with conn.cursor() as cur:
            # F4: news表补列(存在则跳过)
            if not column_exists(cur, "news", "summary"):
                cur.execute("ALTER TABLE news ADD COLUMN summary TEXT NULL COMMENT 'AI生成的新闻摘要'")
                print("已添加列: news.summary")
            else:
                print("列已存在,跳过: news.summary")
            if not column_exists(cur, "news", "tags"):
                cur.execute("ALTER TABLE news ADD COLUMN tags VARCHAR(255) NULL COMMENT 'AI生成的标签,逗号分隔'")
                print("已添加列: news.tags")
            else:
                print("列已存在,跳过: news.tags")
            # F2: 对话表(IF NOT EXISTS幂等)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID',
                    user_id INT NOT NULL COMMENT '用户ID',
                    role VARCHAR(20) NOT NULL COMMENT '角色:user/assistant',
                    content TEXT NOT NULL COMMENT '消息内容',
                    sources TEXT NULL COMMENT '引用来源JSON,仅assistant消息有',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    INDEX idx_chat_user_time (user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户AI对话记录表'
            """)
            print("表已就绪: chat_messages")

            # 003: rag_feedback表升级(补updated_at列 + 唯一约束防重复反馈)
            cur.execute("""CREATE TABLE IF NOT EXISTS rag_feedback (
                id INT PRIMARY KEY AUTO_INCREMENT COMMENT '反馈ID',
                message_id INT NOT NULL COMMENT '被评价的assistant消息ID',
                user_id INT NOT NULL COMMENT '用户ID',
                rating INT NOT NULL COMMENT '评分:1赞/-1踩',
                reason VARCHAR(255) NULL COMMENT '踩的原因,可选',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                INDEX idx_feedback_user (user_id, created_at),
                UNIQUE KEY uq_feedback_user_message (user_id, message_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI对话反馈表'""")
            print("表已就绪: rag_feedback")
            if not column_exists(cur, "rag_feedback", "updated_at"):
                cur.execute("ALTER TABLE rag_feedback ADD COLUMN updated_at DATETIME NOT NULL "
                            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'")
                print("已添加列: rag_feedback.updated_at")
            else:
                print("列已存在,跳过: rag_feedback.updated_at")
            if not index_exists(cur, "rag_feedback", "uq_feedback_user_message"):
                # 先清理历史重复数据(同用户同消息只保留最新一条),否则唯一索引创建失败
                cur.execute("""DELETE FROM rag_feedback WHERE id NOT IN (
                    SELECT max_id FROM (
                        SELECT MAX(id) AS max_id FROM rag_feedback GROUP BY user_id, message_id
                    ) t)""")
                if cur.rowcount:
                    print(f"已清理重复反馈{cur.rowcount}条")
                cur.execute("ALTER TABLE rag_feedback ADD UNIQUE KEY uq_feedback_user_message (user_id, message_id)")
                print("已添加唯一索引: uq_feedback_user_message")
            else:
                print("索引已存在,跳过: uq_feedback_user_message")
        conn.commit()
        print("迁移完成")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
