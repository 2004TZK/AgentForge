-- ============================================================
-- AgentForge 迁移：默认对话模型统一为千问云端 qwen3.7-plus（决策 #10 清理）
--   背景：AI 服务已切换千问云端（qwen3.7-plus），但 agent.model_name
--   列默认值与存量种子数据仍为 deepseek-chat；未绑定 Provider 的 Agent
--   会把该模型名直发 DashScope 兼容端点，导致"模型不存在"错误。
--   1) 列默认值改为 qwen3.7-plus
--   2) 存量未绑定 Provider 且为 deepseek-chat 的 Agent 统一改为 qwen3.7-plus
--      （已绑定自定义 Provider 的 Agent 保留其模型名，不受影响）
-- 执行方式：由 docker/mysql/upgrade/migrate.sh 按文件名顺序自动应用
-- ============================================================

USE `agentforge`;

ALTER TABLE `agent`
  MODIFY COLUMN `model_name` VARCHAR(50) NOT NULL DEFAULT 'qwen3.7-plus' COMMENT '默认模型';

UPDATE `agent`
SET `model_name` = 'qwen3.7-plus'
WHERE `model_name` = 'deepseek-chat' AND `provider_id` IS NULL;
