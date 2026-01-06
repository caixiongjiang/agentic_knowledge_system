-- =====================================================
-- 清理所有软删除的记录（deleted = 1）
-- =====================================================
-- 
-- 功能说明：
--   此脚本用于物理删除所有标记为已删除（deleted = 1）的记录
--   执行前请确保已备份重要数据！
-- 
-- 使用方法：
--   方法1: 使用 Python 脚本执行
--     python scripts/mysql/cleanup_deleted_records.py
-- 
--   方法2: 使用 MySQL 客户端直接执行
--     mysql -h 192.168.201.14 -u root -p default < scripts/mysql/cleanup_deleted_records.sql
-- 
--   方法3: 在 MySQL Workbench/Navicat 等工具中手动执行
-- 
-- 注意事项：
--   - 此操作不可逆，请谨慎执行
--   - 建议先使用 SELECT 语句预览要删除的数据
--   - 生产环境建议先备份数据库
-- 
-- =====================================================

-- 使用目标数据库
USE `default`;

-- =====================================================
-- 1. 预览即将删除的记录数（可选）
-- =====================================================

-- 取消下面的注释可以预览每张表将删除的记录数
-- SELECT 'chunk_section_document' AS table_name, COUNT(*) AS deleted_count 
-- FROM chunk_section_document WHERE deleted = 1
-- UNION ALL
-- SELECT 'section_document', COUNT(*) FROM section_document WHERE deleted = 1
-- UNION ALL
-- SELECT 'chunk_meta_info', COUNT(*) FROM chunk_meta_info WHERE deleted = 1
-- UNION ALL
-- SELECT 'section_meta_info', COUNT(*) FROM section_meta_info WHERE deleted = 1
-- UNION ALL
-- SELECT 'chunk_summary', COUNT(*) FROM chunk_summary WHERE deleted = 1
-- UNION ALL
-- SELECT 'chunk_atomic_qa', COUNT(*) FROM chunk_atomic_qa WHERE deleted = 1
-- UNION ALL
-- SELECT 'document_summary', COUNT(*) FROM document_summary WHERE deleted = 1
-- UNION ALL
-- SELECT 'document_meta_info', COUNT(*) FROM document_meta_info WHERE deleted = 1
-- UNION ALL
-- SELECT 'workspace_file_system', COUNT(*) FROM workspace_file_system WHERE deleted = 1;

-- =====================================================
-- 2. 物理删除所有软删除的记录
-- =====================================================

-- Base Layer: 基础数据表
DELETE FROM chunk_section_document WHERE deleted = 1;
DELETE FROM section_document WHERE deleted = 1;
DELETE FROM chunk_meta_info WHERE deleted = 1;
DELETE FROM section_meta_info WHERE deleted = 1;

-- Extract Layer: 提取数据表
DELETE FROM chunk_summary WHERE deleted = 1;
DELETE FROM chunk_atomic_qa WHERE deleted = 1;
DELETE FROM document_summary WHERE deleted = 1;
DELETE FROM document_meta_info WHERE deleted = 1;

-- Business Layer: 业务数据表
DELETE FROM workspace_file_system WHERE deleted = 1;

-- =====================================================
-- 3. 显示清理结果
-- =====================================================

SELECT '清理完成' AS status;
SELECT 
    'chunk_section_document' AS table_name, 
    COUNT(*) AS remaining_deleted 
FROM chunk_section_document WHERE deleted = 1
UNION ALL
SELECT 'section_document', COUNT(*) FROM section_document WHERE deleted = 1
UNION ALL
SELECT 'chunk_meta_info', COUNT(*) FROM chunk_meta_info WHERE deleted = 1
UNION ALL
SELECT 'section_meta_info', COUNT(*) FROM section_meta_info WHERE deleted = 1
UNION ALL
SELECT 'chunk_summary', COUNT(*) FROM chunk_summary WHERE deleted = 1
UNION ALL
SELECT 'chunk_atomic_qa', COUNT(*) FROM chunk_atomic_qa WHERE deleted = 1
UNION ALL
SELECT 'document_summary', COUNT(*) FROM document_summary WHERE deleted = 1
UNION ALL
SELECT 'document_meta_info', COUNT(*) FROM document_meta_info WHERE deleted = 1
UNION ALL
SELECT 'workspace_file_system', COUNT(*) FROM workspace_file_system WHERE deleted = 1;
