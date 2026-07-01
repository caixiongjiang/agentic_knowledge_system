-- Migration: 将 chat_session.agent_mode (BOOL) 替换为 mode (VARCHAR)
-- Date: 2026-06-29
-- Author: cursor-agent
-- 说明:
--   交互模式由布尔 `agent_mode`（仅 Agent / RAG 两态）扩展为字符串 `mode`，
--   以支持后续 plan / rag / 其它模式。应用层（ORM / Pydantic / 前端）已全部
--   切换到 `mode` 字段，DB 需同步：
--     - 删除旧列 `agent_mode`
--     - 新增列 `mode VARCHAR(32) NOT NULL DEFAULT 'agent'`
--   开发环境数据可清空，故不做 agent_mode → mode 的数据回填；
--   若需保留历史数据，可先用下面的“可选回填”再删旧列。
-- 影响:
--   仅 chat_session 表。应用层代码已对齐新列，迁移完成后即可生效。
-- 兼容:
--   迁移前：新代码读 `mode` 列会报“未知列”错误 → 必须先执行本脚本再上线代码。
--   迁移后：旧代码读 `agent_mode` 会报错（已无此列）→ 旧代码不可再部署。
--   即：SQL 必须先于代码在生产库执行完成（与 README 约定一致）。
-- 回滚:
--   ALTER TABLE chat_session DROP COLUMN mode;
--   ALTER TABLE chat_session
--     ADD COLUMN agent_mode TINYINT(1) NOT NULL DEFAULT 1
--     COMMENT '是否启用 Agent 工具循环（False 时走 RAG 单轮快路径）'
--     AFTER model;

-- 可选回填（仅当想保留历史会话的 agent_mode 语义时执行；否则跳过）：
-- UPDATE chat_session SET mode = CASE WHEN agent_mode = 1 THEN 'agent' ELSE 'rag' END;

ALTER TABLE chat_session
  DROP COLUMN agent_mode;

ALTER TABLE chat_session
  ADD COLUMN mode VARCHAR(32) NOT NULL DEFAULT 'agent'
  COMMENT '会话交互模式（agent 默认 / plan / rag 等）'
  AFTER model;
