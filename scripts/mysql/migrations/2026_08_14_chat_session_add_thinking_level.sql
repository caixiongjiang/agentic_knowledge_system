-- Migration: Add thinking_level column to chat_session table
-- Date: 2026-08-14
-- Description: Replaces the boolean enable_thinking flag with a unified thinking_level
--   (pi standard 7 levels: off/minimal/low/medium/high/xhigh/max). enable_thinking
--   is kept as a legacy column; NULL thinking_level on old rows is downgraded to
--   enable_thinking at read time (True->medium / False->off).

ALTER TABLE chat_session
ADD COLUMN thinking_level VARCHAR(16) NULL DEFAULT NULL
COMMENT '思考强度档位（off/minimal/low/medium/high/xhigh/max）；NULL=旧会话按 enable_thinking 降级'
AFTER enable_thinking;

-- 回填：把已有会话的 thinking_level 按 enable_thinking 翻译一遍，避免老会话
-- 一直走降级分支。新会话直接由应用层写入。
UPDATE chat_session
SET thinking_level = CASE WHEN enable_thinking = 1 THEN 'medium' ELSE 'off' END
WHERE thinking_level IS NULL;
