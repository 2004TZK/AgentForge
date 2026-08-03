-- ============================================================
-- M4 迁移：多模型配置（决策 #12）
--   model_provider 表（多 Provider 并存：本地 Ollama / 远端 OpenAI 兼容）
--   agent.provider_id 绑定默认 Provider（缺省 NULL = 内置 Ollama）
-- 执行方式：由 docker/mysql/upgrade/migrate.sh 自动执行（M4 起），
--       或手动 mysql -uagentforge -p agentforge < 本文件
-- 说明：脚本幂等（表/列已存在时自动跳过，可安全重放）。
-- ============================================================

USE `agentforge`;

-- 1. Provider 表
CREATE TABLE IF NOT EXISTS `model_provider` (
  `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Provider ID',
  `name`         VARCHAR(100)    NOT NULL                COMMENT '名称（如 本地 Ollama / DeepSeek 云端）',
  `provider_type` VARCHAR(20)    NOT NULL DEFAULT 'ollama' COMMENT '类型 ollama（本地原生/think 可控）/ openai（OpenAI 兼容）',
  `base_url`     VARCHAR(300)    NOT NULL                COMMENT 'API 基础地址（如 http://ollama:11434 或 https://api.deepseek.com/v1）',
  `api_key`      VARCHAR(300)    DEFAULT NULL            COMMENT 'API Key（本地模型留空）',
  `models`       JSON            DEFAULT NULL            COMMENT '可用模型名列表 ["qwen3.5:0.8b", ...]',
  `enabled`      TINYINT(1)      NOT NULL DEFAULT 1      COMMENT '是否启用',
  `creator_id`   BIGINT UNSIGNED NOT NULL                COMMENT '创建者 ID（0=系统内置）',
  `deleted`      TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_provider_creator` (`creator_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型 Provider 配置（多 Provider 并存）';

-- 2. agent 绑定 Provider
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent' AND COLUMN_NAME = 'provider_id');
SET @ddl = IF(@col_exists = 0,
  'ALTER TABLE `agent` ADD COLUMN `provider_id` BIGINT UNSIGNED DEFAULT NULL COMMENT ''模型 Provider ID（NULL=内置 Ollama）'' AFTER `model_name`',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. 内置默认 Provider（本地 Ollama，creator_id=0 系统内置）
INSERT INTO `model_provider` (`name`, `provider_type`, `base_url`, `api_key`, `models`, `creator_id`)
SELECT '本地 Ollama', 'ollama', 'http://ollama:11434', NULL,
       JSON_ARRAY('qwen3.5:0.8b', 'bge-m3'),
       0
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM `model_provider` WHERE `creator_id` = 0 AND `provider_type` = 'ollama');
