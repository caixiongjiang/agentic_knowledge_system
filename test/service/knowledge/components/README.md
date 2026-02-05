# FileParser 组件测试说明

## 测试文件

- `test_file_parser_service_e2e.py` - 端到端测试（支持 Service 和 Kafka 两种模式）
- `start_file_parser_worker.py` - Kafka Worker 启动脚本

## 快速开始

### 1. Service 模式（推荐，快速测试）

直接运行测试，无需启动额外服务：

```bash
uv run python test/service/knowledge/components/test_file_parser_service_e2e.py
```

**测试内容：**
- ✅ PDF 文件上传到 MinIO
- ✅ 调用 MinerU 解析文件
- ✅ 解析结果验证（文本、图片、表格）
- ✅ MySQL 消息数据验证
- ✅ MongoDB 消息数据验证
- ✅ 图片上传到 MinIO 验证

### 2. Kafka 模式（完整流程测试）

测试完整的 Kafka 消息流程：

**步骤：**

```bash
# 终端 1: 启动 Worker
uv run python test/service/knowledge/components/start_file_parser_worker.py

# 终端 2: 运行测试（带 --kafka 参数）
uv run python test/service/knowledge/components/test_file_parser_service_e2e.py --kafka
```

**测试内容：**
- ✅ Service 模式的所有测试
- ✅ Kafka 消息生产和消费
- ✅ 下游 Topic 消息验证：
  - `db_write.meta.start` (MySQL 写入消息)
  - `db_write.mongo.start` (MongoDB 写入消息)
  - `knowledge_base.parse.end` (解析完成消息)

## 测试流程

```
1. 上传测试文件 (TP-LoRA.pdf) 到 MinIO
   ↓
2. 发送解析请求
   ├── Service 模式: 直接调用 FileParserService
   └── Kafka 模式: 发送消息到 knowledge_base.index.start
   ↓
3. MinerU 解析文件 (提取文本、图片、表格)
   ↓
4. 验证解析结果
   ├── 文本内容数量
   ├── 图片提取和上传
   └── 表格提取和 Markdown 转换
   ↓
5. 验证数据存储
   ├── MySQL: 消息列表 (按会话组织)
   └── MongoDB: 消息详细内容 (包含富文本)
   ↓
6. [Kafka 模式] 验证下游消息
   ├── db_write.meta.start (数据库写入)
   └── knowledge_base.parse.end (解析完成通知)
   ↓
7. 清理测试数据 (可选: --cleanup)
```

## 命令行参数

```bash
# 显示帮助
uv run python test/service/knowledge/components/test_file_parser_service_e2e.py --help

# 常用参数
--kafka          # 启用 Kafka 模式
--cleanup        # 测试后清理 MinIO 文件
--timeout 300    # 设置 Kafka 消费超时（秒）
```

## 前置条件

确保以下服务正常运行：

| 服务 | 地址 | 用途 |
|------|------|------|
| Kafka | 192.168.201.14:9092 | 消息队列（Kafka 模式必需） |
| MinIO | 192.168.201.14:9000 | 对象存储 |
| MinerU | http://192.168.201.14:18000 | PDF 解析服务 |
| MySQL | 192.168.201.14:3307 | 消息元数据存储 |
| MongoDB | 192.168.201.14:27017 | 消息内容存储 |

## 测试数据

- **测试文件**: `tmp_files/pdf/TP-LoRA.pdf`
- **默认参数**:
  - `user_id`: test_user_001
  - `session_id`: test_session_001
  - `file_id`: test_file_001
  - `knowledge_base_id`: kb_001
- **Kafka 模式**: 使用随机 UUID 避免冲突

## 故障排查

### 1. Service 模式失败

```bash
# 检查 MinIO 连接
curl http://192.168.201.14:9000

# 检查 MinerU 服务
curl http://192.168.201.14:18000/health
```

### 2. Kafka 模式超时

```bash
# 确认 Worker 正在运行
# 检查 Kafka 是否正常
kafka-topics.sh --list --bootstrap-server 192.168.201.14:9092

# 查看 Topic 消息
kafka-console-consumer.sh --topic knowledge_base.index.start \
  --bootstrap-server 192.168.201.14:9092 --from-beginning
```

### 3. 解析失败

```bash
# 检查日志输出
# MinerU 解析错误通常会在日志中显示详细堆栈

# 验证测试文件存在
ls -lh tmp_files/pdf/TP-LoRA.pdf
```

## 预期输出

### 成功运行示例

```
[INFO] ========== FileParser Service E2E Test ==========
[INFO] 测试模式: Service
[INFO] 步骤 1/8: 上传测试文件到 MinIO
[SUCCESS] ✅ 文件上传成功: test_files/test_user_001/test_file_001.pdf
[INFO] 步骤 2/8: 解析文件
[SUCCESS] ✅ 解析成功，耗时: 12.34s
[INFO] 步骤 3/8: 验证解析结果
[SUCCESS] ✅ 文本块数量: 45
[SUCCESS] ✅ 图片数量: 8
[INFO] 步骤 4/8: 验证 MySQL 消息
[SUCCESS] ✅ MySQL 消息数: 53
[INFO] 步骤 5/8: 验证 MongoDB 消息
[SUCCESS] ✅ MongoDB 消息数: 53
[INFO] 步骤 6/8: 验证图片上传
[SUCCESS] ✅ 所有图片已上传到 MinIO
[SUCCESS] ========== 所有测试通过 ✅ ==========
```

## 开发说明

- 测试默认**不清理**文件，方便在 MinIO 中查看结果
- 使用 `--cleanup` 参数可在测试后自动清理
- Kafka 模式使用随机 ID，支持并发测试
- 测试失败会输出详细的错误信息和堆栈跟踪
