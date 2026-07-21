-- Migration: section_document 加 is_leaf 列 + 拓扑索引
-- Date: 2026-07-17
-- Author: agentic
-- 说明: 将 section 树拓扑（parent_section_id / is_leaf）从 MongoDB section_data 迁移到
--       MySQL section_document，使骨架树重建可在 MySQL 单次 JOIN 完成（消除 N+1），
--       并支持按 (document_id, parent_section_id) / (document_id, is_leaf) 索引加速子树/叶子查询。
--       parent_section_id 列在原建表脚本中已存在（nullable），本脚本只补 is_leaf 列与两组索引。
-- 影响: 仅 ALTER 现有表；不破坏既有数据。应用层 SQLAlchemy 不会自动 ALTER 已有表，
--       故生产 / 手动环境必须先执行本脚本，再部署依赖 is_leaf 的新代码。
-- 兼容: 老代码不读 is_leaf，迁移前后均可运行；新代码在列缺失时查询会报错，
--       故发版时本脚本需先于新代码合并执行。
-- 回滚:
--   ALTER TABLE `section_document` DROP INDEX `idx_doc_parent`;
--   ALTER TABLE `section_document` DROP INDEX `idx_doc_leaf`;
--   ALTER TABLE `section_document` DROP COLUMN `is_leaf`;

SET NAMES utf8mb4;

-- ----------------------------
-- 1. 新增 is_leaf 列
-- ----------------------------
ALTER TABLE `section_document`
  ADD COLUMN `is_leaf` tinyint(1) DEFAULT NULL
  COMMENT '是否叶子 section：True=挂有 chunk 的结构叶子，False=父 section（rollup）。由 SectionSummaryService 写入。'
  AFTER `document_id`;

-- ----------------------------
-- 2. 拓扑索引：按文档取子树 / 取叶子
-- ----------------------------
CREATE INDEX `idx_doc_parent` ON `section_document` (`document_id`, `parent_section_id`);
CREATE INDEX `idx_doc_leaf`   ON `section_document` (`document_id`, `is_leaf`);
