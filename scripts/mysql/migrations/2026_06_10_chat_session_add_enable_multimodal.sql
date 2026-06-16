-- Migration: Add enable_multimodal column to chat_session table
-- Date: 2026-06-10
-- Description: Adds support for multimodal image reading capability toggle per session

ALTER TABLE chat_session
ADD COLUMN enable_multimodal TINYINT(1) NOT NULL DEFAULT 0
COMMENT '是否启用多模态读图（仅支持多模态的模型生效）'
AFTER enable_thinking;
