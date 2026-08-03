-- ============================================================
-- H2 测试库表结构（与 docker/mysql/init/01-schema.sql 对齐的 H2 兼容子集）
-- 说明：H2 不支持 UNSIGNED / 列 COMMENT / 内联 KEY / ENGINE 子句，
--       此处仅保留类型与约束语义一致的最小 DDL；
--       逻辑删除（deleted）、时间戳默认值等行为与 MySQL 保持一致。
-- ============================================================

CREATE TABLE `user` (
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

CREATE TABLE `agent` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name`          VARCHAR(100) NOT NULL,
  `description`   VARCHAR(500),
  `system_prompt` CLOB         NOT NULL,
  `model_name`    VARCHAR(50)  NOT NULL DEFAULT 'deepseek-chat',
  `temperature`   DECIMAL(3,2) NOT NULL DEFAULT 0.70,
  `creator_id`    BIGINT       NOT NULL,
  `deleted`       TINYINT      NOT NULL DEFAULT 0,
  `created_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_agent_creator` FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
);

CREATE TABLE `agent_tool` (
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

CREATE TABLE `document` (
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

CREATE TABLE `session` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `agent_id`     BIGINT       NOT NULL,
  `user_id`      BIGINT       NOT NULL,
  `name`         VARCHAR(100) NOT NULL DEFAULT '新会话',
  `deleted`      TINYINT      NOT NULL DEFAULT 0,
  `created_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE `conversation` (
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
