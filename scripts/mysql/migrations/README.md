# MySQL 迁移脚本

本项目未引入 Alembic；所有 schema 演进通过本目录下的版本化 SQL 脚本管理。

## 命名约定

```
YYYY_MM_DD_<table>_<action>.sql
```

例：`2026_05_19_chat_session_add_model.sql`

## 使用方式

每次发版前由运维 / 开发同学按时间顺序执行未上线的脚本：

```bash
mysql -h <host> -P <port> -u <user> -p <database> \
    < scripts/mysql/migrations/2026_05_19_chat_session_add_model.sql
```

或通过 Navicat / DBeaver 等图形工具直接打开执行。

## 脚本要求

每个脚本头部必须包含：

- `Migration`: 一句话描述
- `Date`: 计划执行日期
- `Author`: 提交人
- `说明`: 为什么需要这个变更
- `影响`: 涉及哪些表 / 是否影响其它代码
- `兼容`: 老代码 / 新代码在本次迁移前后是否都能跑
- `回滚`: 一段可执行的回滚 SQL（建议都写）

## ⚠️ 生产环境注意

- 大表 ADD COLUMN 在 MySQL 8.x 多数情况下是 INSTANT 操作，但仍建议低峰执行；
- 一旦应用层代码合并到主分支，SQL 必须先于代码在生产库执行完成。
