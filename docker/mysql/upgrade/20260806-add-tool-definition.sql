-- ============================================================
-- 用户自定义工具（工具定义开发文档 v3.0 §5）：
--   1) 新增 tool_definition 表（用户自定义工具定义：HTTP 工具 / 代码工具）
--   2) agent_tool 表扩展 tool_source / tool_definition_id（区分内置/自定义来源）
-- 应用：docker compose up migrate（或手动执行）
-- ============================================================

CREATE TABLE IF NOT EXISTS `tool_definition` (
  `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `creator_id`     BIGINT UNSIGNED NOT NULL COMMENT '创建者ID',
  `name`           VARCHAR(100)    NOT NULL COMMENT '工具名（用户级唯一，供 LLM 调用）',
  `display_name`   VARCHAR(100)    NOT NULL COMMENT '展示名称',
  `description`    VARCHAR(500)    DEFAULT NULL COMMENT '给 LLM 看的工具描述',
  `tool_type`      VARCHAR(20)     NOT NULL COMMENT 'http / script',
  `parameters`     JSON            NOT NULL COMMENT 'LLM 调用参数 Schema（OpenAI function parameters）',
  `http_config`    JSON            DEFAULT NULL COMMENT 'HTTP 请求定义（tool_type=http，密钥字段已加密）',
  `script_config`  JSON            DEFAULT NULL COMMENT '代码定义（tool_type=script）',
  `visibility`     VARCHAR(20)     NOT NULL DEFAULT 'PRIVATE' COMMENT 'PRIVATE/PUBLIC',
  `deleted`        TINYINT(1)      NOT NULL DEFAULT 0,
  `created_time`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_creator_name` (`creator_id`, `name`),
  KEY `idx_creator` (`creator_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户自定义工具定义';

-- agent_tool 扩展：工具来源（builtin=内置注册表 / custom=自定义工具定义）
ALTER TABLE `agent_tool`
  ADD COLUMN `tool_source`        VARCHAR(16)  NOT NULL DEFAULT 'builtin' COMMENT 'builtin/custom' AFTER `tool_name`,
  ADD COLUMN `tool_definition_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '自定义工具定义ID（tool_source=custom 时）' AFTER `tool_source`;
