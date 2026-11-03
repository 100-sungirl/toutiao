-- AI对话反馈模块升级迁移(F反馈逻辑完善)
-- 执行方式: python utils/run_migration.py (可重复执行,幂等)

-- 1. rag_feedback表新增更新时间列(改评分/原因时自动刷新)
ALTER TABLE rag_feedback
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间(改评分/原因时刷新)';

-- 2. 清理历史重复反馈(同一用户对同一消息只保留最新一条,否则唯一索引创建失败)
DELETE FROM rag_feedback WHERE id NOT IN (
    SELECT max_id FROM (
        SELECT MAX(id) AS max_id FROM rag_feedback GROUP BY user_id, message_id
    ) t
);

-- 3. 唯一约束:同一用户对同一条消息只有一条反馈,重复提交走更新而非插入
ALTER TABLE rag_feedback
    ADD UNIQUE KEY uq_feedback_user_message (user_id, message_id);
