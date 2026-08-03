-- ============================================================
-- M2 验证修复（2026-08-03）：conversation 增加 sources 列
-- 引用来源落库，历史消息可回溯引用（同步/流式回答均已存储）。
-- 适用：已应用 20260803-add-session.sql 的部署
-- 执行：mysql -uagentforge -p agentforge < 20260803-add-sources.sql
-- ============================================================

USE `agentforge`;

ALTER TABLE `conversation`
  ADD COLUMN `sources` JSON NULL COMMENT '引用来源 [{file,snippet,score}]（M2 起，旧数据为 NULL）' AFTER `assistant_message`;
