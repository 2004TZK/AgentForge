-- ============================================================
-- AgentForge 初始化数据（幂等：显式 ID + ON DUPLICATE KEY UPDATE，
-- 容器重建 / 脚本重复执行均安全）
-- ============================================================

USE `agentforge`;

START TRANSACTION;

-- ------------------------------------------------------------
-- 管理员账号 admin / admin123
-- （BCrypt 哈希与注册流程同款生成；仅限本地开发，生产部署后强制改密）
-- ------------------------------------------------------------
INSERT INTO `user` (`id`, `username`, `email`, `password_hash`, `avatar`)
VALUES (1, 'admin', 'admin@agentforge.local',
        '$2b$10$20.IynHLSka9ShRP7e27SOiTmF1j1sDVV861ScdhDTYo2HQia/uSC', NULL)
ON DUPLICATE KEY UPDATE `email` = VALUES(`email`), `password_hash` = VALUES(`password_hash`);

-- ------------------------------------------------------------
-- 示例智能体「Java Expert」
-- ------------------------------------------------------------
INSERT INTO `agent` (`id`, `name`, `description`, `system_prompt`, `model_name`, `temperature`, `creator_id`)
VALUES (1, 'Java Expert', '资深 Java 工程师，帮助解决 Java 相关问题。',
        '你是一名资深Java工程师，帮助用户解决Java问题。',
        'deepseek-chat', 0.70, 1)
ON DUPLICATE KEY UPDATE
  `name`          = VALUES(`name`),
  `description`   = VALUES(`description`),
  `system_prompt` = VALUES(`system_prompt`),
  `model_name`    = VALUES(`model_name`),
  `temperature`   = VALUES(`temperature`),
  `creator_id`    = VALUES(`creator_id`);

-- ------------------------------------------------------------
-- 示例智能体「Research Agent」：绑定 Github Tool + Calculator Tool
-- ------------------------------------------------------------
INSERT INTO `agent` (`id`, `name`, `description`, `system_prompt`, `model_name`, `temperature`, `creator_id`)
VALUES (2, 'Research Agent', '研究助手，可查询 Github 仓库信息并完成计算。',
        '你是一名研究助手，优先使用工具获取 Github 仓库信息，并用计算器完成数值计算。',
        'deepseek-chat', 0.70, 1)
ON DUPLICATE KEY UPDATE
  `name`          = VALUES(`name`),
  `description`   = VALUES(`description`),
  `system_prompt` = VALUES(`system_prompt`),
  `model_name`    = VALUES(`model_name`),
  `temperature`   = VALUES(`temperature`),
  `creator_id`    = VALUES(`creator_id`);

INSERT INTO `agent_tool` (`id`, `agent_id`, `tool_name`, `tool_config`, `enabled`)
VALUES (1, 2, 'github', JSON_OBJECT(), 1),
       (2, 2, 'calculator', JSON_OBJECT(), 1)
ON DUPLICATE KEY UPDATE `tool_config` = VALUES(`tool_config`), `enabled` = VALUES(`enabled`);

COMMIT;
