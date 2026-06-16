-- =============================================================
-- Migration: chat_session 增加 model 列
-- Date    : 2026-05-19
-- Author  : caixiongjiang
-- 说明    :
--   前端"知识库对话"接入 LiteLLM 模型清单后，用户可以在 UI 直接挑模型
--   字符串（如 'openai/gpt-4o-mini'），需要在 chat_session 上持久化用户
--   最近一次的选择，与 model_preset 字段并存（后台 agent 仍走 preset）。
--
-- 影响    : 仅 chat_session 表加列；不影响其他表。
-- 兼容    : 老代码读不到该字段也能正常跑（NULL ↔ 走 model_preset）。
-- 回滚    : ALTER TABLE chat_session DROP COLUMN `model`;
-- =============================================================

ALTER TABLE `chat_session`
  ADD COLUMN `model` VARCHAR(255) NULL DEFAULT NULL
  COMMENT 'LiteLLM 模型字符串（如 openai/gpt-4o-mini），NULL 表示由 model_preset 决定'
  AFTER `model_preset`;
