# LLM Client 使用指南

**版本**: v1.0  
**创建日期**: 2026-01-05  
**状态**: ✅ 已完成

---

## 📋 目录

1. [快速开始](#快速开始)
2. [支持的Provider](#支持的provider)
3. [基本用法](#基本用法)
4. [高级用法](#高级用法)
5. [配置说明](#配置说明)
6. [常见问题](#常见问题)

---

## 🚀 快速开始

### 环境准备

1. **设置API Key（在.env文件中）**

```bash
# DeepSeek
DEEPSEEK_API_KEY=sk-xxx

# OpenAI
OPENAI_API_KEY=sk-xxx

# Gemini
GEMINI_API_KEY=xxx

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-xxx
```

2. **安装依赖**

```bash
pip install httpx pydantic loguru
```

### 最简单的示例

```python
from src.client.llm import create_llm_client

# 创建客户端
client = create_llm_client(
    provider="deepseek",
    model_name="deepseek-chat",
    temperature=0.0,
    max_tokens=1000
)

# 发送请求
response = client.generate(
    messages=[
        {"role": "user", "content": "什么是Python？"}
    ]
)

# 获取结果
print(response.content)  # 回答内容
print(response.usage.total_tokens)  # Token使用
```

---

## 🌐 支持的Provider

| Provider | 模型示例 | 特性 | API Key环境变量 |
|----------|---------|------|----------------|
| **OpenAI** | gpt-4o, gpt-4-turbo | 标准格式 | OPENAI_API_KEY |
| **DeepSeek** | deepseek-chat, deepseek-reasoner | V3.2，支持推理模式 | DEEPSEEK_API_KEY |
| **Gemini** | gemini-1.5-pro | 多模态支持 | GEMINI_API_KEY |
| **Anthropic** | claude-3-5-sonnet | 长上下文 | ANTHROPIC_API_KEY |

### DeepSeek-V3.2 模型说明

- **deepseek-chat**: 非思考模式，快速响应，适合一般对话
- **deepseek-reasoner**: 思考模式，适合复杂推理任务（推荐）

---

## 💡 基本用法

### 1. 直接使用（临时模式）

```python
from src.client.llm import create_llm_client

client = create_llm_client("deepseek", "deepseek-chat")
response = client.generate(messages=[...])
# 临时HTTP客户端自动关闭，无需手动管理
```

### 2. 上下文管理器（推荐，批量处理）

```python
with create_llm_client("deepseek", "deepseek-chat") as client:
    # 复用连接池，性能更优
    response1 = client.generate(messages=[...])
    response2 = client.generate(messages=[...])
    response3 = client.generate(messages=[...])
# 自动关闭连接池
```

### 3. 异步模式

```python
import asyncio
from src.client.llm import create_llm_client

async def main():
    async with create_llm_client("deepseek", "deepseek-chat") as client:
        response = await client.agenerate(messages=[...])
        print(response.content)

asyncio.run(main())
```

---

## 🔥 高级用法

### 1. 异步并发（高性能）

```python
import asyncio
from src.client.llm import create_llm_client

async def process_batch(questions):
    """批量处理，并发执行"""
    async with create_llm_client("deepseek", "deepseek-chat") as client:
        # 创建并发任务
        tasks = [
            client.agenerate(messages=[{"role": "user", "content": q}])
            for q in questions
        ]
        
        # 并发执行（复用连接池）
        responses = await asyncio.gather(*tasks)
        
        return responses

# 运行
questions = ["问题1", "问题2", "问题3", ...]
responses = asyncio.run(process_batch(questions))
```

**性能对比：**
- 串行处理100个请求：~1000秒
- 异步并发：~10秒（100倍提升）

### 2. 控制并发数量（避免过载）

```python
import asyncio
from src.client.llm import create_llm_client

async def process_with_limit(questions, max_concurrent=10):
    """限制并发数量"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_generate(client, msg):
        async with semaphore:
            return await client.agenerate(messages=msg)
    
    async with create_llm_client("deepseek", "deepseek-chat") as client:
        tasks = [limited_generate(client, [{"role": "user", "content": q}]) 
                 for q in questions]
        return await asyncio.gather(*tasks)

# 100个请求，但同时只有10个在执行
responses = asyncio.run(process_with_limit(questions, max_concurrent=10))
```

### 3. DeepSeek-V3.2 推理模式

```python
# 方式1: 使用 deepseek-reasoner（推荐）
client = create_llm_client(
    provider="deepseek",
    model_name="deepseek-reasoner",  # V3.2 思考模式
    temperature=0.0,
    max_tokens=500
)

response = client.generate(messages=[...])

# 访问推理过程
if response.thinking:
    print("推理过程:", response.thinking.reasoning)
    print("推理Token:", response.thinking.tokens_used)

# 方式2: 使用 deepseek-chat + enable_thinking（等价）
client = create_llm_client(
    provider="deepseek",
    model_name="deepseek-chat",
    enable_thinking=True  # 启用推理
)
```

**推荐**: 直接使用 `deepseek-reasoner`，语义更清晰。

### 4. 多模态（Gemini）

```python
client = create_llm_client("gemini", "gemini-1.5-pro")

response = client.generate(
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这张图片里有什么？"},
                {"type": "image_url", "image_url": "https://..."}
            ]
        }
    ]
)
```

### 5. 错误处理

```python
import httpx
from src.client.llm import create_llm_client

async def safe_generate(client, messages):
    """带错误处理的生成"""
    try:
        return await client.agenerate(messages=messages, max_tokens=100)
    except httpx.TimeoutException:
        print("请求超时，重试中...")
        return await client.agenerate(messages=messages, max_tokens=100)
    except httpx.HTTPError as e:
        print(f"HTTP错误: {e}")
        return None
    except ValueError as e:
        print(f"参数错误: {e}")
        return None

# 批量处理，一个失败不影响其他
async with create_llm_client("deepseek", "deepseek-chat") as client:
    tasks = [safe_generate(client, msg) for msg in messages_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 6. 自定义参数

```python
client = create_llm_client(
    provider="deepseek",
    model_name="deepseek-chat",
    api_base="https://custom-api.com",  # 自定义API地址
    temperature=0.7,
    max_tokens=2000,
    top_p=0.9,
    timeout=120,  # 超时时间（秒）
    enable_retry=True,  # 启用重试
    max_retries=3,
    retry_delay=0.5
)
```

---

## ⚙️ 配置说明

### 配置文件：config.json

```json
{
  "llm": {
    "providers": {
      "deepseek": {
        "api_base": "https://api.deepseek.com",
        "default_timeout": 120
      }
    },
    
    "presets": {
      "fast": {
        "provider": "deepseek",
        "model_name": "deepseek-chat",
        "temperature": 0.0,
        "max_tokens": 2048
      },
      "reasoning": {
        "provider": "deepseek",
        "model_name": "deepseek-chat",
        "enable_thinking": true
      }
    }
  }
}
```

### 环境变量：.env

```bash
# DeepSeek (V3.2)
DEEPSEEK_API_KEY=sk-xxx
# 模型: deepseek-chat (非思考), deepseek-reasoner (思考)

# OpenAI
OPENAI_API_KEY=sk-xxx

# Gemini
GEMINI_API_KEY=xxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
```

---

## ❓ 常见问题

### Q1: 如何选择同步还是异步？

**同步：** 简单场景，单次请求
```python
client = create_llm_client("deepseek", "deepseek-chat")
response = client.generate(messages=[...])
```

**异步：** 批量处理，高并发需求
```python
async with create_llm_client("deepseek", "deepseek-chat") as client:
    responses = await asyncio.gather(
        client.agenerate(messages=msg1),
        client.agenerate(messages=msg2),
        ...
    )
```

### Q2: 上下文管理器是必须的吗？

**不是必须，但强烈推荐：**

```python
# 临时模式（可以）
client = create_llm_client("deepseek", "deepseek-chat")
response = client.generate(messages=[...])
# 临时HTTP客户端自动关闭

# 上下文管理器（推荐）
with create_llm_client("deepseek", "deepseek-chat") as client:
    response1 = client.generate(messages=[...])  # 复用连接
    response2 = client.generate(messages=[...])  # 复用连接
# 持久化HTTP客户端自动关闭
```

### Q3: 如何处理API配额限制？

使用信号量限制并发：

```python
semaphore = asyncio.Semaphore(5)  # 最多5个并发

async def limited_generate(client, msg):
    async with semaphore:
        return await client.agenerate(messages=msg)
```

### Q4: Gemini的API key为什么不同？

Gemini使用URL参数传递API key，已自动处理：

```python
# 无需特殊处理，正常使用即可
client = create_llm_client("gemini", "gemini-1.5-pro")
response = client.generate(messages=[...])
# 内部自动添加 ?key=xxx 到URL
```

### Q5: 如何查看原始响应？

```python
response = client.generate(messages=[...])
print(response.raw_response)  # 原始API响应
```

### Q6: 支持流式输出吗？

当前版本暂不支持流式输出，后续版本会添加。

---

## 📚 相关文档

- [设计文档](../../../cursor_docs/llm/llm_client_design.md)
- [Adapter开发指南](../../../cursor_docs/llm/adapters_guide.md)
- [快速参考](../../../cursor_docs/llm/quick_reference.md)

---

## 🎯 最佳实践

1. ✅ **批量处理使用异步**：性能提升100倍
2. ✅ **使用上下文管理器**：复用连接池
3. ✅ **限制并发数量**：避免API过载
4. ✅ **启用错误处理**：一个失败不影响其他
5. ✅ **记录Token使用**：成本控制

---

**完成时间**: 2026-01-05  
**维护者**: caixiongjiang
