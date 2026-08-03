-- ============================================================
-- M4 迁移：Agent 公开/私有可见性（决策 #6）
-- 公开 PUBLIC（所有人可见）/ 私有 PRIVATE（仅创建者可见，默认）
-- 执行方式：由 docker/mysql/upgrade/migrate.sh 自动执行（M4 起），
--       或手动 mysql -uagentforge -p agentforge < 本文件
-- 说明：脚本幂等（列已存在时自动跳过，可安全重放）。
-- ============================================================

USE `agentforge`;

SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent' AND COLUMN_NAME = 'visibility');
SET @ddl = IF(@col_exists = 0,
  'ALTER TABLE `agent` ADD COLUMN `visibility` VARCHAR(20) NOT NULL DEFAULT ''PRIVATE'' COMMENT ''可见性 PUBLIC/PRIVATE（私有仅创建者可见）'' AFTER `workflow_id`',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
