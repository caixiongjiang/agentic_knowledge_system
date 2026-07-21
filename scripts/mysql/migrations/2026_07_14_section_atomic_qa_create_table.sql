-- Migration: Create section_atomic_qa table
-- Date: 2026-07-14
-- Author: agentic
-- 说明: TextAnalyzer v1.1 section 级 atomic_qa 抽取落地。
--       QA 正文（question/answer/source_chunk_ids/relevance）存 MongoDB section_data.atomic_qa，
--       QA 向量存 Milvus atomic_qa_store，本表仅做 qa ↔ section ↔ document 关联，
--       供按 section/document 批量查询与级联删除。
-- 取代: v1.0 chunk_atomic_qa 表（chunk 级抽取遗留，无生产数据，已随代码删除，本脚本不含其 drop）。
-- 影响: 新增表 section_atomic_qa；不影响现有表。应用层 SQLAlchemy 会随 init_db 自动建表，
--       本脚本供生产 / 手动执行使用（CREATE IF NOT EXISTS，幂等）。
-- 兼容: 老代码不引用本表，迁移前后均可运行；新代码在表缺失时会因 MySQLWriter 路由失败而报错，
--       故发版时本脚本需先于新代码合并执行。
-- 回滚:
--   DROP TABLE IF EXISTS `section_atomic_qa`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for section_atomic_qa
-- ----------------------------
CREATE TABLE IF NOT EXISTS `section_atomic_qa` (
  `qa_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'AtomicQA 唯一标识符（Milvus atomic_qa_store 主键，UUID 格式）',
  `section_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属 Section ID（与 split / section_summary 阶段一致）',
  `document_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属 Document ID（document-{uuid}）',
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
  PRIMARY KEY (`qa_id`),
  KEY `idx_section_atomic_qa_section_id` (`section_id`),
  KEY `idx_section_atomic_qa_document_id` (`document_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
