# Kafka 基础设施

基于 aiokafka 的异步 Kafka 消息队列基础设施，用于实现事件驱动的索引 Pipeline。

## 目录结构

```
src/db/kafka/
├── __init__.py                 # 包入口
├── README.md                   # 本文档
├── connection/                 # 连接管理
│   ├── __init__.py
│   ├── base.py                # 基础连接接口
│   ├── kafka_manager.py       # Kafka 连接管理器
│   └── factory.py             # 连接工厂（单例）
├── topics.py                   # Topic 定义和配置
└── types.py                    # Kafka 相关类型定义
```

## 安装依赖

```bash
# 添加 aiokafka 依赖
uv add aiokafka
uv add lz4
```

## 配置说明

### 1. 配置文件 (config/config.toml)

已添加完整的 Kafka 配置，包括：
- Broker 配置（地址、安全协议）
- Producer 配置（acks、批处理、压缩等）
- Consumer 配置（Group ID、offset 策略、拉取参数等）
- Topic 配置（分区数、副本因子、保留时间等）
- 批处理配置（各 Writer 的批处理参数）
- 重试和 DLQ 配置

### 2. 环境变量 (env.example)

已添加 Kafka 认证相关环境变量：
- `KAFKA_SASL_USERNAME` - SASL 用户名（如果使用 SASL 认证）
- `KAFKA_SASL_PASSWORD` - SASL 密码
- `KAFKA_SSL_*` - SSL 证书路径（如果使用 SSL）

## 核心组件

### 1. KafkaManager - 连接管理器

负责管理 Kafka Producer、Consumer 和 Admin Client 的生命周期。

```python
from src.db.kafka.connection.factory import get_kafka_manager

# 获取 Manager 实例（单例）
kafka_manager = get_kafka_manager()

# 建立连接
await kafka_manager.connect()

# 获取 Producer
producer = await kafka_manager.get_producer()

# 获取 Consumer
consumer = await kafka_manager.get_consumer(
    topics=["knowledge_base:index:start"],
    group_id="group-file-parser"
)

# 创建 Topics
from src.db.kafka.topics import KafkaTopics
await kafka_manager.create_topics(KafkaTopics.get_topic_configs_dict())

# 断开连接
await kafka_manager.disconnect()
```

### 2. KafkaTopics - Topic 定义

定义系统中所有 Topics 及其配置。

```python
from src.db.kafka.topics import KafkaTopics

# 访问 Topic 名称
topic_name = KafkaTopics.INDEX_START  # "knowledge_base:index:start"

# 获取所有 Topics
all_topics = KafkaTopics.get_all_topics()

# 获取 Topic 配置
topic_configs = KafkaTopics.get_topic_configs()

# 获取配置字典（用于创建 Topics）
config_dict = KafkaTopics.get_topic_configs_dict()

# 获取 DLQ Topic
dlq_topic = KafkaTopics.get_dlq_topic("knowledge_base:index:start")
# 返回: "knowledge_base:index:start.dlq"
```

### 3. MessageKey - 消息 Key 生成器

统一的 Message Key 格式：`{user_id}:{file_id}`

```python
from src.db.kafka.types import MessageKey

# 生成 Key
key = MessageKey.generate("user_123", "file_456")
# 返回: "user_123:file_456"

# 解析 Key
user_id, file_id = MessageKey.parse("user_123:file_456")
```

### 4. ConsumerGroup - Consumer Group 定义

```python
from src.db.kafka.types import ConsumerGroup

# 使用预定义的 Group ID
group_id = ConsumerGroup.FILE_PARSER  # "group-file-parser"

# 添加配置的前缀
full_group_id = ConsumerGroup.with_prefix("file-parser")
# 返回: "aks-file-parser"
```

## Topic 设计

**命名规范**：`{业务模块}.{处理阶段}.{事件类型}`
- 使用点号 `.` 分隔（Kafka 最佳实践）
- 业务模块：knowledge_base, db_write, memory 等
- 事件类型：start（开始）, end（完成）

### 第一层：任务流转 Topics

| Topic 名称 | 分区数 | 说明 |
|-----------|--------|------|
| `knowledge_base.index.start` | 32 | 索引构建开始（文件已在S3） |
| `knowledge_base.parse.end` | 32 | 文件解析完成 |
| `knowledge_base.split.end` | 32 | 文本分割完成（前台进度100%） |
| `knowledge_base.summary.end` | 16 | 文件摘要完成 |
| `knowledge_base.graph.end` | 16 | 知识图谱抽取完成 |
| `knowledge_base.image.end` | 16 | 图片理解完成 |

### 第二层：数据库写入 Topics

| Topic 名称 | 分区数 | 说明 |
|-----------|--------|------|
| `db_write.embedding.start` | 32 | 向量数据写入（原始文本） |
| `db_write.graph.start` | 16 | 图谱数据写入 |
| `db_write.meta.start` | 32 | 元数据写入 |
| `db_write.mongo.start` | 32 | 文档数据写入 |

## Message Key 设计

**核心原则**：所有消息使用统一的 Key 格式 `{user_id}:{file_id}`，保证同一文件的所有消息路由到同一分区，确保数据一致性。

**优势**：
- ✅ 数据一致性：向量、元数据、图谱要么全部成功，要么全部失败
- ✅ 简化设计：无需复杂的分布式事务协调
- ✅ 易于追踪：同一文件的所有消息在同一分区，便于问题排查
- ✅ 批处理优化：性能通过 Writer 层的批处理保证

## 使用示例

### 完整示例：发送和接收消息

```python
import asyncio
from src.db.kafka import get_kafka_manager, KafkaTopics, MessageKey

async def example():
    # 1. 获取 Manager
    kafka_manager = get_kafka_manager()
    
    try:
        # 2. 连接 Kafka
        await kafka_manager.connect()
        
        # 3. 创建所有 Topics
        await kafka_manager.create_topics(KafkaTopics.get_topic_configs_dict())
        
        # 4. 发送消息
        producer = await kafka_manager.get_producer()
        
        # 生成 Message Key
        key = MessageKey.generate("user_123", "file_456")
        
        # 发送消息（需要序列化为 bytes）
        await producer.send(
            KafkaTopics.INDEX_START,
            key=key.encode("utf-8"),
            value=b'{"file_id": "file_456", "user_id": "user_123"}'
        )
        
        print(f"消息已发送到 {KafkaTopics.INDEX_START}")
        
        # 5. 接收消息
        consumer = await kafka_manager.get_consumer(
            topics=[KafkaTopics.INDEX_START],
            group_id="group-file-parser"
        )
        
        async for msg in consumer:
            print(f"收到消息: topic={msg.topic}, partition={msg.partition}, offset={msg.offset}")
            print(f"Key: {msg.key.decode('utf-8')}")
            print(f"Value: {msg.value.decode('utf-8')}")
            
            # 手动提交 offset（enable_auto_commit=False）
            await consumer.commit()
            break
        
    finally:
        # 6. 断开连接
        await kafka_manager.disconnect()

# 运行示例
if __name__ == "__main__":
    asyncio.run(example())
```

## 配置调优

### Producer 优化

```toml
[kafka.producer]
acks = "all"              # 等待所有副本确认（最高可靠性，代码转换为 -1）
batch_size = 65536        # 64KB 批处理（映射到 max_batch_size）
linger_ms = 5             # 5ms 批处理延迟
compression_type = "lz4"  # LZ4 压缩（速度快）
```

**aiokafka 参数映射说明**：
- `acks="all"` → `acks=-1`（aiokafka 要求整数）
- `batch_size` → `max_batch_size`（aiokafka 参数名）
- 重试机制：aiokafka 内置自动重试，无需配置

### Consumer 优化

```toml
[kafka.consumer]
max_poll_records = 500    # 单次拉取最多 500 条
fetch_min_bytes = 1024    # 最小拉取 1KB
fetch_max_wait_ms = 500   # 最多等待 500ms
```

### Topic 优化

```toml
[kafka.topics]
replication_factor = 3         # 3 副本
min_insync_replicas = 2        # 至少 2 个副本同步
retention_ms = 604800000       # 7 天保留
```

## 注意事项

1. **连接管理**：使用单例模式的 `get_kafka_manager()`，避免重复创建连接
2. **手动提交**：默认 `enable_auto_commit=False`，需要手动调用 `await consumer.commit()`
3. **消息序列化**：Kafka 只接受 bytes，需要手动序列化/反序列化
4. **异步操作**：所有操作都是异步的，必须使用 `await`
5. **资源清理**：程序退出前务必调用 `await kafka_manager.disconnect()`

## 下一步

第一批基础设施已完成，接下来需要开发：
1. Producer 封装（src/db/kafka/producer.py）
2. Consumer 封装（src/db/kafka/consumer.py）
3. 消息模型定义（src/types/messages/）
4. 幂等性和重试机制（src/db/kafka/deduplication.py, retry_manager.py）

## 测试

创建测试文件验证 Kafka 基础设施：

```bash
# 运行测试（需要先启动 Kafka）
uv run python test/db/kafka/test_kafka_manager.py
```
