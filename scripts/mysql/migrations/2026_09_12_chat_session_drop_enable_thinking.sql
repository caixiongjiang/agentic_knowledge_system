-- Migration: Drop legacy enable_thinking column from chat_session table
-- Date: 2026-09-12
-- Author: caixiongjiang
-- 说明: enable_thinking 已被 thinking_level（7 档枚举）完全取代，
--   应用层不再读写该字段。2026-08-14 的迁移已把旧值回填到 thinking_level，
--   本次直接删除列，避免 INSERT 时 MySQL 因 NOT NULL 无默认值而报错。
-- 影响: chat_session 表；删除后旧代码（仍引用 enable_thinking）将无法读写该列。
-- 兼容: 迁移前——新代码 INSERT 不带 enable_thinking，MySQL 报错；
--   迁移后——新代码正常工作；旧代码引用 enable_thinking 会报 Unknown column。
-- 回滚:
--   ALTER TABLE chat_session
--   ADD COLUMN enable_thinking TINYINT(1) NOT NULL DEFAULT 0
--   COMMENT '兼容：默认不启用思考链' AFTER mode;

ALTER TABLE chat_session
DROP COLUMN enable_thinking;
