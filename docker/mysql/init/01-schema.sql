-- ============================================================
-- AgentForge 数据库初始化：建库建表（基线迁移）
-- 约定：utf8mb4 / utf8mb4_0900_ai_ci / InnoDB
--       全部业务表含 deleted 逻辑删除字段（配合 MyBatis Plus 逻辑删除）
--       created_time 默认当前时间，updated_time 自动更新
--       Phase 2 起该脚本作为 Flyway 基线迁移
-- ============================================================

CREATE DATABASE IF NOT EXISTS `agentforge`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `agentforge`;

-- ------------------------------------------------------------
-- 用户表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username`      VARCHAR(50)     NOT NULL                COMMENT '用户名',
  `email`         VARCHAR(100)    DEFAULT NULL            COMMENT '邮箱',
  `password_hash` VARCHAR(100)    NOT NULL                COMMENT 'BCrypt密码哈希',
  `avatar`        VARCHAR(255)    DEFAULT NULL            COMMENT '头像URL',
  `deleted`       TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除 0-否 1-是',
  `created_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';

-- ------------------------------------------------------------
-- 智能体表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `agent` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '智能体ID',
  `name`          VARCHAR(100)    NOT NULL                COMMENT '智能体名称',
  `description`   VARCHAR(500)    DEFAULT NULL            COMMENT '描述',
  `system_prompt` TEXT            NOT NULL                COMMENT '系统提示词',
  `model_name`    VARCHAR(50)     NOT NULL DEFAULT 'deepseek-chat' COMMENT '默认模型',
  `provider_id`   BIGINT UNSIGNED DEFAULT NULL            COMMENT '模型 Provider ID（M4，NULL=默认）',
  `temperature`   DECIMAL(3,2)    NOT NULL DEFAULT 0.70   COMMENT '采样温度',
  `mode`          VARCHAR(20)     NOT NULL DEFAULT 'chat' COMMENT '运行模式 chat/workflow（M3）',
  `workflow_id`   BIGINT UNSIGNED DEFAULT NULL            COMMENT '绑定的工作流ID（mode=workflow 时生效）',
  `visibility`    VARCHAR(20)     NOT NULL DEFAULT 'PRIVATE' COMMENT '可见性 PUBLIC/PRIVATE（M4）',
  `creator_id`    BIGINT UNSIGNED NOT NULL                COMMENT '创建者ID',
  `deleted`       TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_creator_id` (`creator_id`),
  CONSTRAINT `fk_agent_creator` FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='智能体表';

-- ------------------------------------------------------------
-- 工具配置表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `agent_tool` (
  `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `agent_id`     BIGINT UNSIGNED NOT NULL                COMMENT '智能体ID',
  `tool_name`    VARCHAR(100)    NOT NULL                COMMENT '工具名 calculator/github',
  `tool_config`  JSON            DEFAULT NULL            COMMENT '工具参数配置',
  `enabled`      TINYINT(1)      NOT NULL DEFAULT 1      COMMENT '是否启用',
  `deleted`      TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_tool` (`agent_id`, `tool_name`),
  CONSTRAINT `fk_agent_tool_agent` FOREIGN KEY (`agent_id`) REFERENCES `agent` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='工具配置表';

-- ------------------------------------------------------------
-- 文档表（文件内容不存 MySQL：Chunk 向量存 Qdrant，原始文件存共享卷）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `document` (
  `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '文档ID',
  `agent_id`     BIGINT UNSIGNED NOT NULL                COMMENT '所属智能体ID',
  `file_name`    VARCHAR(255)    NOT NULL                COMMENT '原始文件名',
  `file_path`    VARCHAR(500)    NOT NULL                COMMENT '相对存储路径',
  `file_type`    VARCHAR(50)     NOT NULL                COMMENT 'pdf/docx/txt/md',
  `status`       VARCHAR(20)     NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/PROCESSING/READY/FAILED',
  `deleted`      TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_agent_id` (`agent_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='文档表';

-- ------------------------------------------------------------
-- 会话表（M2 多会话：同一 Agent 下用户可建多个会话，历史按会话隔离）
-- ------------------------------------------------------------
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

-- ------------------------------------------------------------
-- 对话记录表（一问一答一行；M2 起按会话隔离，session_id 为 NULL 表示历史遗留数据）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `conversation` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '记录ID',
  `agent_id`          BIGINT UNSIGNED NOT NULL                COMMENT '智能体ID',
  `user_id`           BIGINT UNSIGNED NOT NULL                COMMENT '用户ID',
  `session_id`        BIGINT UNSIGNED NULL                    COMMENT '会话ID（NULL=旧版数据）',
  `user_message`      TEXT            NULL                    COMMENT '用户消息',
  `assistant_message` TEXT            NULL                    COMMENT '助手回复',
  `sources`           JSON            NULL                    COMMENT '引用来源 [{file,snippet,score}]（M2 起，旧数据为 NULL）',
  `deleted`           TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_agent_user_time` (`agent_id`, `user_id`, `created_time`),
  KEY `idx_session_time` (`session_id`, `created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='对话记录表（一问一答一行）';
