# FileParserService 使用指南

## 概述

FileParserService 是文件解析服务的核心组件,负责协调文件下载和解析流程。

## 架构设计

```
FileParserService (Service 层)
  ↓
1. 从对象存储下载文件
  ↓
2. 保存到临时文件
  ↓
3. 调用 FileParser.parse_and_store()
  ↓
   FileParser (Parser 层 - 路由器)
     ↓
   根据文件扩展名路由到具体 Parser
     ↓
   PDFParser / WordParser / ExcelParser ...
     ↓
   返回解析结果
  ↓
4. 清理临时文件
  ↓
5. 返回标准化的 ParseResult
```

## 核心功能

1. **文件下载**: 从对象存储下载文件(支持 MinIO/OSS/GCS/S3)
2. **临时文件管理**: 创建和清理临时文件
3. **调用 FileParser**: 委托给 FileParser 进行解析和存储
4. **结果标准化**: 将 FileParser 的结果转换为标准 ParseResult 模型
5. **错误处理**: 完善的异常处理和资源清理

## 支持的文件类型

| 文件类型 | MIME Type | 状态 |
|---------|----------|------|
| PDF | `application/pdf` | ✅ 已支持 |
| Word (docx) | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 🚧 待实现 |
| Word (doc) | `application/msword` | 🚧 待实现 |
| Excel (xlsx) | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | 🚧 待实现 |
| Excel (xls) | `application/vnd.ms-excel` | 🚧 待实现 |
| PowerPoint (pptx) | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | 🚧 待实现 |
| PowerPoint (ppt) | `application/vnd.ms-powerpoint` | 🚧 待实现 |
| Markdown | `text/markdown` | 🚧 待实现 |
| Text | `text/plain` | 🚧 待实现 |

## 使用方式

### 基本用法

```python
from src.db.storage.manager import StorageManager
from src.service.knowledge.components import FileParserService
from src.db.mysql.connection import get_mysql_session

# 获取数据库会话
session = get_mysql_session()

try:
    # 使用异步上下文管理器确保资源正确释放
    async with StorageManager() as storage:
        # 创建服务实例
        service = FileParserService(
            storage_manager=storage,
            mysql_session=session
        )
        
        # 解析文件
        result = await service.parse_file(
            user_id="user_123",
            file_id="file_456",
            filename="document.pdf",
            storage_path="knowledge-files/users/user_123/sessions/session_789/raw/file_456/document.pdf",
            knowledge_base_id="kb_001",
            knowledge_base_name="我的知识库",
            creator="user_123",
            store_images=True  # 是否存储图片到对象存储
        )
        
        # 检查解析结果
        if result.is_success():
            print(f"解析成功: {result.get_summary()}")
            print(f"- 总页数: {result.total_pages}")
            print(f"- 状态: {result.status}")
        else:
            print(f"解析失败: {result.error_message}")
finally:
    session.close()
```

### 自定义 Parser

```python
from src.index.common_file_extract.parser.pdf_parser import PDFParser
from src.client.mineru import Mineru2Client

# 创建自定义 Mineru 客户端
mineru_client = Mineru2Client(
    api_url="http://your-mineru-server:8080",
    timeout=600
)

# 创建自定义 PDF Parser
pdf_parser = PDFParser(
    mineru_client=mineru_client,
    max_pages_per_request=10,  # 单次请求最大页数
    max_concurrent_requests=3   # 最大并发请求数
)

# 使用自定义 Parser
async with StorageManager() as storage:
    service = FileParserService(
        storage_manager=storage,
        pdf_parser=pdf_parser
    )
    
    result = await service.parse_file(...)
```

### 自定义 Repository

```python
from src.db.mysql.repositories.base.element_meta_info_repo import ElementMetaInfoRepository
from src.db.mongodb.repositories.element_data_repository import ElementDataRepository

# 创建自定义 Repository
element_meta_repo = ElementMetaInfoRepository()
element_data_repo = ElementDataRepository()

async with StorageManager() as storage:
    service = FileParserService(
        storage_manager=storage,
        element_meta_repo=element_meta_repo,
        element_data_repo=element_data_repo
    )
    
    result = await service.parse_file(...)
```

## 数据流转

```
FileParserService:
1. 从对象存储下载文件
   ↓
2. 保存到临时文件
   ↓
3. 调用 FileParser.parse_and_store(临时文件路径)
   ↓

FileParser:
4. 检测文件类型(根据扩展名)
   ↓
5. 路由到对应 Parser (PDFParser/WordParser/...)
   ↓
6. Parser 解析文件
   ↓
7. 存储到数据库:
   - MySQL (element_meta_info): 元信息
   - MongoDB (element_data): 内容数据
   - 可选: MinIO (图片文件)
   ↓
8. 返回解析统计信息

FileParserService:
9. 清理临时文件
   ↓
10. 转换为标准 ParseResult
   ↓
11. 返回 ParseResult
```

## 错误处理

```python
try:
    result = await service.parse_file(...)
    
    if result.status == ParseStatus.SUCCESS:
        print("解析成功")
    elif result.status == ParseStatus.PARTIAL_SUCCESS:
        print(f"部分成功: {result.error_message}")
    elif result.status == ParseStatus.FAILED:
        print(f"解析失败: {result.error_message}")
        
except ValueError as e:
    # 不支持的文件类型
    print(f"文件类型错误: {e}")
    
except Exception as e:
    # 其他错误
    print(f"解析过程出错: {e}")
```

## ParseResult 结构

```python
result = ParseResult(
    user_id="user_123",
    file_id="file_456",
    filename="document.pdf",
    status=ParseStatus.SUCCESS,
    
    # 统一的元素列表(文本、图片、表格)
    elements=[
        ElementInfo(
            element_id="elem_001",
            element_index=0,
            element_type=ElementType.TEXT,
            text="文本内容",
            page_index=0
        ),
        ElementInfo(
            element_id="elem_002",
            element_index=1,
            element_type=ElementType.IMAGE,
            image_file_path="path/to/image.png",
            page_index=1
        ),
        # ...
    ],
    
    # 文档元数据
    document_metadata={"author": "张三", "title": "测试文档"},
    parse_tool="mineru",
    parse_quality=0.95,
    document_language="zh",
    total_pages=10,
    total_chars=5000,
    
    # 存储路径
    storage_path="bucket/path/to/file.pdf",
    knowledge_base_id="kb_001",
    knowledge_base_name="我的知识库"
)

# 使用便捷方法
print(result.get_summary())         # 获取摘要
print(result.get_element_stats())   # 获取元素统计
print(result.text_elements)         # 获取所有文本元素
print(result.image_elements)        # 获取所有图片元素
print(result.table_elements)        # 获取所有表格元素
```

## 存储数据获取

```python
# 获取 MySQL 数据(用于 element_meta_info 表)
mysql_data = result.get_mysql_data()
# [
#   {
#     "element_id": "elem_001",
#     "element_index": 0,
#     "element_type": "text",
#     "page_index": 0,
#     "text_level": 1,
#     ...
#   },
#   ...
# ]

# 获取 MongoDB 数据(用于 element_data 集合)
mongodb_data = result.get_mongodb_data()
# [
#   {
#     "_id": "elem_001",
#     "type": "text",
#     "content": {"text": "..."}
#   },
#   ...
# ]
```

## 配置说明

在 `config.toml` 中配置:

```toml
[storage]
type = "minio"  # 存储类型: minio/oss/gcs/s3

[minio]
endpoint = "localhost:9000"
default_bucket = "knowledge-files"
secure = false
region = "us-east-1"

[mineru]
api_url = "http://localhost:8080"
timeout = 300
max_pages_per_request = 4
max_concurrent_requests = 5
```

## 最佳实践

### 1. 使用异步上下文管理器

```python
# ✅ 推荐: 自动管理资源
async with StorageManager() as storage:
    service = FileParserService(storage_manager=storage)
    result = await service.parse_file(...)

# ❌ 不推荐: 需要手动清理
storage = StorageManager()
service = FileParserService(storage_manager=storage)
result = await service.parse_file(...)
await storage.close()  # 容易忘记
```

### 2. 检查解析状态

```python
result = await service.parse_file(...)

# ✅ 推荐: 使用便捷方法
if result.is_success():
    process_result(result)

# ❌ 不推荐: 直接比较枚举
if result.status == ParseStatus.SUCCESS:
    process_result(result)
```

### 3. 错误处理

```python
# ✅ 推荐: 捕获具体异常
try:
    result = await service.parse_file(...)
except ValueError as e:
    handle_unsupported_type(e)
except Exception as e:
    handle_general_error(e)

# ❌ 不推荐: 捕获所有异常
try:
    result = await service.parse_file(...)
except:
    pass
```

### 4. 使用依赖注入进行测试

```python
from unittest.mock import AsyncMock

# ✅ 推荐: 注入 Mock 对象
mock_storage = AsyncMock()
mock_parser = AsyncMock()

service = FileParserService(
    storage_manager=mock_storage,
    pdf_parser=mock_parser
)

# 易于测试
```

## 性能优化

### 1. 并发处理多个文件

```python
async def parse_multiple_files(file_list):
    async with StorageManager() as storage:
        service = FileParserService(storage_manager=storage)
        
        tasks = [
            service.parse_file(
                user_id=f["user_id"],
                file_id=f["file_id"],
                filename=f["filename"],
                storage_path=f["storage_path"],
                mime_type=f["mime_type"]
            )
            for f in file_list
        ]
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

### 2. 批量存储优化

目前 MySQL 存储尚未实现批量插入,MongoDB 已支持批量 upsert。

```python
# MongoDB 自动使用批量操作
await element_data_repo.bulk_upsert_elements(elements_data)
```

## 注意事项

1. **临时文件**: 当前 PDFParser 需要文件路径,服务会创建临时文件并自动清理
2. **MySQL 批量插入**: 目前待实现,单条插入性能较低
3. **图片上传**: 仅在提供 `session_id` 时才会上传图片到 MinIO
4. **资源清理**: 必须使用异步上下文管理器确保资源正确释放

## 测试

运行单元测试:

```bash
cd /path/to/project
PYTHONPATH=$(pwd) uv run python test/service/knowledge/test_file_parser_service.py
```

## 扩展

### 添加新的 Parser

```python
# 1. 实现 Parser
class WordParser:
    async def parse(self, file_bytes: bytes, filename: str) -> Dict:
        # 解析逻辑
        return {"elements": [...], ...}

# 2. 在 FileParserService 中添加路由
def _get_parser(self, mime_type: str):
    file_type = self.SUPPORTED_MIME_TYPES.get(mime_type)
    
    if file_type == "pdf":
        return self.pdf_parser
    elif file_type == "docx":
        return self.word_parser  # 新增
    # ...
```

## 相关文档

- [FileParser Worker 开发文档](../../../cursor_docs/kafka_workers/file_parser_worker_development.md)
- [ParseResult 数据模型](../../../src/types/models/parse_result.py)
- [Storage 层文档](../../../src/db/storage/README.md)
