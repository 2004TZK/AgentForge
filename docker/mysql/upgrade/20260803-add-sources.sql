-- ============================================================
-- M2 验证修复（2026-08-03）：conversation 增加 sources 列
-- 引用来源落库，历史消息可回溯引用（同步/流式回答均已存储）。
-- 适用：已应用 20260803-add-session.sql 的部署
-- 执行：由 docker/mysql/upgrade/migrate.sh 自动执行（M4 起），
--       或手动 mysql -uagentforge -p agentforge < 本文件
-- 说明：脚本幂等（列已存在时自动跳过，可安全重放）。
-- ============================================================

USE `agentforge`;

SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'conversation' AND COLUMN_NAME = 'sources');
SET @ddl = IF(@col_exists = 0,
  'ALTER TABLE `conversation` ADD COLUMN `sources` JSON NULL COMMENT ''引用来源 [{file,snippet,score}]（M2 起，旧数据为 NULL）'' AFTER `assistant_message`',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
