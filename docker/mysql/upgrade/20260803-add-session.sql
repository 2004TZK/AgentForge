-- ============================================================
-- M2 多会话迁移（2026-08-03）：新增 session 表 + conversation.session_id
-- 适用：已在 Phase 1-2 部署过的数据库（全新部署由 01-schema.sql 直接建表）
-- 执行：由 docker/mysql/upgrade/migrate.sh 自动执行（M4 起），
--       或手动 mysql -uagentforge -p agentforge < 本文件
-- 说明：脚本幂等（列/索引已存在时自动跳过，可安全重放）。
-- ============================================================

USE `agentforge`;

-- 1. conversation 增加会话归属列（可空，旧数据不受影响）
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'conversation' AND COLUMN_NAME = 'session_id');
SET @ddl = IF(@col_exists = 0,
  'ALTER TABLE `conversation` ADD COLUMN `session_id` BIGINT UNSIGNED NULL COMMENT ''会话ID（NULL=旧版数据）'' AFTER `user_id`',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. 会话归属索引（历史按会话隔离查询）
SET @idx_exists = (SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'conversation' AND INDEX_NAME = 'idx_session_time');
SET @ddl = IF(@idx_exists = 0,
  'ALTER TABLE `conversation` ADD KEY `idx_session_time` (`session_id`, `created_time`)',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. 会话表
CREATE TABLE IF NOT EXISTS `session` (
  `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '会话ID',
  `agent_id`     BIGINT UNSIGNED NOT NULL                COMMENT '智能体ID',
  `user_id`      BIGINT UNSIGNED NOT NULL                COMMENT '用户ID',
  `name`         VARCHAR(100)    NOT NULL DEFAULT '新会话' COMMENT '会话名称（首条消息自动命名）',
  `deleted`      TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_agent_user_time` (`agent_id`, `user_id`, `updated_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会话表';
