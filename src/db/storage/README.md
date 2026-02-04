# 对象存储管理器使用文档

## 概述

对象存储管理器提供统一的存储操作接口，支持多种对象存储方式（MinIO、阿里云 OSS、Google Cloud Storage、AWS S3 等）。采用工厂模式和适配器模式，可以通过配置文件灵活切换存储类型。

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    上层业务服务                          │
│  FileParserService / TextSplitterService / ...          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              StorageManager (统一管理器)                 │
│  - 提供统一的存储操作接口                               │
│  - 屏蔽底层存储差异                                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              StorageFactory (工厂类)                     │
│  根据配置创建对应的存储适配器                            │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┼───────────┬──────────────┐
         ▼           ▼           ▼              ▼
    MinIOAdapter OSSAdapter  GCSAdapter    S3Adapter
```

## 核心功能

### 1. 上传文件

```python
from src.db.storage.manager import StorageManager

storage = StorageManager()

# 基础上传
storage_path = await storage.upload_file(
    file_bytes=file_content,
    bucket="my-bucket",
    object_path="path/to/file.txt"
)

# 上传原始文件（自动构建路径）
storage_path = await storage.upload_raw_file(
    file_bytes=file_content,
    user_id="user123",
    session_id="session456",
    file_id="file789",
    filename="document.pdf"
)

# 上传图片（自动构建路径）
image_path = await storage.upload_image(
    image_bytes=image_content,
    user_id="user123",
    session_id="session456",
    file_id="file789",
    image_name="figure1.png"
)
```

### 2. 下载文件

```python
# 下载文件
file_bytes = await storage.download_file(storage_path)

# 检查文件是否存在
exists = await storage.file_exists(storage_path)
```

### 3. 预览文件（生成预签名 URL）

```python
# 生成预览 URL（默认 1 小时过期）
preview_url = await storage.get_preview_url(storage_path)

# 指定过期时间（秒）
preview_url = await storage.get_preview_url(storage_path, expires=7200)  # 2小时

# 获取原始文件的预览 URL
url = await storage.get_raw_file_preview_url(
    user_id="user123",
    session_id="session456",
    file_id="file789",
    filename="document.pdf",
    expires=3600
)

# 获取图片的预览 URL
image_url = await storage.get_image_preview_url(
    user_id="user123",
    session_id="session456",
    file_id="file789",
    image_name="figure1.png",
    expires=3600
)
```

### 4. 删除文件

```python
# 删除文件
success = await storage.delete_file(storage_path)
```

## 配置说明

### 1. 配置文件 (config/config.toml)

```toml
# 存储配置
[storage]
type = "minio"  # 存储类型: minio, oss, gcs, s3

# MinIO 配置
[minio]
endpoint = "localhost:9000"
secure = false
default_bucket = "knowledge-files"
region = "us-east-1"
part_size = 10485760  # 10MB
```

### 2. 环境变量 (.env)

```bash
# MinIO 认证信息
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## 存储路径规范

### 原始文件路径

格式：`users/{user_id}/sessions/{session_id}/raw/{file_id}/{filename}`

示例：`users/user123/sessions/session456/raw/file789/document.pdf`

### 图片路径

格式：`users/{user_id}/sessions/{session_id}/parsed/{file_id}/images/{image_name}`

示例：`users/user123/sessions/session456/parsed/file789/images/figure1.png`

## 错误处理

```python
from src.db.storage.base import (
    StorageError,
    FileNotFoundError,
    UploadError,
    DownloadError
)

try:
    file_bytes = await storage.download_file(storage_path)
except FileNotFoundError:
    logger.error("文件不存在")
except DownloadError as e:
    logger.error(f"下载失败: {e}")
except StorageError as e:
    logger.error(f"存储错误: {e}")
```

## 扩展新的存储类型

### 1. 创建适配器

在 `src/db/storage/adapters/` 目录下创建新的适配器文件，例如 `oss_adapter.py`：

```python
from src.db.storage.base import BaseStorageAdapter

class OSSAdapter(BaseStorageAdapter):
    """阿里云 OSS 存储适配器"""
    
    def __init__(self):
        # 初始化 OSS 客户端
        pass
    
    async def download_file(self, storage_path: str) -> bytes:
        # 实现下载逻辑
        pass
    
    async def upload_file(self, file_bytes: bytes, bucket: str, object_path: str) -> str:
        # 实现上传逻辑
        pass
    
    # ... 实现其他接口方法
```

### 2. 注册适配器

在适配器文件末尾注册：

```python
from src.db.storage.factory import StorageFactory
StorageFactory.register_adapter("oss", OSSAdapter)
```

### 3. 更新配置

在 `config.toml` 中添加新的存储配置：

```toml
[storage]
type = "oss"  # 切换到 OSS

[oss]
endpoint = "oss-cn-hangzhou.aliyuncs.com"
# ... 其他配置
```

## 测试

运行测试脚本：

```bash
uv run python test/test_storage_manager.py
```

测试包括：
1. 文件上传和下载
2. 预览 URL 生成
3. 图片上传
4. 文件删除

## 最佳实践

### 1. 使用依赖注入

在 Service 层使用依赖注入，便于测试：

```python
class FileParserService:
    def __init__(self, storage_manager: StorageManager):
        self._storage = storage_manager
    
    async def parse_file(self, storage_path: str):
        file_bytes = await self._storage.download_file(storage_path)
        # ... 处理文件
```

### 2. 错误处理

始终捕获存储相关的异常：

```python
try:
    await storage.upload_file(...)
except UploadError as e:
    logger.error(f"上传失败: {e}")
    # 处理错误
```

### 3. 资源清理

对于临时文件，记得清理：

```python
# 上传后删除临时文件
temp_path = await storage.upload_raw_file(...)
# ... 使用文件
await storage.delete_file(temp_path)
```

### 4. 预签名 URL 过期时间

根据使用场景设置合适的过期时间：
- 短期分享：300秒（5分钟）
- 一般预览：3600秒（1小时）
- 长期访问：86400秒（24小时）

## 性能优化

### 1. 并发上传

使用 `asyncio.gather` 并发上传多个文件：

```python
tasks = [
    storage.upload_image(img1, user_id, session_id, file_id, "img1.png"),
    storage.upload_image(img2, user_id, session_id, file_id, "img2.png"),
    storage.upload_image(img3, user_id, session_id, file_id, "img3.png"),
]
results = await asyncio.gather(*tasks)
```

### 2. 连接复用

StorageManager 内部的客户端连接会自动复用，无需每次创建新实例。

### 3. 分块上传

对于大文件，可以使用 MinIO 的分块上传功能（part_size 配置）。

## 注意事项

1. **Bucket 创建**：MinIOAdapter 会自动创建不存在的 bucket
2. **路径格式**：storage_path 格式为 `bucket/object_path`
3. **安全性**：生产环境建议启用 `secure=true` 使用 HTTPS
4. **认证信息**：敏感信息应存储在 `.env` 文件中，不要提交到代码仓库

## 常见问题

### Q1: 如何切换存储类型？

修改 `config.toml` 中的 `storage.type` 配置项，并确保对应的适配器已注册。

### Q2: 预签名 URL 失效怎么办？

重新生成 URL，或者增加 `expires` 参数的值。

### Q3: 如何处理大文件？

MinIO 支持自动分块上传，通过 `part_size` 配置项调整分块大小。

### Q4: 如何实现文件版本控制？

在路径中添加版本号或时间戳，例如：
```python
object_path = f"users/{user_id}/files/{file_id}/v{version}/{filename}"
```

## 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-02-04 | v1.0 | 初始版本，实现 MinIO 适配器 |

---

**维护者**: JarsonCai  
**文档状态**: ✅ 已完成
