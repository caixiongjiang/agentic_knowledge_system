# 文档切分模块 (Splitter)

## 概述

文档切分模块负责将解析后的结构化文档切分成合适大小的 Chunk，用于后续的向量化、检索和问答。

## 核心设计理念

**"结构优先，长度兜底"** (Structure-First, Size-Constraint)

- 先按文档自然结构（段落）打散
- 再根据 Token 限制决定合并或拆分
- 最大化保留语义完整性和结构信息

## 模块结构

```
splitter/
├── models.py              # 配置模型和枚举
├── text_cleaner.py        # 文本清洗工具
├── text_splitter.py       # 文本切分器（5种算法）
├── table_splitter.py      # 表格切分器
├── element_processor.py   # 元素处理器
└── README.md             # 本文档

注意：切分服务已移至 Service 层:
src/service/knowledge/components/text_splitter_service.py
```

## 核心组件

### 1. SplitConfig (配置模型)

```python
from src.index.common_file_extract.splitter import SplitConfig, SplitMethod

# 使用默认配置（推荐）
config = SplitConfig()

# 自定义配置
config = SplitConfig(
    split_method=SplitMethod.STRUCTURE_FIRST,
    chunk_size=1000,
    chunk_overlap=0,
    enable_table_split=True,
    enable_text_clean=True
)

# 使用推荐配置
from src.index.common_file_extract.splitter import RECOMMENDED_CONFIGS
config = RECOMMENDED_CONFIGS["table_intensive"]  # 表格密集型文档
```

### 2. TextSplitter (文本切分器)

支持 5 种切分方法：

| 方法 | 说明 | 适用场景 | 推荐度 |
|------|------|---------|-------|
| `structure_first` | 两阶段结构切分 | 所有类型文档 | ⭐⭐⭐⭐⭐ |
| `recursive` | 递归切分 | 通用文档 | ⭐⭐⭐⭐ |
| `regular` | 常规切分 | 格式规整文档 | ⭐⭐⭐ |
| `semantic` | 语义切分 | 高精度检索场景 | ⭐⭐⭐ |
| `token` | Token切分 | 特定LLM限制 | ⭐⭐⭐ |

```python
from src.index.common_file_extract.splitter import TextSplitter, SplitConfig

splitter = TextSplitter(SplitConfig())
chunks = splitter.split_text(text)
```

### 3. TableSplitter (表格切分器)

智能处理超长表格：

```python
from src.index.common_file_extract.splitter import TableSplitter

splitter = TableSplitter()

# 组装表格（不切分）
table_text = splitter.assemble_table(
    table_body="...",
    table_caption="表1: 数据统计",
    table_footnote="注: 数据来源"
)

# 智能切分超长表格（每个切片保留标题和脚注）
table_chunks = splitter.split_large_table(
    table_body="...",
    table_caption="表1: 数据统计",
    table_footnote="注: 数据来源",
    chunk_size=2000
)
```

### 4. TextSplitterService (切分服务)

核心服务类，整合所有功能（位于 Service 层）：

```python
from src.service.knowledge.components.text_splitter_service import TextSplitterService
from src.index.common_file_extract.splitter.models import SplitConfig
from src.db.mysql.connection.mysql_manager import mysql_manager

# 初始化服务
service = TextSplitterService(SplitConfig())

# 从数据库加载 ParseResult 并切分
async def split_document():
    with mysql_manager.get_session() as session:
        # 1. 从数据库加载 ParseResult
        parse_result = await service.load_parse_result_from_db(
            user_id="user_001",
            file_id="file_001",
            mysql_session=session,
            knowledge_base_id="kb_001"
        )
        
        # 2. 执行切分
        split_result = await service.split_document(
            parse_result=parse_result,
            document_id="doc_001"
        )
        
        # 3. 获取数据库写入数据
        mysql_data = split_result.get_mysql_data(document_id="doc_001")
        mongodb_data = split_result.get_mongodb_data()
        embedding_messages = split_result.get_embedding_messages()
        
        return split_result
```

## 数据流向

```
┌─────────────────────────────────────────────────────────────┐
│  MySQL (element_meta_info) + MongoDB (element_data)         │
│  ↓                                                           │
│  ParseResult (ElementInfo 列表)                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  TextSplitterService.split_document()                        │
│  ├─ TextSplitter (文本切分)                                 │
│  ├─ TableSplitter (表格切分)                                │
│  ├─ ElementProcessor (元素处理)                             │
│  └─ TextCleaner (文本清洗)                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  SplitResult (Section + Chunk 列表)                         │
│  ├─ get_mysql_data() → MySQL 批量写入                       │
│  ├─ get_mongodb_data() → MongoDB 批量写入                   │
│  └─ get_embedding_messages() → Kafka 向量化队列             │
└─────────────────────────────────────────────────────────────┘
```

## 切分策略说明

### 两阶段结构切分 (Structure-First) ⭐ 推荐

**核心理念**: 先按段落边界拆分，再根据大小决定合并或拆分。

**工作流程**:

```
文本输入
   ↓
[阶段1] 按 \n\n 拆分成段落列表
   ↓
[阶段2] 遍历每个段落
   ↓
判断段落大小
   ├─> 超大段落 (> chunk_size)
   │      ↓
   │   使用递归切分器切碎该段落
   │      ↓
   │   将切碎的 chunks 加入结果
   │
   └─> 普通段落 (<= chunk_size)
          ↓
       判断: Buffer + 段落是否超长?
          ├─> 超长: 提交 Buffer, 段落成为新 Buffer
          └─> 未超长: 合并到 Buffer
   ↓
返回最终 chunks
```

**优点**:
- ✅ 段落边界清晰，避免中间切割
- ✅ 语义完整性最佳
- ✅ 避免伪合并

**推荐配置**:
```python
config = SplitConfig(
    split_method=SplitMethod.STRUCTURE_FIRST,
    chunk_size=1000,
    chunk_overlap=0,  # 段落本身保证连续性，建议设为0
)
```

### 超长表格切分

**核心原则**:
1. 按行切分表格主体
2. 每个切片都保留完整的标题（caption）和脚注（footnote）
3. 表头在每个切片中重复出现

**示例**:

```
原始表格（100行）:
Caption: 表1：销售数据统计
Header: | 日期 | 产品 | 销量 |
Row 1-99: ...
Footnote: 数据来源：销售系统

切分后（每30行一个切片）:
┌────────────────────────────────┐
│ Chunk 1                        │
│ Caption: 表1：销售数据统计      │
│ Header: | 日期 | 产品 | 销量 | │
│ Row 1-30: ...                  │
│ Footnote: 数据来源：销售系统    │
└────────────────────────────────┘
┌────────────────────────────────┐
│ Chunk 2                        │
│ Caption: 表1：销售数据统计      │← 标题保留
│ Header: | 日期 | 产品 | 销量 | │← 表头保留
│ Row 31-60: ...                 │
│ Footnote: 数据来源：销售系统    │← 脚注保留
└────────────────────────────────┘
```

## 推荐配置方案

### 1. 通用文档（默认）

```python
config = SplitConfig(
    split_method=SplitMethod.STRUCTURE_FIRST,
    chunk_size=1000,
    chunk_overlap=0
)
```

### 2. 长文档（书籍、论文）

```python
config = RECOMMENDED_CONFIGS["long_document"]
# 等同于:
# SplitConfig(
#     split_method=SplitMethod.STRUCTURE_FIRST,
#     chunk_size=1500,
#     chunk_overlap=0
# )
```

### 3. 表格密集型文档

```python
config = RECOMMENDED_CONFIGS["table_intensive"]
# 等同于:
# SplitConfig(
#     split_method=SplitMethod.STRUCTURE_FIRST,
#     chunk_size=2000,
#     chunk_overlap=0,
#     enable_table_split=True,
#     table_max_size=3000
# )
```

### 4. 代码文档

```python
config = RECOMMENDED_CONFIGS["code_document"]
# 等同于:
# SplitConfig(
#     split_method=SplitMethod.STRUCTURE_FIRST,
#     chunk_size=1200,
#     chunk_overlap=0,
#     code_block_max_size=2000
# )
```

## 数据模型

### SplitResult

包含切分后的所有数据：

```python
split_result = SplitResult(
    user_id="user_001",
    file_id="file_001",
    filename="document.pdf",
    status=SplitStatus.SUCCESS,
    sections=[...],  # Section列表
    chunks=[...],    # Chunk列表
    split_method="structure_first",
    chunk_size=1000,
    total_sections=10,
    total_chunks=50,
    document_language="zh"
)

# 获取统计信息
summary = split_result.get_summary()

# 获取数据库写入数据
mysql_data = split_result.get_mysql_data(document_id="doc_001")
mongodb_data = split_result.get_mongodb_data()
embedding_messages = split_result.get_embedding_messages()
```

### ChunkInfo

单个 Chunk 的完整信息：

```python
chunk = ChunkInfo(
    chunk_id="chunk-uuid",
    chunk_type=ChunkType.TEXT,
    section_id="section-uuid",
    content={
        "original": {"content": "文本内容"},
        "translations": []
    },
    page_index=0,
    language="zh",
    metadata={}
)

# 转换为数据库格式
mysql_dict = chunk.to_mysql_dict()
mongodb_dict = chunk.to_mongodb_dict()
embedding_msg = chunk.to_embedding_message_dict()
```

## 最佳实践

### 1. chunk_size 选择

| 内容类型 | 推荐大小 | 理由 |
|---------|---------|------|
| 短问答 | 300-500 | 保证完整问答对 |
| 普通文章 | 800-1200 | 平衡语义完整性和检索粒度 |
| 技术文档 | 1000-1500 | 保留足够上下文 |
| 书籍章节 | 1500-2000 | 保持段落完整性 |

### 2. chunk_overlap 设置

- **structure_first 方法**: 建议设为 0（段落边界天然保证连续性）
- **其他方法**: 建议设为 chunk_size 的 10-20%

### 3. 文本清洗

建议启用所有清洗选项：

```python
config = SplitConfig(
    enable_text_clean=True,
    remove_extra_whitespace=True,
    remove_control_chars=True
)
```

### 4. 表格处理

表格密集型文档建议：
- `chunk_size >= 1500`
- `enable_table_split=True`
- `preserve_table_header=True`

## 性能优化

### 批量处理

```python
from src.service.knowledge.components.text_splitter_service import TextSplitterService

# 推荐：批量加载和处理
async def batch_split(file_ids: List[str]):
    service = TextSplitterService()
    results = []
    
    for file_id in file_ids:
        split_result = await service.split_document(...)
        results.append(split_result)
    
    # 批量写入数据库
    await batch_save_to_db(results)
```

### 内存管理

```python
# 及时清理大对象
del parse_result
del split_result
```

## 注意事项

1. ⚠️ 图片已在 FileParser 阶段上传，切分时直接继承存储信息
2. ⚠️ 所有数据从 MySQL + MongoDB 加载，不依赖中间文件
3. ⚠️ `structure_first` 方法的 `chunk_overlap` 建议设为 0
4. ⚠️ 表格切分会增加存储开销（标题和脚注重复）

## 版本信息

- **版本**: v1.0.0
- **更新日期**: 2026-02-06
- **作者**: JarsonCai
