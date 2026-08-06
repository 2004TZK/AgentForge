-- ============================================================
-- AgentForge 迁移：内置工具可编辑副本（tool_type=builtin）
--   tool_definition 新增 builtin_name：引用系统内置工具（如 calculator/github），
--   用户复制内置工具后得到可编辑副本（描述/参数/默认配置可改，执行仍走内置实现）
-- ============================================================

USE `agentforge`;

ALTER TABLE `tool_definition`
  ADD COLUMN `builtin_name` VARCHAR(100) DEFAULT NULL COMMENT '内置工具引用（tool_type=builtin）' AFTER `tool_type`;
