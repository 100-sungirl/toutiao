-- 002: 新闻持续抓取 + AI会话/反馈/检索日志
-- 数据库: news_app

-- 1. 新闻源配置表
CREATE TABLE IF NOT EXISTS news_sources (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '源ID',
    name VARCHAR(50) NOT NULL COMMENT '源名称,如36氪',
    source_type VARCHAR(20) NOT NULL DEFAULT 'rss' COMMENT '类型:rss/api',
    url VARCHAR(500) NOT NULL COMMENT '订阅地址或API地址',
    category_id INT NOT NULL COMMENT '抓取新闻归入的分类ID',
    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用:1是0否',
    last_fetch_at DATETIME NULL COMMENT '最近一次抓取时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_source_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻源配置表';

-- 2. 抓取日志表
CREATE TABLE IF NOT EXISTS news_fetch_logs (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
    source_id INT NOT NULL COMMENT '新闻源ID',
    status VARCHAR(20) NOT NULL COMMENT '状态:success/failed',
    fetched_count INT NOT NULL DEFAULT 0 COMMENT '抓取条数',
    inserted_count INT NOT NULL DEFAULT 0 COMMENT '新插入条数',
    skipped_count INT NOT NULL DEFAULT 0 COMMENT '去重跳过条数',
    message VARCHAR(500) NULL COMMENT '备注/错误信息',
    duration_ms INT NOT NULL DEFAULT 0 COMMENT '耗时(毫秒)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_log_source_time (source_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻抓取日志表';

-- 3. AI对话会话表
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '会话ID',
    user_id INT NOT NULL COMMENT '用户ID',
    title VARCHAR(100) NOT NULL DEFAULT '新会话' COMMENT '会话标题',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后活跃时间',
    KEY idx_session_user (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI对话会话表';

-- 4. chat_messages 增加会话字段
ALTER TABLE chat_messages
    ADD COLUMN session_id INT NULL COMMENT '所属会话ID,空为历史遗留消息' AFTER user_id,
    ADD KEY idx_msg_session (session_id);

-- 5. 对话反馈表
CREATE TABLE IF NOT EXISTS rag_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '反馈ID',
    message_id INT NOT NULL COMMENT '被评价的assistant消息ID',
    user_id INT NOT NULL COMMENT '用户ID',
    rating TINYINT NOT NULL COMMENT '评分:1赞/-1踩',
    reason VARCHAR(255) NULL COMMENT '踩的原因,可选',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_feedback_user (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI对话反馈表';

-- 6. 检索日志表(RAG可观测性)
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
    user_id INT NULL COMMENT '用户ID,匿名可空',
    query VARCHAR(500) NOT NULL COMMENT '用户原始问题',
    rewritten_query VARCHAR(1000) NULL COMMENT '多轮改写/多查询后的问题,JSON数组',
    retrieved_news_ids JSON NULL COMMENT '召回的新闻ID列表',
    scores JSON NULL COMMENT '对应相似度分数列表',
    latency_ms INT NOT NULL DEFAULT 0 COMMENT '检索耗时(毫秒)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_retrieval_time (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG检索日志表';
