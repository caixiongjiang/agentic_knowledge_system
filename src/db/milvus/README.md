# Milvus 连接层

Milvus向量数据库连接管理模块，支持Server版和Lite版两种模式。

## 📋 目录结构

```
src/db/milvus/
├── README.md                      # 本文档
├── __init__.py                    # 模块导出
├── milvus_base.py                 # 抽象基类
├── milvus_manager.py              # Server版管理器
├── milvus_lite_manager.py         # Lite版管理器
└── milvus_factory.py              # 工厂函数
```

## 🚀 快速开始

```python
from src.db.milvus import get_milvus_manager

# 自动选择模式（根据配置）
manager = get_milvus_manager()

# 列出所有集合
collections = manager.list_collections()
print(f"找到 {len(collections)} 个集合")
```

## 🏗️ 架构设计

### 类层次结构

```
BaseMilvusManager (抽象基类)
├── MilvusManager (Server版)
└── MilvusLiteManager (Lite版)
```

### 设计模式

- **工厂模式**: 自动选择Server/Lite模式
- **单例模式**: 全局唯一实例，线程安全
- **策略模式**: 不同的连接策略
- **模板方法**: 抽象基类定义流程

## 📦 模块说明

### 1. milvus_base.py

抽象基类，定义统一的连接管理接口。

**核心功能:**
- 线程安全的单例模式（双重检查锁定）
- 内存泄漏防护（析构函数、上下文管理器）
- 统一的连接管理接口

**关键方法:**
- `_connect()`: 连接到Milvus（抽象方法）
- `_verify_connection()`: 验证连接（抽象方法）
- `disconnect()`: 断开连接（抽象方法）
- `check_connection()`: 检查连接状态
- `reconnect()`: 强制重连

### 2. milvus_manager.py

Server版连接管理器，连接到远程Milvus服务器。

**适用场景:**
- 生产环境
- 需要高并发的场景
- 多客户端共享数据

**特点:**
- 支持用户名/密码/Token认证
- 完整的连接池管理
- 健康检查和自动重连

### 3. milvus_lite_manager.py

Lite版连接管理器，使用本地文件数据库。

**适用场景:**
- 开发和测试环境
- 单机部署
- 快速原型开发

**特点:**
- 无需启动独立服务
- 数据存储在本地文件
- 支持数据库备份
- 并发控制（信号量机制）

**特有方法:**
- `get_database_size()`: 获取数据库文件大小
- `backup_database()`: 备份数据库文件
- `acquire_connection()`: 获取连接许可
- `release_connection()`: 释放连接许可

### 4. milvus_factory.py

工厂函数模块，提供统一的管理器获取接口。

**核心函数:**
- `get_milvus_manager(mode=None)`: 获取管理器（自动或指定模式）
- `get_milvus_server_manager()`: 强制获取Server版
- `get_milvus_lite_manager()`: 强制获取Lite版
- `reset_manager()`: 重置管理器实例
- `get_manager_type()`: 获取当前管理器类型
- `is_manager_initialized()`: 检查是否已初始化

## ⚙️ 配置说明

### 配置文件 (config/config.toml)

```toml
[milvus]
# 模式选择: "server" 或 "lite"
mode = "server"

# Server版配置
host = "localhost"
port = 19530
database = "default"
timeout = 30
alias_prefix = "aks_milvus"

# Lite版配置
lite_db_path = "./data/milvus.db"
lite_max_connections = 10
```

### 环境变量 (.env)

```bash
# Server版认证（可选）
MILVUS_USER=username
MILVUS_PASSWORD=password
MILVUS_TOKEN=your_token
```

## 💡 使用示例

### 自动模式

```python
from src.db.milvus import get_milvus_manager

# 根据配置自动选择
manager = get_milvus_manager()
```

### 强制Server版

```python
from src.db.milvus import get_milvus_server_manager

manager = get_milvus_server_manager()
info = manager.get_connection_info()
print(f"连接到: {info['uri']}")
```

### 强制Lite版

```python
from src.db.milvus import get_milvus_lite_manager

manager = get_milvus_lite_manager()
size = manager.get_database_size()
print(f"数据库大小: {size / 1024:.2f} KB")
```

### 上下文管理器

```python
from src.db.milvus import get_milvus_manager

with get_milvus_manager() as manager:
    collections = manager.list_collections()
    # 自动处理资源释放
```

## 🔒 安全特性

### 1. 内存安全

- ✅ 实现 `__del__()` 析构函数
- ✅ 支持 `with` 上下文管理器
- ✅ 及时释放连接资源
- ✅ 避免循环引用

### 2. 线程安全

- ✅ 双重检查锁定（DCL）
- ✅ 使用 `threading.RLock()` 可重入锁
- ✅ 所有共享状态加锁保护
- ✅ 多线程测试验证

### 3. 异常处理

- ✅ 完善的异常捕获
- ✅ 连接失败自动重试
- ✅ 详细的错误日志

## 🧪 测试

运行测试：

```bash
cd /path/to/project
python test/db/milvus/test_connection_layer.py
```

测试覆盖：
1. ✅ 工厂模式测试
2. ✅ Server版管理器测试
3. ✅ Lite版管理器测试
4. ✅ 上下文管理器测试
5. ✅ 线程安全测试

## 📊 性能对比

| 特性 | Server版 | Lite版 |
|-----|---------|--------|
| 连接方式 | 远程服务 | 本地文件 |
| 并发性能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 部署复杂度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 适用场景 | 生产环境 | 开发/测试 |

## 📚 相关文档

- [快速参考](../../../cursor_docs/milvus/快速参考.md)
- [连接层使用指南](../../../cursor_docs/milvus/连接层使用指南.md)
- [连接层开发总结](../../../cursor_docs/milvus/连接层开发总结.md)
- [重构改造计划](../../../cursor_docs/milvus/重构改造计划.md)

## 🔗 依赖

- Python >= 3.8
- pymilvus >= 2.3.0
- loguru
- 项目内部依赖:
  - `src.utils.config_manager`
  - `src.utils.env_manager`

## 📝 版本历史

### v1.0.0 (2026-01-03)

- ✅ 实现抽象基类
- ✅ 重构Server版管理器
- ✅ 新增Lite版管理器
- ✅ 实现工厂模式
- ✅ 完善文档和测试

## 🤝 贡献

如需修改或扩展，请遵循以下原则：

1. 保持单例模式的线程安全
2. 确保内存安全（资源及时释放）
3. 添加完整的类型注解和文档字符串
4. 编写相应的单元测试
5. 更新相关文档

## 📧 联系方式

- 开发者: caixiongjiang
- 项目: Agentic Knowledge System

---

**最后更新**: 2026-01-03
