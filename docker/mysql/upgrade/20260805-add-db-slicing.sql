-- ============================================================
-- 数据库文件自动切片（设计 v0.2 §8.2）：document 表新增切片元数据字段
-- 应用：docker compose up migrate（或手动执行）
-- ============================================================
ALTER TABLE `document`
  ADD COLUMN `chunk_count`      INT UNSIGNED NOT NULL DEFAULT 0  COMMENT '切片数（入库完成后回填）' AFTER `status`,
  ADD COLUMN `slicing_mode`     VARCHAR(16)  NOT NULL DEFAULT 'auto' COMMENT '切片方式：auto/manual' AFTER `chunk_count`,
  ADD COLUMN `slicing_config`   JSON         NULL                COMMENT '手动切片参数快照（重试沿用）' AFTER `slicing_mode`,
  ADD COLUMN `processed_chunks` INT UNSIGNED NOT NULL DEFAULT 0  COMMENT '已入库 chunk 数（进度回写）' AFTER `slicing_config`,
  ADD COLUMN `total_chunks`     INT UNSIGNED NOT NULL DEFAULT 0  COMMENT '总 chunk 数（解析完成后回写）' AFTER `processed_chunks`;
