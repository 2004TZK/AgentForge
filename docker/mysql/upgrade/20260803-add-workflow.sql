-- ============================================================
-- M3 迁移：Workflow v1（工作流定义/节点/运行记录表）+ Agent 运行模式
-- 执行方式：由 docker/mysql/upgrade/migrate.sh 自动执行（M4 起），
--       或手动 mysql -h 127.0.0.1 -P 3307 -uroot -p < 本文件
-- 说明：脚本幂等（列已存在时自动跳过，可安全重放）。
-- ============================================================

USE `agentforge`;

-- ------------------------------------------------------------
-- 智能体表新增运行模式与工作流绑定
-- ------------------------------------------------------------
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent' AND COLUMN_NAME = 'mode');
SET @ddl = IF(@col_exists = 0,
  'ALTER TABLE `agent` ADD COLUMN `mode` VARCHAR(20) NOT NULL DEFAULT ''chat'' COMMENT ''运行模式 chat/workflow'' AFTER `temperature`, ADD COLUMN `workflow_id` BIGINT UNSIGNED DEFAULT NULL COMMENT ''绑定的工作流ID（mode=workflow 时生效）'' AFTER `mode`',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------
-- 工作流定义表（元数据 + 描述）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `workflow` (
  `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '工作流ID',
  `name`         VARCHAR(100)    NOT NULL                COMMENT '工作流名称',
  `description`  VARCHAR(500)    DEFAULT NULL            COMMENT '描述',
  `creator_id`   BIGINT UNSIGNED NOT NULL                COMMENT '创建者ID',
  `status`       VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE' COMMENT '状态 ACTIVE/DISABLED',
  `deleted`      TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_creator` (`creator_id`),
  CONSTRAINT `fk_workflow_creator` FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='工作流定义表';

-- ------------------------------------------------------------
-- 工作流节点表（节点键/类型/参数/下一节点，线性链）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `workflow_node` (
  `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '节点ID',
  `workflow_id`  BIGINT UNSIGNED NOT NULL                COMMENT '工作流ID',
  `node_key`     VARCHAR(100)    NOT NULL                COMMENT '节点键（变量引用/日志标识）',
  `node_type`    VARCHAR(20)     NOT NULL                COMMENT '节点类型 llm/tool',
  `params`       JSON            DEFAULT NULL            COMMENT '节点参数（tool/llm 配置，含 {var} 模板）',
  `next_node`    VARCHAR(100)    DEFAULT NULL            COMMENT '下一节点键（NULL=流程结束）',
  `deleted`      TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_workflow_node` (`workflow_id`, `node_key`),
  CONSTRAINT `fk_workflow_node_wf` FOREIGN KEY (`workflow_id`) REFERENCES `workflow` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='工作流节点表';

-- ------------------------------------------------------------
-- 工作流运行记录表（节点级日志 JSON）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `workflow_run` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '运行ID',
  `workflow_id`   BIGINT UNSIGNED NOT NULL                COMMENT '工作流ID',
  `agent_id`      BIGINT UNSIGNED DEFAULT NULL            COMMENT '触发 Agent（对话模式触发时）',
  `user_id`       BIGINT UNSIGNED NOT NULL                COMMENT '触发用户ID',
  `input`         JSON            DEFAULT NULL            COMMENT '运行输入 {key: value}',
  `status`        VARCHAR(20)     NOT NULL DEFAULT 'RUNNING' COMMENT 'RUNNING/SUCCESS/FAILED',
  `output`        TEXT            DEFAULT NULL            COMMENT '最终输出',
  `node_logs`     JSON            DEFAULT NULL            COMMENT '节点级日志 [{node,type,status,output,error,durationMs}]',
  `error`         VARCHAR(500)    DEFAULT NULL            COMMENT '失败原因',
  `started_time`  DATETIME        DEFAULT NULL            COMMENT '开始时间',
  `finished_time` DATETIME        DEFAULT NULL            COMMENT '结束时间',
  `deleted`       TINYINT(1)      NOT NULL DEFAULT 0      COMMENT '逻辑删除',
  `created_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_workflow_user` (`workflow_id`, `user_id`, `created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='工作流运行记录表（节点级日志）';
