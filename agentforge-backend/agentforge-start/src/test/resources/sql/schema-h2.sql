-- ============================================================
-- H2 测试库表结构（与 docker/mysql/init/01-schema.sql 对齐的 H2 兼容子集）
-- 说明：H2 不支持 UNSIGNED / 列 COMMENT / 内联 KEY / ENGINE 子句，
--       此处仅保留类型与约束语义一致的最小 DDL；
--       逻辑删除（deleted）、时间戳默认值等行为与 MySQL 保持一致。
--       全部 CREATE 使用 IF NOT EXISTS：多 Spring 上下文共享同一内存库
--       （DB_CLOSE_DELAY=-1）时脚本幂等执行。
-- ============================================================

CREATE TABLE IF NOT EXISTS `user` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `username`      VARCHAR(50)  NOT NULL,
  `email`         VARCHAR(100),
  `password_hash` VARCHAR(100) NOT NULL,
  `avatar`        VARCHAR(255),
  `deleted`       TINYINT      NOT NULL DEFAULT 0,
  `created_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_user_username` UNIQUE (`username`),
  CONSTRAINT `uk_user_email` UNIQUE (`email`)
);

CREATE TABLE IF NOT EXISTS `agent` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name`          VARCHAR(100) NOT NULL,
  `description`   VARCHAR(500),
  `system_prompt` CLOB         NOT NULL,
  `model_name`    VARCHAR(50)  NOT NULL DEFAULT 'deepseek-chat',
  `temperature`   DECIMAL(3,2) NOT NULL DEFAULT 0.70,
  `mode`          VARCHAR(20)  NOT NULL DEFAULT 'chat',
  `workflow_id`   BIGINT,
  `creator_id`    BIGINT       NOT NULL,
  `deleted`       TINYINT      NOT NULL DEFAULT 0,
  `created_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_agent_creator` FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
);

CREATE TABLE IF NOT EXISTS `agent_tool` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `agent_id`     BIGINT       NOT NULL,
  `tool_name`    VARCHAR(100) NOT NULL,
  `tool_config`  JSON,
  `enabled`      TINYINT      NOT NULL DEFAULT 1,
  `deleted`      TINYINT      NOT NULL DEFAULT 0,
  `created_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_agent_tool` UNIQUE (`agent_id`, `tool_name`),
  CONSTRAINT `fk_agent_tool_agent` FOREIGN KEY (`agent_id`) REFERENCES `agent` (`id`)
);

CREATE TABLE IF NOT EXISTS `document` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `agent_id`     BIGINT       NOT NULL,
  `file_name`    VARCHAR(255) NOT NULL,
  `file_path`    VARCHAR(500) NOT NULL,
  `file_type`    VARCHAR(50)  NOT NULL,
  `status`       VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
  `deleted`      TINYINT      NOT NULL DEFAULT 0,
  `created_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `session` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `agent_id`     BIGINT       NOT NULL,
  `user_id`      BIGINT       NOT NULL,
  `name`         VARCHAR(100) NOT NULL DEFAULT '新会话',
  `deleted`      TINYINT      NOT NULL DEFAULT 0,
  `created_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `conversation` (
  `id`                BIGINT  NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `agent_id`          BIGINT  NOT NULL,
  `user_id`           BIGINT  NOT NULL,
  `session_id`        BIGINT,
  `user_message`      CLOB,
  `assistant_message` CLOB,
  `sources`           CLOB,
  `deleted`           TINYINT NOT NULL DEFAULT 0,
  `created_time`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- M3 Workflow v1（与 docker/mysql/upgrade/20260803-add-workflow.sql 对齐）
-- ============================================================

CREATE TABLE IF NOT EXISTS `workflow` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name`         VARCHAR(100) NOT NULL,
  `description`  VARCHAR(500),
  `creator_id`   BIGINT       NOT NULL,
  `status`       VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
  `deleted`      TINYINT      NOT NULL DEFAULT 0,
  `created_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_workflow_creator` FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
);

-- 注意：H2 JSON 类型列回读为双重编码字符串，JacksonTypeHandler 无法解析；
-- 与 conversation.sources 同约定，JSON 列一律用 CLOB（MySQL 端仍为 JSON 列）。
CREATE TABLE IF NOT EXISTS `workflow_node` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `workflow_id`  BIGINT       NOT NULL,
  `node_key`     VARCHAR(100) NOT NULL,
  `node_type`    VARCHAR(20)  NOT NULL,
  `params`       CLOB,
  `next_node`    VARCHAR(100),
  `deleted`      TINYINT      NOT NULL DEFAULT 0,
  `created_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_workflow_node` UNIQUE (`workflow_id`, `node_key`),
  CONSTRAINT `fk_workflow_node_wf` FOREIGN KEY (`workflow_id`) REFERENCES `workflow` (`id`)
);

CREATE TABLE IF NOT EXISTS `workflow_run` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `workflow_id`   BIGINT       NOT NULL,
  `agent_id`      BIGINT,
  `user_id`       BIGINT       NOT NULL,
  `input`         CLOB,
  `status`        VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',
  `output`        CLOB,
  `node_logs`     CLOB,
  `error`         VARCHAR(500),
  `started_time`  DATETIME,
  `finished_time` DATETIME,
  `deleted`       TINYINT      NOT NULL DEFAULT 0,
  `created_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
