/*
 Navicat Premium Dump SQL

 Source Server         : caixj-mysql
 Source Server Type    : MySQL
 Source Server Version : 80406 (8.4.6)
 Source Host           : 192.168.201.14:3306
 Source Schema         : default

 Target Server Type    : MySQL
 Target Server Version : 80406 (8.4.6)
 File Encoding         : 65001

 Date: 09/02/2026 10:09:56
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for element_meta_info
-- ----------------------------
DROP TABLE IF EXISTS `element_meta_info`;
CREATE TABLE `element_meta_info` (
  `element_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '全局唯一ID (UUID格式)',
  `element_index` int NOT NULL COMMENT '元素在文档中的顺序（从0开始计数）',
  `page_index` int DEFAULT NULL COMMENT '页码（从0开始）',
  `element_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '元素类型：text=文本, image=图片, table=表格, discarded=丢弃',
  `page_position` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '在页面中的位置（JSON数组格式：[x, y, width, height]）',
  `text_level` int DEFAULT NULL COMMENT '文本元素层级深度（1=一级，2=二级，仅text类型有效）',
  `bucket_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '对象存储桶名称（如 MinIO bucket）',
  `image_file_path` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片文件路径',
  `image_file_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片文件名',
  `image_file_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片文件类型：png, jpg, svg等',
  `image_file_format` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片格式详细信息',
  `image_file_suffix` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片文件后缀名（含.）',
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
  PRIMARY KEY (`element_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
