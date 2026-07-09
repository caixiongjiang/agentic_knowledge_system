-- Migration: Create section_summary table
-- Date: 2026-07-02
-- Author: agentic
-- 说明: 新增 Section 级摘要抽取阶段（SectionSummaryWorker）。
--       每个 section 生成一条摘要，正文存 MongoDB section_data.summary，
--       向量存 Milvus summary collection（role=section_summary），
--       本表仅做 section ↔ summary_id ↔ document 关联，供按文档批量查询/级联删除。
-- 影响: 新增表 section_summary；不影响现有表。应用层 SQLAlchemy 会随 init_db 自动建表，
--       本脚本供生产 / 手动执行使用（CREATE IF NOT EXISTS，幂等）。
-- 兼容: 老代码不引用本表，迁移前后均可运行；新代码在表缺失时会因 MySQLWriter 路由失败而报错，
--       故发版时本脚本需先于新代码合并执行。
-- 回滚:
--   DROP TABLE IF EXISTS `section_summary`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for section_summary
-- ----------------------------
CREATE TABLE IF NOT EXISTS `section_summary` (
  `section_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Section 唯一标识符（与 split 阶段一致，UUID 格式）',
  `document_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属 Document ID（document-{uuid}）',
  `summary_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '关联的 Summary ID（Milvus summary collection 主键）',
  `status` int NOT NULL COMMENT '状态标识：0=正常，其他值根据业务定义',
  `creator` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '创建者用户名或ID',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `updater` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '最后更新者用户名或ID',
  `update_time` datetime NOT NULL COMMENT '最后更新时间',
  `deleted` int NOT NULL COMMENT '软删除标记：0=未删除，1=已删除',
  `knowledge_base_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '知识库ID，标识数据所属的知识库',
  `knowledge_base_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '知识库名称，便于查询和展示',
  `parent_knowledge_base_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父知识库ID，用于表示知识库之间的层次关系',
  `parent_knowledge_base_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父知识库名称，便于查询和展示',
  `knowledge_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '知识库类型：common_file=普通文件',
  PRIMARY KEY (`section_id`),
  KEY `idx_section_summary_document_id` (`document_id`),
  KEY `idx_section_summary_summary_id` (`summary_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
