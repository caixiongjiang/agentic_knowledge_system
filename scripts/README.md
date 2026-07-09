# Scripts 工具脚本目录

本目录包含项目的各种启动和管理脚本。

## 📂 目录结构

```
scripts/
├── start_all_workers.py      # 🚀 Kafka Workers 统一启动脚本（推荐）
├── README_WORKERS.md          # Worker 启动脚本详细文档
├── milvus/                    # Milvus 数据库管理脚本
│   ├── export_milvus_schema.py
│   └── read_milvus_db.py
├── mongodb/                   # MongoDB 数据库管理脚本
│   ├── cleanup_deleted_records.js
│   └── cleanup_deleted_records.py
└── mysql/                     # MySQL 数据库管理脚本
    ├── cleanup_deleted_records.py
    └── cleanup_deleted_records.sql
```

## 🚀 核心脚本

### 1. Kafka Workers 统一启动脚本

**文件**: `start_all_workers.py`

**用途**: 统一管理和启动所有 Kafka Workers

**功能**:
- ✅ 启动所有 Workers 或指定的 Workers
- ✅ 并发管理多个 Worker 实例
- ✅ 统一的日志和错误处理
- ✅ 优雅的关闭机制

**使用方法**:

```bash
# 查看所有可用的 Workers（10个）
uv run python scripts/start_all_workers.py --list

# 启动所有 Workers（10个）
uv run python scripts/start_all_workers.py

# 启动所有任务流转 Workers（6个）
uv run python scripts/start_all_workers.py --workers file_parser,text_splitter,section_summary,file_summary,kg_extractor,text_analyzer

# 启动所有 DB Writers（4个）
uv run python scripts/start_all_workers.py --workers embedding_milvus_writer,neo4j_writer,mysql_writer,mongo_writer

# 启动指定的 Workers
uv run python scripts/start_all_workers.py --workers file_parser,text_splitter,embedding_milvus_writer

# 停止（按 Ctrl+C）
```

**Workers 总数**: 10 个（6 个任务流转 + 4 个数据库写入）

**第一层：任务流转 Workers**:
- `file_parser` - 文件解析
- `text_splitter` - 文本分割
- `section_summary` - Section 摘要
- `file_summary` - 文件摘要
- `kg_extractor` - 知识图谱抽取
- `text_analyzer` - 文本分析 / Atomic QA

**第二层：数据库写入 Writers**:
- `embedding_milvus_writer` - 向量写入（批量 Embedding + Milvus）
- `neo4j_writer` - 图谱写入（批量写入 Neo4j）
- `mysql_writer` - 元数据写入（批量写入 MySQL）
- `mongo_writer` - 文档写入（批量写入 MongoDB）

## 🗄️ 数据库管理脚本

### 2. Milvus 数据库管理

#### 导出 Milvus Schema
```bash
uv run python scripts/milvus/export_milvus_schema.py
```

功能：导出所有 Milvus Collections 的 Schema 定义

#### 读取 Milvus 数据
```bash
uv run python scripts/milvus/read_milvus_db.py
```

功能：查询和浏览 Milvus 中的向量数据

### 3. MongoDB 数据库管理

#### 清理已删除记录（Python）
```bash
uv run python scripts/mongodb/cleanup_deleted_records.py
```

#### 清理已删除记录（JavaScript）
```bash
mongo < scripts/mongodb/cleanup_deleted_records.js
```

功能：物理删除 MongoDB 中标记为已删除的记录（软删除清理）

### 4. MySQL 数据库管理

#### 清理已删除记录（Python）
```bash
uv run python scripts/mysql/cleanup_deleted_records.py
```

#### 清理已删除记录（SQL）
```bash
mysql -u user -p database < scripts/mysql/cleanup_deleted_records.sql
```

功能：物理删除 MySQL 中标记为已删除的记录（软删除清理）

## 💡 数据插入方式说明

系统支持两种数据插入方式，可以灵活选择：

### 方式1：直接插入（同步）
```python
# 在 Service 层直接调用 Repository
await element_meta_info_repo.batch_create(result.get_mysql_data())
await element_data_repository.bulk_upsert_elements(result.get_mongodb_data())
```

**优点**: 快速、简单、数据立即持久化  
**适用**: 元数据、小数据量

### 方式2：消息插入（异步）
```python
# 发送消息到 DB Writers
await producer.send(
    topic=KafkaTopics.DB_WRITE_META,
    message=MetaWriteMessage(data=result.get_mysql_data())
)
```

**优点**: 异步、批量优化、高吞吐  
**适用**: 向量数据、大数据量

### 混合模式（推荐）
- FileParser: 直接写入元数据和文档数据（快速持久化）
- TextSplitter: 发送消息到 `embedding_milvus_writer`（批量向量化）
- KGExtractor: 发送消息到 `neo4j_writer`（批量图谱写入）

**关键**: Worker 启动脚本和数据插入方式是解耦的，修改插入方式只需改 Service 层代码。

## 📝 脚本开发规范

如果需要添加新的脚本，请遵循以下规范：

1. **文件头注释**: 包含作者、日期、功能描述
2. **参数解析**: 使用 `argparse` 提供友好的命令行接口
3. **日志记录**: 使用 `loguru` 记录详细的运行日志
4. **错误处理**: 提供清晰的错误信息和恢复建议
5. **文档说明**: 在本 README 中添加使用说明

## 🔧 常见问题

### Q: Worker 启动失败？
A: 检查以下几点：
1. Kafka 是否正常运行: `telnet 192.168.201.14 9092`
2. 配置文件是否正确: `config/config.toml`
3. 依赖服务是否启动（MinIO、MinerU、LLM API）

### Q: 如何查看 Worker 日志？
A: Worker 日志会实时输出到控制台，包含颜色标记：
- ✓ 绿色 = 成功
- ⚠ 黄色 = 警告
- ❌ 红色 = 错误
- ℹ 蓝色 = 信息

### Q: 如何停止所有 Workers？
A: 按 `Ctrl+C` 即可优雅地停止所有 Workers，它们会自动清理资源。

### Q: 可以同时启动多个相同的 Worker 吗？
A: 可以！在不同的终端运行相同的启动命令，Kafka 会自动分配分区，实现负载均衡。

## 📚 相关文档

- [FileParser Worker 开发文档](../cursor_docs/kafka_workers/file_parser_worker_development.md)
- [架构设计文档](../docs/通用文件和工作空间文件知识库/通用文件索引高性能架构设计.md)
- [Kafka Topic 设计](../src/db/kafka/topics.py)

## 🤝 贡献

如果需要添加新的脚本或改进现有脚本，请：
1. 创建功能分支
2. 添加脚本和相应的文档
3. 更新本 README
4. 提交 Pull Request

---

**最后更新**: 2026-02-05  
**维护者**: JarsonCai
