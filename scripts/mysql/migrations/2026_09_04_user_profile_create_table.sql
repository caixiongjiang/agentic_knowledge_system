-- Migration: Create user_profile table
-- Date: 2026-09-04
-- Author: agentic
-- 说明: 创建用户资料表 user_profile，用于存储用户个性化信息（昵称、头像 MinIO 路径与访问地址、个人简介等）。
--       支持基于 user_id 的头像与资料持久化，未上传头像时前端根据 user_id 确定性生成 Identicon。
-- 影响: 新增表 user_profile；不影响现有业务表。
-- 兼容: 老系统无此表，迁移后由应用层提供默认降级处理。
-- 回滚:
--   DROP TABLE IF EXISTS `user_profile`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for user_profile
-- ----------------------------
CREATE TABLE IF NOT EXISTS `user_profile` (
  `user_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户唯一标识符（UUID 或 Logto sub）',
  `nickname` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户昵称 / 显示名称',
  `avatar_url` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '自定义头像对外访问 URL',
  `avatar_storage_path` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '头像在 MinIO 上的存储路径 (bucket/object_path)',
  `bio` text COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户个人简介 / 签名',
  `custom_data` json DEFAULT NULL COMMENT '扩展自定义 JSON 配置',
  `status` int NOT NULL DEFAULT 0 COMMENT '状态标识：0=正常，其他值根据业务定义',
  `creator` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '创建者用户名或ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updater` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '最后更新者用户名或ID',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `deleted` int NOT NULL DEFAULT 0 COMMENT '软删除标记：0=未删除，1=已删除',
  PRIMARY KEY (`user_id`),
  KEY `idx_user_profile_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户个人资料及头像信息表';

SET FOREIGN_KEY_CHECKS = 1;
