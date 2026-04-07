# Agentic 知识库召回架构设计

## 版本信息

- **版本号**: v2.0
- **创建日期**: 2026-02-28
- **最后更新**: 2026-04-03
- **设计目标**: 在百万级文档规模下，以 **"先准后快"** 为原则，构建兼顾高效批量召回与 Agentic 自主补全的分层检索体系。

## 1. 架构理念演进

### 1.1 传统 RAG 的局限

传统 RAG 是一条静态的线性流水线：

```
Query → 多路召回(语义+BM25) → 粗排 → Reranker → 拼接 Prompt
```

其核心缺陷：
- **路由僵化**：召回路由在代码中固定，无法根据 query 意图动态调整
- **单粒度视角**：通常只在 Chunk 粒度检索，无法利用 Document/Section/QA/Graph 等多粒度信息
- **无反馈机制**：一次性出结果，即使召回不完整也无法自我修正
- **规模瓶颈**：纯 Agentic（LLM 逐步工具调用）在百万文档下延迟不可控

### 1.2 新架构：计划-执行-验证 三阶段模型

新架构的核心是将 LLM 的智能嵌入检索管道的**两个关键决策点**，中间保持高效的确定性执行：

```
LLM₁ (路由规划) → 确定性多路召回 Pipeline → LLM₂ (结果验证 + 自主补全)
   计划阶段              执行阶段                 校验阶段
```

**设计哲学**：
- **LLM 做决策，Pipeline 做执行** —— 不让 LLM 逐条搜索（太慢），也不让规则引擎做意图理解（太傻）
- **先准后快** —— 可接受 5-10 秒延迟，但必须保证召回的准确性和覆盖度
- **多粒度自由导航** —— 从 Chunk、Section、Document、QA、Graph 任意粒度入手，支持上卷、下钻、同级扩展

---

## 2. 整体 Pipeline 架构

### 2.1 全景流程

```
┌───────────────────────────────────────────────────────────────┐
│  Phase 1: 查询理解 + 路由规划 (LLM₁)                 ~1-2s   │
│                                                                │
│  输入: query_text + 可用路由描述 + 元数据过滤条件              │
│  输出: 结构化路由计划 (JSON)                                   │
│    - 激活哪些路由 + 每路参数                                   │
│    - 对 query 的意图理解和关键实体抽取                         │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 2: 多路并行召回 (无 LLM)                       ~100ms  │
│                                                                │
│  根据路由计划，asyncio.gather 并行执行多路召回                 │
│  每路独立查询各自的存储后端 (Milvus / MongoDB / MySQL)         │
│  产出: List[RetrieveResult]（混合粒度）                        │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 3: 跨粒度对齐 (无 LLM)                          ~50ms  │
│                                                                │
│  将 Section/Document/QA/Summary 级别结果下钻对齐到 Chunk 粒度  │
│  非 Chunk 粒度结果通过 query 向量做 in-memory 二次精排         │
│  产出: 统一的 List[ChunkItem]                                  │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 4: RRF 融合 + 去重 (无 LLM)                      ~5ms  │
│                                                                │
│  跨路由 Reciprocal Rank Fusion (k=60)                          │
│  按 chunk_id 去重，保留最高融合分                              │
│  产出: 排序后的 ~100-200 候选 ChunkItem                        │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 5: Reranker 精排 (无 LLM)                    ~200-500ms │
│                                                                │
│  Cross-Encoder (bge-reranker-v2-m3) 对候选集精排              │
│  产出: Top-K 精排结果                                          │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 6: 结果验证 + 自主补全 (LLM₂ Agent)            ~1-5s   │
│                                                                │
│  LLM 审视: 原始 query + Top-K 结果                             │
│    → 通过: 直接返回                                 (~1-2s)   │
│    → 不通过: LLM 自主选择工具补全 (max 2-3 轮)      (~3-6s)   │
│                                                                │
│  可用工具: ContextWindow / DrillDown / RollUp /                │
│           Skeleton / ReRetrieve / GraphExplore                 │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
                       最终结果返回

总延迟预算:
  - 验证通过场景: ~2-4s
  - 需要补全场景: ~4-8s
  - 极端补全场景: ~8-10s (max)
```

### 2.2 多粒度入口与自由导航

系统支持从任意粒度入手检索，并在粒度间自由穿梭：

```
                    Document (摘要语义 / 关键词)
                        ▲ roll_up  │ drill_down
                        │          ▼
                    Section (章节标题语义)
                        ▲ roll_up  │ drill_down
                        │          ▼
  context_window ◄── Chunk (文本块语义 / 稀疏词权重) ──► context_window
                        ▲ roll_up  │ drill_down
                        │          ▼
                    Element (文本 / 表格 / 图像 / 公式)

  独立入口:
    QA 对 (atomic_qa_store) ──溯源──► Chunk
    Graph 实体/关系 (Neo4j) ──溯源──► Chunk
```

**每个入口都是一条独立的召回路由**，LLM₁ 可以根据 query 意图选择任意组合。

---

## 3. Phase 1 详设：LLM₁ 路由规划

### 3.1 角色定位

LLM₁ 是一个 **"参谋"** —— 只做分析和规划，不执行检索。它接收 query 和可用路由的描述信息，输出结构化的路由计划。

### 3.2 可用路由清单

LLM₁ 可选择的路由直接对应已实现的原子能力（Capability）：

| 路由标识 | 对应 Capability 类 | Milvus Collection / 后端 | 粒度 | 描述 |
|---------|-------------------|-------------------------|------|------|
| `chunk_dense` | `ChunkVectorSearch` | `chunk_store` | Chunk | 基础 Chunk 稠密向量 ANN 检索 |
| `enhanced_chunk_dense` | `EnhancedChunkVectorSearch` | `enhanced_chunk_store` | Chunk | 融合 Section 标题语义的增强 Chunk 检索 |
| `section_dense` | `SectionVectorSearch` | `section_store` | Section | 章节标题级语义检索 |
| `qa_dense` | `QAVectorSearch` | `atomic_qa_store` | QA | 原子 QA 对语义匹配 |
| `summary_dense` | `SummaryVectorSearch` | `summary_store` | Document | 文档摘要级语义检索 |
| `bm25_sparse` | `BM25Search` | `chunk_store (sparse_vector)` | Chunk | BGE-M3 稀疏向量全文检索 |
| `exact_match` | `ExactMatch` | MongoDB `chunk_data` | Chunk | 精确/前缀/正则字面匹配 |
| `boolean_search` | `BooleanSearch` | MongoDB `chunk_data` | Chunk | AND/OR/NOT 布尔逻辑检索 |
| `graph_explore` | *(待实现)* | Neo4j | Link/Node | 实体关系多跳探索 |

### 3.3 LLM₁ 输入

```json
{
  "role": "system",
  "content": "你是一个检索路由规划器。根据用户查询和可用的检索路由，生成最优的多路召回计划。\n\n## 可用路由\n<各路由的名称、描述、适用场景、参数格式>\n\n## 规划原则\n1. 通用查询至少激活 chunk_dense + bm25_sparse 两路\n2. 包含专有名词/代码/型号时，额外激活 exact_match\n3. 问答型查询（什么是/如何）额外激活 qa_dense\n4. 主题探索型查询额外激活 section_dense 或 summary_dense\n5. 包含代词/上下文依赖时，优先使用 enhanced_chunk_dense 替代 chunk_dense\n6. 每路 top_k 建议为最终需求的 2-3 倍"
}
```

```json
{
  "role": "user",
  "content": "查询: {query_text}\n过滤条件: {filters}\n最终需要 top_k={top_k} 条结果\n\n请生成路由计划。"
}
```

### 3.4 LLM₁ 输出格式

```json
{
  "query_analysis": {
    "intent": "factual_qa | topic_exploration | comparison | navigation | exact_lookup",
    "key_entities": ["实体1", "实体2"],
    "contains_jargon": true,
    "context_dependent": false,
    "reasoning": "该查询要求精确查找某芯片型号的技术参数，包含专有名词 STM32G030C6"
  },
  "route_plan": [
    {
      "route": "chunk_dense",
      "top_k": 30,
      "params": {}
    },
    {
      "route": "bm25_sparse",
      "top_k": 30,
      "params": {}
    },
    {
      "route": "exact_match",
      "top_k": 10,
      "params": {
        "keywords": ["STM32G030C6"],
        "match_mode": "fuzzy"
      }
    }
  ],
  "fusion_strategy": "rrf",
  "rerank_top_n": 50
}
```

### 3.5 为什么用 LLM 而不是规则引擎

| 维度 | 规则引擎 | LLM |
|------|---------|-----|
| 意图理解 | 基于关键词模式匹配，覆盖面有限 | 理解自然语言语义，处理歧义和隐含意图 |
| 实体抽取 | 需要预定义词表或 NER 模型 | 零样本抽取，无需维护词表 |
| 适应性 | 新增路由需要手动添加规则 | 只需更新 system prompt 中的路由描述 |
| 延迟 | < 1ms | ~1-2s |
| 适用规模 | 百万级可接受（延迟预算 5-10s 内） | 百万级可接受 |

在 5-10s 延迟预算下，LLM 路由规划的 1-2s 开销完全可接受，换来的是显著更好的路由质量。

---

## 4. Phase 2-5 详设：确定性执行 Pipeline

### 4.1 Phase 2：多路并行召回

根据 LLM₁ 的路由计划，使用 `asyncio.gather` 并行执行所有激活的路由：

```python
async def _parallel_recall(self, route_plan: List[RouteConfig], query: str, filters: MetadataFilter) -> List[RetrieveResult]:
    tasks = []
    for route in route_plan:
        capability = self._get_capability(route.route)
        task = capability.execute(query=build_query(route, query, filters))
        tasks.append(task)
    return await asyncio.gather(*tasks)
```

**并行策略**：所有路由独立执行，取最慢一路的耗时。典型场景下 Milvus ANN 查询 ~20-50ms，3-5 路并行总耗时 ~50-100ms。

### 4.2 Phase 3：跨粒度对齐

不同路由返回的结果粒度不同，统一对齐到 **Chunk 粒度**（因为 Chunk 是最终送入 Reranker 和 LLM 的基本单元）：

| 源粒度 | 对齐方式 | 分数继承 |
|--------|---------|---------|
| Chunk (chunk_dense / enhanced / bm25 / exact_match) | 直接使用 | 原始分数 |
| Section (section_dense) | 查询 `ChunkSectionDocumentRepo` 获取该 Section 下所有 Chunk，用 query 向量 in-memory 二次精排取 top-N | 继承 Section 分数 × 衰减系数 (0.9) |
| QA (qa_dense) | 通过 QA 元数据中的 `chunk_id` 溯源 | 继承 QA 分数 |
| Document/Summary (summary_dense) | Document → Section → Chunk 逐级下钻，每级取 top-N | 继承 Summary 分数 × 衰减系数 (0.7) |
| Graph (graph_explore) | 通过 Link 的 `chunk_id` 溯源到原始 Chunk | 继承图谱分数 |

**关键约束**：Section/Document 级别下钻时，不拉取全部 Chunk。使用 query 向量对下钻出的 Chunk 向量做 in-memory cosine similarity，每个 Section 只保留 top-N（默认 N=5），防止大文档（数百个 Chunk）污染结果池。

### 4.3 Phase 4：RRF 融合 + 去重

**Reciprocal Rank Fusion (RRF)** 融合公式：

```
RRF_score(chunk) = Σ 1 / (k + rank_i(chunk))
```

其中 `k = 60`（标准取值），`rank_i` 是 chunk 在第 i 路中的排名。

RRF 的优势在于不依赖原始分数的绝对值，只关注相对排名，天然适合跨粒度、跨引擎的异构结果融合。

**去重规则**：按 `chunk_id` 去重，保留 RRF 分数最高的记录。

### 4.4 Phase 5：Reranker 精排

使用 Cross-Encoder 模型（`bge-reranker-v2-m3`）对融合后的候选集精排：

- 输入：(query, chunk_text) 对
- 输出：相关性分数
- 候选数量：取融合后的 top-N（默认 N=100，由 LLM₁ 的 `rerank_top_n` 控制）
- 最终保留：top-K（用户指定的最终返回数量）

---

## 5. Phase 6 详设：LLM₂ 结果验证 Agent

### 5.1 角色定位

LLM₂ 是一个 **mini-Agent** —— 能思考，能调用工具。它的职责是对精排后的 Top-K 结果进行**质量校验**，判断是否充分覆盖了 query 的信息需求。

### 5.2 工具箱

LLM₂ 可调用的工具直接对应已实现的导航类原子能力和新增的二次召回能力：

| 工具名称 | 对应 Capability | 用途 | 典型触发场景 |
|---------|----------------|------|-------------|
| `context_window` | `ContextWindow` | 获取锚点 Chunk 前后相邻 Chunk | 结果文本被截断、遇到"如上所述"等过渡语 |
| `drill_down` | `DrillDown` | 从 Section/Document 下钻到 Chunk/Element | 需要更细粒度信息（如特定表格、图像） |
| `roll_up` | `RollUp` | 从 Chunk 上卷到 Section/Document | 需要更宏观的上下文背景 |
| `skeleton` | `Skeleton` | 提取文档骨架大纲 | 需要了解文档整体结构以辅助定位 |
| `re_retrieve` | *(新增)* | 用修改后的 query 或不同路由组合重新走 Phase 2-5 | 初始结果完全不相关、覆盖度严重不足 |
| `graph_explore` | *(待实现)* | 以实体为起点探索关联知识 | 需要补充隐性关联或多跳推理信息 |

### 5.3 LLM₂ 系统提示

```
你是一个检索结果验证器。你的任务是判断检索结果是否充分回答了用户查询。

## 判断标准
1. 信息完整性：结果是否覆盖了 query 涉及的所有方面
2. 信息截断：是否有结果的文本明显被截断（半句话、缺少结论）
3. 上下文缺失：是否有结果需要更多背景才能理解
4. 多样性：结果是否过于集中在某一篇文档

## 决策选项
- 如果结果充分：返回 {"action": "pass"}
- 如果需要补全：返回 {"action": "supplement", "tool_calls": [...]}

## 约束
- 最多进行 2-3 轮工具调用
- 优先使用 context_window 和 drill_down，它们延迟最低
- re_retrieve 是最后手段，仅在初始结果严重不足时使用
```

### 5.4 工具调用示例

**场景：检索结果文本截断**

```json
{
  "action": "supplement",
  "reasoning": "第 3 条结果 (chunk_id=abc123) 以'具体的性能对比数据如下表所示：'结尾，但未包含表格数据",
  "tool_calls": [
    {
      "tool": "context_window",
      "params": {
        "chunk_id": "abc123",
        "direction": "next",
        "window_size": 2
      }
    }
  ]
}
```

**场景：query 涉及两个方面，结果只覆盖了一个**

```json
{
  "action": "supplement",
  "reasoning": "用户问了'A方案和B方案的对比'，但结果只包含A方案的信息，缺少B方案",
  "tool_calls": [
    {
      "tool": "re_retrieve",
      "params": {
        "modified_query": "B方案 性能 设计 架构",
        "route_overrides": ["chunk_dense", "bm25_sparse", "exact_match"],
        "top_k": 10
      }
    }
  ]
}
```

---

## 6. 原子能力分层体系

### 6.1 分层总览

在新架构下，原子能力（Capability）不再平铺暴露给外部 Agent，而是分化为三个层次：

```
┌─────────────────────────────────────────────────────────┐
│  层次 1: 高阶检索 Skill (对外暴露)                       │
│                                                           │
│  smart_retrieve(query, filters, top_k)                   │
│    整个 RetrieveService Pipeline 的封装                   │
│    外部 Agent 的主要入口                                  │
│                                                           │
│  retrieve_single(capability_name, **params)               │
│    直接调用某个原子能力（旁路，保留手动探索权）            │
└───────────────────────────┬───────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────┐
│  层次 2: 召回路由 (LLM₁ 的选择空间，Pipeline 内部消化)    │
│                                                           │
│  ┌─ 语义检索路由 ────────────────────────────────────┐   │
│  │  ChunkVectorSearch        → chunk_store           │   │
│  │  EnhancedChunkVectorSearch → enhanced_chunk_store  │   │
│  │  SectionVectorSearch      → section_store         │   │
│  │  QAVectorSearch           → atomic_qa_store       │   │
│  │  SummaryVectorSearch      → summary_store         │   │
│  └───────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─ 字面检索路由 ────────────────────────────────────┐   │
│  │  BM25Search     → Milvus sparse_vector (BGE-M3)   │   │
│  │  ExactMatch     → MongoDB $regex                  │   │
│  │  BooleanSearch  → MongoDB 布尔 AST                │   │
│  └───────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─ 图谱检索路由 (待实现) ───────────────────────────┐   │
│  │  GraphExplore   → Neo4j Cypher                    │   │
│  └───────────────────────────────────────────────────┘   │
└───────────────────────────┬───────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────┐
│  层次 3: 补全工具 (LLM₂ Agent 的工具箱，Pipeline 内部)    │
│                                                           │
│  ┌─ 导航能力 ────────────────────────────────────────┐   │
│  │  ContextWindow  → 同 Section 内前后滑动扩充       │   │
│  │  DrillDown      → 跨粒度下钻 (Document→Chunk)     │   │
│  │  RollUp         → 跨粒度上卷 (Chunk→Section)      │   │
│  │  Skeleton       → 文档骨架目录提取                │   │
│  └───────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─ 扩展能力 ────────────────────────────────────────┐   │
│  │  ReRetrieve     → 二次召回 (重走 Phase 2-5)       │   │
│  │  GraphExplore   → 实体关系多跳探索 (待实现)       │   │
│  │  Traceback      → 知识溯源 (Graph→Chunk, 待实现)  │   │
│  └───────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

### 6.2 层次 1：高阶检索 Skill（对外暴露）

对外部 Agent 或上层业务来说，检索系统只暴露两个 Skill：

**Skill A：智能检索 (`smart_retrieve`)**

对应 `RetrieveService.retrieve()` 方法。外部 Agent 将其视为黑盒，一次调用完成从路由规划到结果验证的完整流程。

```
输入: query_text, filters (knowledge_base_id / document_ids / ...), top_k
输出: List[ChunkItem] (精排 + 验证后的最终结果)
```

**Skill B：直接能力调用 (`retrieve_single`)**

对应 `RetrieveService.retrieve_single()` 方法。外部 Agent 绕过 Pipeline，直接调用任意一个原子能力。用于手动探索、调试或 Agentic 工作流中需要精确控制时。

```
输入: capability_name (如 "context_window"), 对应能力的具体参数
输出: RetrieveResult (该能力的原始结果)
```

### 6.3 层次 2：召回路由能力（LLM₁ 选择空间）

这些能力**不直接暴露给外部 Agent**，而是被 RetrieveService 内部消化为 LLM₁ 可选的路由选项。每个能力的 `CapabilityDescriptor` 用于生成 LLM₁ 的 system prompt。

#### 6.3.1 语义向量检索路由

**Route: chunk_dense — Chunk 稠密向量检索**
- Capability: `ChunkVectorSearch`
- Collection: `chunk_store`
- 向量: Qwen3-embedding-0.6b (1024d), COSINE / HNSW
- 适用: 事实性问答，精确定位单一知识点

**Route: enhanced_chunk_dense — 上下文增强 Chunk 检索**
- Capability: `EnhancedChunkVectorSearch`
- Collection: `enhanced_chunk_store`
- 向量: 融合 Section 标题背景语义的 Chunk 向量
- 适用: 包含代词、上下文依赖的查询

**Route: section_dense — 章节级语义检索**
- Capability: `SectionVectorSearch`
- Collection: `section_store`
- 适用: 主题探索，宽泛问题，需要了解某概念全貌
- 对齐: 结果需下钻到 Chunk 粒度

**Route: qa_dense — QA 对语义匹配**
- Capability: `QAVectorSearch`
- Collection: `atomic_qa_store`
- 适用: 问答型查询，直接匹配预生成的 QA 对
- 对齐: 通过 QA 元数据中的 chunk_id 溯源

**Route: summary_dense — 文档摘要级检索**
- Capability: `SummaryVectorSearch`
- Collection: `summary_store`
- 适用: 文档定位，宏观概览
- 对齐: Document → Section → Chunk 逐级下钻

#### 6.3.2 字面检索路由

**Route: bm25_sparse — BGE-M3 稀疏向量全文检索**
- Capability: `BM25Search`
- 后端: Milvus `chunk_store.sparse_vector` (IP 度量)
- 适用: 关键词匹配排序，弥补语义模型在专有名词上的缺陷

**Route: exact_match — 精确字面匹配**
- Capability: `ExactMatch`
- 后端: MongoDB `chunk_data` ($regex)
- 模式: EXACT / PREFIX / REGEX / FUZZY
- 适用: 专有名词、型号代码、公式符号、报错日志

**Route: boolean_search — 布尔逻辑检索**
- Capability: `BooleanSearch`
- 后端: MongoDB `chunk_data`
- 适用: 严格限定条件组合 `(A AND B) OR C NOT D`

#### 6.3.3 图谱检索路由（待实现）

**Route: graph_explore — 实体关系多跳探索**
- 后端: Neo4j
- 适用: 隐性关系、多跳推理、实体关联网络探查
- 对齐: 通过 Link 的 chunk_id 溯源到 Chunk

### 6.4 层次 3：补全工具能力（LLM₂ 工具箱）

这些能力**不参与初始多路召回**，而是在 LLM₂ 判定初始结果不充分时，按需调用。

**Tool: context_window — 上下文滑动窗口扩充**
- Capability: `ContextWindow`
- 触发: 结果文本截断、过渡句（"如上所述"）、信息不完整
- 操作: 获取同 Section 内锚点 Chunk 前后 ±K 个 Chunk
- 约束: 不跨越 Section 边界

**Tool: drill_down — 跨粒度下钻**
- Capability: `DrillDown`
- 触发: 需要更细粒度信息（如特定表格、图像 Element）
- 操作: Document → Section → Chunk → Element 逐级聚焦

**Tool: roll_up — 跨粒度上卷**
- Capability: `RollUp`
- 触发: 需要更宏观的上下文背景
- 操作: Chunk → Section → Document 逐级扩展

**Tool: skeleton — 文档骨架提取**
- Capability: `Skeleton`
- 触发: 需要了解文档整体结构以辅助二次定位
- 操作: 提取层级目录树 (section_id, title, level, chunk_count)

**Tool: re_retrieve — 二次召回**
- 触发: 初始结果严重不足或完全不相关
- 操作: 用修改后的 query 或不同路由组合重新走 Phase 2-5
- 约束: 最多触发 1 次，防止延迟失控

**Tool: graph_explore — 实体关系探索（待实现）**
- 触发: 需要补充隐性关联知识或验证实体关系
- 操作: 以实体为起点，N 度关联邻居探索

---

## 7. RetrieveService 接口设计

### 7.1 核心接口

```python
class RetrieveService:
    """检索编排服务 — 三阶段 Pipeline 的统一入口"""

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        """智能检索（完整 Pipeline）

        Phase 1: LLM₁ 路由规划
        Phase 2-5: 多路并行召回 → 跨粒度对齐 → RRF 融合 → Rerank
        Phase 6: LLM₂ 结果验证 + 自主补全
        """

    async def retrieve_single(
        self, capability_name: str, **kwargs
    ) -> RetrieveResult:
        """直接调用单个原子能力（旁路模式）"""

    async def retrieve_custom(
        self, routes: List[RouteConfig], query: str, filters: MetadataFilter, **kwargs
    ) -> RetrieveResponse:
        """自定义路由组合（跳过 LLM₁ 规划，直接执行 Phase 2-6）"""
```

### 7.2 请求/响应模型

```python
class RetrieveRequest(BaseModel):
    """检索请求"""
    query_text: str                                     # 查询文本
    filters: MetadataFilter = Field(default_factory=MetadataFilter)  # 元数据过滤
    top_k: int = 10                                     # 最终返回数量
    enable_rerank: bool = True                          # 是否启用 Reranker 精排
    enable_validation: bool = True                      # 是否启用 LLM₂ 结果验证
    route_hints: Optional[List[str]] = None             # 路由提示（可选，建议激活的路由）
    max_validation_rounds: int = 3                      # LLM₂ 最大工具调用轮数

class RetrieveResponse(BaseModel):
    """检索响应"""
    items: List[ChunkItem]                              # 最终结果列表
    total_count: int                                    # 结果总数
    route_plan: RoutePlan                               # LLM₁ 的路由计划（可审计）
    validation_result: ValidationResult                 # LLM₂ 的验证结果（可审计）
    execution_time_ms: float                            # 总耗时
    phase_timings: Dict[str, float]                     # 各阶段耗时明细
```

---

## 8. 典型检索工作流示例

### 8.1 场景一：精确技术参数查询

**Query**: "STM32G030C6 的 Flash 容量和最大主频是多少？"

**Phase 1 — LLM₁ 路由规划**:
```json
{
  "query_analysis": {
    "intent": "factual_qa",
    "key_entities": ["STM32G030C6", "Flash容量", "最大主频"],
    "contains_jargon": true,
    "reasoning": "包含精确的芯片型号，需要字面匹配 + 语义检索双保险"
  },
  "route_plan": [
    {"route": "exact_match", "top_k": 10, "params": {"keywords": ["STM32G030C6"], "match_mode": "fuzzy"}},
    {"route": "chunk_dense", "top_k": 20},
    {"route": "bm25_sparse", "top_k": 20},
    {"route": "qa_dense", "top_k": 10}
  ],
  "rerank_top_n": 30
}
```

**Phase 2-5**: 4 路并行 → 对齐 → RRF → Rerank，耗时 ~400ms

**Phase 6 — LLM₂ 验证**: 结果中包含完整的芯片参数表格 → **通过**，直接返回

**总耗时**: ~3s

### 8.2 场景二：主题探索 + 信息补全

**Query**: "请总结一下这篇论文中关于知识蒸馏的核心方法和实验结果"

**Phase 1 — LLM₁ 路由规划**:
```json
{
  "query_analysis": {
    "intent": "topic_exploration",
    "key_entities": ["知识蒸馏", "核心方法", "实验结果"],
    "reasoning": "主题探索型查询，涉及方法和实验两个维度，需要章节级入手再下钻"
  },
  "route_plan": [
    {"route": "section_dense", "top_k": 10},
    {"route": "enhanced_chunk_dense", "top_k": 30},
    {"route": "bm25_sparse", "top_k": 20}
  ],
  "rerank_top_n": 50
}
```

**Phase 2-5**: 3 路并行（Section 结果下钻到 Chunk）→ RRF → Rerank，耗时 ~500ms

**Phase 6 — LLM₂ 验证**:
- 发现结果集中覆盖了"方法"部分，但"实验结果"相关 Chunk 的表格被截断
- 调用 `context_window(chunk_id="exp_table_1", direction="next", window_size=2)` 获取后续表格数据
- 再次审视 → **通过**

**总耗时**: ~5s

### 8.3 场景三：跨文档对比分析

**Query**: "请对比分析 2025 年发布的内部架构白皮书中，关于分布式事务的两种新方案的性能数据"

**Phase 1 — LLM₁ 路由规划**:
```json
{
  "query_analysis": {
    "intent": "comparison",
    "key_entities": ["分布式事务", "性能数据", "架构白皮书"],
    "reasoning": "跨文档对比，需要先定位文档（摘要级），再聚焦到具体章节和数据"
  },
  "route_plan": [
    {"route": "summary_dense", "top_k": 5},
    {"route": "section_dense", "top_k": 15},
    {"route": "chunk_dense", "top_k": 30},
    {"route": "bm25_sparse", "top_k": 20},
    {"route": "exact_match", "top_k": 10, "params": {"keywords": ["分布式事务", "QPS", "延迟", "TPS"]}}
  ],
  "rerank_top_n": 60
}
```

**Phase 2-5**: 5 路并行（Summary → Section → Chunk 逐级下钻对齐）→ RRF → Rerank，耗时 ~700ms

**Phase 6 — LLM₂ 验证**:
- 发现结果涵盖了方案 A 的性能数据，但方案 B 的信息不足
- 调用 `re_retrieve(modified_query="方案B 分布式事务 性能对比", route_overrides=["chunk_dense", "bm25_sparse"], top_k=15)` 补充召回
- 补充结果合并后再次审视 → **通过**

**总耗时**: ~8s

---

## 9. 延迟预算与规模考量

### 9.1 百万级文档规模参数

| 指标 | 估算值 |
|------|--------|
| 文档数量 | ~100w |
| Chunk 总数 | ~500w-1000w |
| Milvus Collection 数量 | 5 (chunk / enhanced_chunk / section / qa / summary) |
| 单 Collection 最大向量数 | ~1000w (chunk_store) |
| 向量维度 | 1024 (Qwen3-embedding-0.6b) |
| 索引类型 | HNSW (COSINE) |

### 9.2 各阶段延迟预算

| 阶段 | 延迟 | 说明 |
|------|------|------|
| Phase 1: LLM₁ 路由规划 | 1-2s | 单次 LLM 调用，结构化输出 |
| Phase 2: 多路并行召回 | 50-200ms | Milvus HNSW 在千万向量规模下单次 ANN ~20-50ms |
| Phase 3: 跨粒度对齐 | 30-100ms | MySQL 关系查询 + in-memory 向量精排 |
| Phase 4: RRF 融合 | < 10ms | 纯内存计算 |
| Phase 5: Reranker | 200-500ms | bge-reranker-v2-m3，100 候选 |
| Phase 6: LLM₂ 验证 (通过) | 1-2s | 单次 LLM 调用 |
| Phase 6: LLM₂ 补全 (不通过) | 3-6s | LLM 判断 + 1-2 轮工具调用 |
| **总计 (通过)** | **~2-4s** | |
| **总计 (补全)** | **~5-9s** | |

### 9.3 成本控制策略

- LLM₁/LLM₂ 优先使用**轻量级模型**（如 GPT-4o-mini 或同等级别），路由规划和结果验证不需要最强推理能力
- LLM₂ 工具调用轮次硬上限为 3 轮，防止异常情况下延迟无限膨胀
- `re_retrieve` 工具最多调用 1 次，且走 Phase 2-5（不重新进入 Phase 1 和 Phase 6）

---

## 10. 实现路线图

### 10.1 已完成

- [x] 原子能力基类 `BaseCapability` + 模板方法模式
- [x] 语义检索能力: `ChunkVectorSearch`, `EnhancedChunkVectorSearch`, `SectionVectorSearch`, `QAVectorSearch`, `SummaryVectorSearch`
- [x] 字面检索能力: `BM25Search`, `ExactMatch`, `BooleanSearch`
- [x] 导航能力: `ContextWindow`, `DrillDown`, `RollUp`, `Skeleton`
- [x] 类型系统: `SemanticQuery`, `LexicalQuery`, `NavigationQuery`, `RetrieveResult`, 枚举定义
- [x] 基础设施: `EmbeddingClient`, `SparseEmbeddingClient`, Milvus Repositories

### 10.2 待实现

- [ ] **RetrieveService 编排层** — 核心 Pipeline 实现
  - [ ] LLM₁ 路由规划模块（prompt 工程 + 结构化输出解析）
  - [ ] 多路并行召回执行器
  - [ ] 跨粒度对齐模块（Section/QA/Summary → Chunk 下钻 + 二次精排）
  - [ ] RRF 融合 + 去重模块
  - [ ] LLM₂ 结果验证 Agent（prompt 工程 + function calling）
- [ ] **Reranker 客户端** — `src/client/reranker.py` 实现
- [ ] **ReRetrieve 工具** — 二次召回能力
- [ ] **HTTP API 路由** — `api/routers/knowledge/retrieve.py`
- [ ] **Graph 检索路由** — Neo4j 实体/关系检索 Capability
- [ ] **Knowledge Traceback** — 图谱到原文溯源 Capability
