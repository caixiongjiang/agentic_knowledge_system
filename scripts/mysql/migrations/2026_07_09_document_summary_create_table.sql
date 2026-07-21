-- Migration: Create document_summary table
-- Date: 2026-07-09
-- Author: agentic
-- 说明: FileSummary 阶段落地的关联表（与 section_summary 对齐）。
--       摘要正文存 MongoDB document_data.summary（结构化子文档），
--       摘要向量存 Milvus file_summary_store（role=document_summary），
--       本表仅做 document ↔ summary_id 关联，供按文档批量查询/级联删除。
-- 影响: 新增表 document_summary；不影响现有表。应用层 SQLAlchemy 会随 init_db 自动建表，
--       本脚本供生产 / 手动执行使用（CREATE IF NOT EXISTS，幂等）。
-- 兼容: 老代码不引用本表，迁移前后均可运行；新代码在表缺失时会因 MySQLWriter 路由失败而报错，
--       故发版时本脚本需先于新代码合并执行。
-- 回滚:
--   DROP TABLE IF EXISTS `document_summary`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for document_summary
-- ----------------------------
CREATE TABLE IF NOT EXISTS `document_summary` (
  `document_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Document 唯一标识符（document-{uuid}）',
  `summary_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '关联的 Summary ID（Milvus file_summary_store 主键）',
  `knowledge_base_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '知识库ID',
  `knowledge_base_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '知识库名称',
  `parent_knowledge_base_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父知识库ID',
  `parent_knowledge_base_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父知识库名称',
  `knowledge_type` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '知识类型',
  `status` int NOT NULL DEFAULT '0' COMMENT '状态标识：0=正常，其他值根据业务定义',
  `creator` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'system' COMMENT '创建者用户名或ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updater` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'system' COMMENT '最后更新者用户名或ID',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `deleted` int NOT NULL DEFAULT '0' COMMENT '软删除标记：0=未删除，1=已删除',
  PRIMARY KEY (`document_id`),
  KEY `idx_summary_id` (`summary_id`),
  KEY `idx_knowledge_base_id` (`knowledge_base_id`),
  KEY `idx_deleted_create_time` (`deleted`, `create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Document-Summary 关联表（FileSummary 阶段产出）';

SET FOREIGN_KEY_CHECKS = 1;
