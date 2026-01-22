# Redis 连接管理器

基于 redis-py 异步客户端实现的 Redis 连接管理器，提供异步连接池、上下文管理和命名空间管理功能。

## 功能特性

- ✅ **异步连接池**：基于 `redis.asyncio` 实现高性能异步连接池
- ✅ **上下文管理**：支持 `async with` 语法，自动管理连接生命周期
- ✅ **命名空间管理**：实现 key 值和连接的逻辑分离，避免 key 冲突
- ✅ **统一 Key 管理**：集中管理所有 Redis key 的命名规范和过期时间
- ✅ **工厂模式**：统一的工厂类管理不同类型的 Redis 连接
- ✅ **配置管理**：从配置文件和环境变量读取配置
- ✅ **按配置缓存**：相同配置共享连接池，不同配置独立连接池
- ✅ **健康检查**：内置健康检查功能
- ✅ **完整的数据类型支持**：字符串、哈希、列表、集合、有序集合

## 架构设计

```
src/db/redis/
├── connection/              # 连接层
│   ├── base.py             # 抽象基类
│   ├── standalone_manager.py  # 单机模式管理器
│   ├── cluster_manager.py  # 集群模式管理器（待实现）
│   ├── factory.py          # 工厂类
│   └── __init__.py
├── namespace.py            # 命名空间管理器
├── __init__.py
└── README.md              # 本文档
```

## 配置说明

### config.toml 配置

```toml
[redis]
# 模式选择：standalone（单机）或 cluster（集群）
mode = "standalone"

# 单机模式配置
host = "localhost"
port = 6379
db = 0                      # 数据库编号（0-15）
max_connections = 50        # 连接池最大连接数
socket_timeout = 5.0        # Socket 超时时间（秒）
socket_connect_timeout = 5.0  # Socket 连接超时时间（秒）
decode_responses = true     # 是否自动解码为字符串
encoding = "utf-8"          # 字符编码

# 业务配置（可选）
key_prefix = "aks:"        # 全局键前缀
default_expire = 3600      # 默认过期时间（秒）
```

### .env 环境变量

```bash
# Redis 认证信息
REDIS_USERNAME=          # Redis 用户名（Redis 6.0+）
REDIS_PASSWORD=          # Redis 密码
```

## 使用指南

### 1. 基础使用

#### 1.1 获取连接管理器

```python
from src.db.redis import get_redis_manager

# 使用默认配置（从 config.toml 读取）
manager = await get_redis_manager()

# 指定模式
manager = await get_redis_manager("standalone")

# 自定义配置（覆盖配置文件）
manager = await get_redis_manager(
    "standalone",
    host="192.168.1.100",
    port=6380,
    db=1
)
```

#### 1.2 使用上下文管理器

```python
# 推荐方式：使用 async with 自动管理连接
async with await get_redis_manager() as manager:
    # 执行 Redis 命令
    await manager.execute("SET", "key", "value")
    value = await manager.execute("GET", "key")
    print(value)  # 输出: value

# 连接会在退出 with 块时自动关闭
```

#### 1.3 手动管理连接

```python
# 获取管理器
manager = await get_redis_manager()

# 初始化连接池
await manager.initialize()

# 使用连接
async with manager.get_connection() as conn:
    await conn.set("key", "value")
    value = await conn.get("key")

# 关闭连接池
await manager.close()
```

### 2. 统一 Key 管理（推荐）

**为什么需要统一 Key 管理？**

在大型项目中，Redis key 分散在各处容易导致：
- ❌ 命名不一致
- ❌ 容易冲突
- ❌ TTL 管理混乱
- ❌ 难以维护和查看

**解决方案：使用 `RedisKeys` 统一管理所有 key**

```python
from src.db.redis import RedisKeys

# ❌ 旧方式：手动拼接，容易出错
old_key = f"user:profile:{user_id}"

# ✅ 新方式：使用统一定义
key = RedisKeys.USER.PROFILE.format(user_id="123")
# 结果: "user:profile:123"

# 获取默认过期时间
ttl = RedisKeys.USER.PROFILE.ttl  # 86400秒（1天）
```

#### 2.1 内置的 Key 类型

```python
# 用户相关
RedisKeys.USER.PROFILE          # 用户资料
RedisKeys.USER.SESSION          # 用户会话
RedisKeys.USER.SETTINGS         # 用户设置
RedisKeys.USER.PERMISSIONS      # 用户权限
RedisKeys.USER.ONLINE_STATUS    # 在线状态

# 缓存相关
RedisKeys.CACHE.DOCUMENT        # 文档缓存
RedisKeys.CACHE.QUERY_RESULT    # 查询结果
RedisKeys.CACHE.API_RESPONSE    # API响应
RedisKeys.CACHE.VECTOR_SEARCH   # 向量检索

# 队列相关
RedisKeys.QUEUE.TASK_QUEUE      # 任务队列
RedisKeys.QUEUE.DELAYED_QUEUE   # 延迟队列
RedisKeys.QUEUE.DEAD_LETTER     # 死信队列

# 锁相关
RedisKeys.LOCK.RESOURCE_LOCK    # 资源锁
RedisKeys.LOCK.OPERATION_LOCK   # 操作锁

# 限流相关
RedisKeys.RATE_LIMIT.API_RATE_LIMIT  # API限流
RedisKeys.RATE_LIMIT.IP_RATE_LIMIT   # IP限流

# 排行榜
RedisKeys.LEADERBOARD.GLOBAL    # 全局排行榜
RedisKeys.LEADERBOARD.DAILY     # 每日排行榜

# 统计
RedisKeys.STATS.PAGE_VIEW       # 访问统计
RedisKeys.STATS.USER_ACTIVITY   # 用户活跃度
```

#### 2.2 注册自定义 Key

```python
from src.db.redis import register_custom_key

# 注册自己的业务 key
MY_KEY = register_custom_key(
    category="CUSTOM",
    name="MY_BUSINESS",
    namespace="mybiz",
    pattern="data:{entity_type}:{entity_id}",
    description="自定义业务数据",
    ttl=7200,  # 2小时
    examples=["mybiz:data:order:12345"]
)

# 使用
key = MY_KEY.format(entity_type="order", entity_id="12345")
```

#### 2.3 查看所有 Key

```python
# 打印所有已注册的 key
RedisKeys.list_all()

# 检查 key 冲突
RedisKeys.check_conflicts()
```

### 3. 命名空间管理

命名空间管理器实现了 **key 值和连接的逻辑分离**，允许多个业务模块共享同一个 Redis 连接池，同时避免 key 冲突。

**推荐：结合统一 Key 管理使用**

```python
from src.db.redis import RedisKeys, RedisNamespace

manager = await get_redis_manager()

# 使用统一定义的命名空间
user_ns = RedisNamespace(manager, RedisKeys.USER.PROFILE.namespace)

# 使用统一定义的 key 模式
key_pattern = RedisKeys.USER.PROFILE.pattern  # "profile:{user_id}"
await user_ns.set(
    key_pattern.format(user_id="123"),
    "用户数据",
    ex=RedisKeys.USER.PROFILE.ttl
)
```

#### 3.1 创建命名空间

```python
from src.db.redis import get_redis_manager, RedisNamespace

# 获取连接管理器
manager = await get_redis_manager()

# 为不同业务创建独立命名空间
user_redis = RedisNamespace(manager, "user")
cache_redis = RedisNamespace(manager, "cache")
session_redis = RedisNamespace(manager, "session")
```

#### 3.2 命名空间操作

```python
# 设置值（自动添加命名空间前缀）
await user_redis.set("123", "user_data")    # 实际 key: "user:123"
await cache_redis.set("123", "cache_data")  # 实际 key: "cache:123"

# 获取值
user_data = await user_redis.get("123")     # 从 "user:123" 获取
cache_data = await cache_redis.get("123")   # 从 "cache:123" 获取

# 它们的 key 都是 "123"，但通过命名空间实现了逻辑隔离
```

#### 3.3 子命名空间

```python
# 创建子命名空间
user_redis = RedisNamespace(manager, "user")
user_profile = user_redis.sub_namespace("profile")
user_settings = user_redis.sub_namespace("settings")

# 使用子命名空间
await user_profile.set("123", "profile_data")   # 实际 key: "user:profile:123"
await user_settings.set("123", "settings_data") # 实际 key: "user:settings:123"
```

### 4. 数据类型操作

命名空间管理器支持 Redis 所有常用数据类型：

#### 3.1 字符串操作

```python
# 设置值
await redis_ns.set("key", "value", ex=3600)  # 设置 1 小时过期

# 获取值
value = await redis_ns.get("key")

# 批量操作
await redis_ns.mset({"key1": "value1", "key2": "value2"})
values = await redis_ns.mget(["key1", "key2"])

# 计数器
count = await redis_ns.incr("counter", amount=1)
count = await redis_ns.decr("counter", amount=1)
```

#### 3.2 哈希表操作

```python
# 设置哈希表字段
await redis_ns.hset("user:123", "name", "张三")
await redis_ns.hset("user:123", mapping={"age": "25", "city": "北京"})

# 获取哈希表字段
name = await redis_ns.hget("user:123", "name")
user_data = await redis_ns.hgetall("user:123")

# 删除字段
await redis_ns.hdel("user:123", "age")

# 检查字段是否存在
exists = await redis_ns.hexists("user:123", "name")
```

#### 3.3 列表操作

```python
# 插入元素
await redis_ns.lpush("queue", "task1", "task2")
await redis_ns.rpush("queue", "task3")

# 弹出元素
task = await redis_ns.lpop("queue")
tasks = await redis_ns.rpop("queue", count=2)

# 获取列表
tasks = await redis_ns.lrange("queue", 0, -1)

# 获取长度
length = await redis_ns.llen("queue")
```

#### 3.4 集合操作

```python
# 添加成员
await redis_ns.sadd("tags", "python", "redis", "async")

# 获取所有成员
members = await redis_ns.smembers("tags")

# 检查成员是否存在
exists = await redis_ns.sismember("tags", "python")

# 移除成员
await redis_ns.srem("tags", "python")

# 获取集合大小
size = await redis_ns.scard("tags")
```

#### 3.5 有序集合操作

```python
# 添加成员（带分数）
await redis_ns.zadd("leaderboard", {"user1": 100, "user2": 95})

# 获取排名
top_users = await redis_ns.zrange("leaderboard", 0, 9, withscores=True)

# 获取分数
score = await redis_ns.zscore("leaderboard", "user1")

# 移除成员
await redis_ns.zrem("leaderboard", "user1")
```

#### 3.6 通用键操作

```python
# 检查键是否存在
exists = await redis_ns.exists("key")

# 删除键
await redis_ns.delete("key1", "key2")

# 设置过期时间
await redis_ns.expire("key", 3600)  # 1 小时后过期

# 获取剩余过期时间
ttl = await redis_ns.ttl("key")

# 移除过期时间
await redis_ns.persist("key")

# 查找匹配模式的键
keys = await redis_ns.keys("user:*")
```

### 5. 高级功能

#### 5.1 健康检查

```python
# PING 测试
is_alive = await manager.ping()

# 健康检查
is_healthy = await manager.health_check()
```

#### 5.2 获取信息

```python
# 获取服务器信息
info = await manager.get_info()
memory_info = await manager.get_info("memory")

# 获取数据库键数量
db_size = await manager.get_db_size()
```

#### 5.3 数据库管理

```python
# 清空当前数据库（谨慎使用）
await manager.flush_db(asynchronous=True)

# 清空命名空间（仅删除该命名空间下的键）
await redis_ns.clear_namespace()
```

#### 5.4 切换数据库

```python
# 切换到数据库 1
await manager.select_db(1)
```

## 使用场景示例

### 场景 1：用户会话管理

```python
from src.db.redis import get_redis_manager, RedisNamespace

# 创建会话命名空间
manager = await get_redis_manager()
session_redis = RedisNamespace(manager, "session")

# 存储用户会话
async def store_session(user_id: str, session_data: dict):
    await session_redis.hset(
        user_id,
        mapping={
            "token": session_data["token"],
            "login_time": session_data["login_time"],
            "ip": session_data["ip"]
        }
    )
    # 设置 7 天过期
    await session_redis.expire(user_id, 7 * 24 * 3600)

# 获取用户会话
async def get_session(user_id: str):
    return await session_redis.hgetall(user_id)

# 删除用户会话
async def delete_session(user_id: str):
    await session_redis.delete(user_id)
```

### 场景 2：缓存管理

```python
# 创建缓存命名空间
cache_redis = RedisNamespace(manager, "cache")

# 缓存文档数据
async def cache_document(doc_id: str, content: str, expire: int = 3600):
    await cache_redis.set(doc_id, content, ex=expire)

# 获取缓存
async def get_cached_document(doc_id: str):
    return await cache_redis.get(doc_id)

# 批量缓存
async def cache_multiple(documents: dict):
    await cache_redis.mset(documents)
```

### 场景 3：任务队列

```python
# 创建任务队列命名空间
queue_redis = RedisNamespace(manager, "queue")

# 添加任务到队列
async def enqueue_task(task_data: str):
    await queue_redis.rpush("tasks", task_data)

# 从队列获取任务
async def dequeue_task():
    return await queue_redis.lpop("tasks")

# 获取队列长度
async def get_queue_size():
    return await queue_redis.llen("tasks")
```

### 场景 4：排行榜

```python
# 创建排行榜命名空间
leaderboard_redis = RedisNamespace(manager, "leaderboard")

# 更新用户分数
async def update_score(user_id: str, score: float):
    await leaderboard_redis.zadd("global", {user_id: score})

# 获取排行榜前 10 名
async def get_top_10():
    return await leaderboard_redis.zrange("global", 0, 9, withscores=True)

# 获取用户排名
async def get_user_rank(user_id: str):
    score = await leaderboard_redis.zscore("global", user_id)
    return score
```

## 最佳实践

1. **使用上下文管理器**：始终使用 `async with` 确保连接正确关闭
2. **命名空间隔离**：为不同业务模块创建独立命名空间，避免 key 冲突
3. **设置过期时间**：为缓存数据设置合理的过期时间，避免内存溢出
4. **批量操作**：使用 `mget`、`mset` 等批量操作提高性能
5. **连接池复用**：通过工厂类获取管理器，避免创建多个连接池
6. **健康检查**：定期进行健康检查，确保连接正常
7. **谨慎使用 KEYS**：生产环境避免使用 `keys("*")`，改用 `scan`

## 注意事项

1. **依赖安装**：需要安装 `redis` 包（包含异步支持）
   ```bash
   uv add redis[hiredis]
   ```

2. **Python 版本**：需要 Python 3.13+（支持异步语法）

3. **Redis 版本**：建议使用 Redis 5.0+

4. **集群模式**：集群模式功能尚未完全实现，请使用单机模式

5. **线程安全**：异步连接池是协程安全的，但不是线程安全的

## 故障排查

### 连接失败

```python
# 检查 Redis 是否运行
await manager.ping()

# 检查配置是否正确
print(manager.get_redis_url())
```

### 密码错误

确保 `.env` 文件中的 `REDIS_PASSWORD` 正确。

### 连接超时

调整 `socket_timeout` 和 `socket_connect_timeout` 配置。

### 内存不足

定期清理过期数据，设置合理的 `maxmemory` 策略。

## 性能优化

1. **连接池大小**：根据并发量调整 `max_connections`
2. **管道操作**：对于大量命令，使用 Redis Pipeline
3. **批量操作**：使用 `mget`、`mset`、`hmset` 等批量命令
4. **持久化策略**：根据需求选择 RDB 或 AOF
5. **键设计**：使用合理的键命名规范和过期策略

## 未来扩展

- [ ] Redis Cluster 集群模式完整支持
- [ ] Redis Sentinel 哨兵模式支持
- [ ] Pipeline 管道操作封装
- [ ] Lua 脚本支持
- [ ] 发布/订阅功能
- [ ] Stream 流数据类型支持
- [ ] 连接池监控和统计
