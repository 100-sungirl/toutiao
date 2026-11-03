-- AI功能扩展迁移脚本(F2对话持久化 + F4摘要标签)
-- 执行方式: python utils/run_migration.py (可重复执行,幂等)

-- F4: 新闻表新增AI摘要与标签列
ALTER TABLE news ADD COLUMN summary TEXT NULL COMMENT 'AI生成的新闻摘要';
ALTER TABLE news ADD COLUMN tags VARCHAR(255) NULL COMMENT 'AI生成的标签,逗号分隔';

-- F2: 对话历史持久化表
CREATE TABLE IF NOT EXISTS chat_messages (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID',
    user_id INT NOT NULL COMMENT '用户ID',
    role VARCHAR(20) NOT NULL COMMENT '角色:user/assistant',
    content TEXT NOT NULL COMMENT '消息内容',
    sources TEXT NULL COMMENT '引用来源JSON,仅assistant消息有',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_chat_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户AI对话记录表';
