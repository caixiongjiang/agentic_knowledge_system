<div align="center">

# Agentic Knowledge System: Agentic, Traceable RAG over Real Documents

<p align="center"><b>Multi-Granularity Indexing&nbsp; ◦ &nbsp;LLM-Routed Retrieval&nbsp; ◦ &nbsp;Agentic Chat with Tools&nbsp; ◦ &nbsp;Bbox Source Tracing</b></p>

<h4 align="center">
  <a href="./docs/组件策略设计/文档解析设计.md">📖 解析设计</a>&nbsp; • &nbsp;
  <a href="./docs/组件策略设计/检索溯源方案设计.md">📖 溯源设计</a>&nbsp; • &nbsp;
  <a href="./docs/通用文件和工作空间文件知识库/通用文件索引高性能架构设计.md">📖 索引架构</a>&nbsp; • &nbsp;
  <a href="./docs/通用文件和工作空间文件知识库/通用文件多路检索召回设计.md">📖 检索召回</a>&nbsp; • &nbsp;
  <a href="./docs/特殊功能设计/知识库对话设计.md">📖 对话设计</a>
</h4>

</div>

---

# 📑 Introduction

`agentic_knowledge_system`（AKS）是一个面向**真实长文档**的 Agentic 知识库与 RAG 后端引擎。它把一份文档拆成「页 → section → chunk → 元素」多级结构，对每一级分别建索引（向量 / 摘要 / 原子问答 / 知识图谱），检索时由 LLM₁ 先做**路由规划**，再并行多路召回、跨粒度对齐、融合、重排，最后把答案连同**可溯源的 bbox** 一起返回。对话层基于 WebSocket 流式输出，并给 LLM 一组**知识库操作工具**（钻取 / 上卷 / 骨架 / 上下文窗口 / 全文检索 / 读图），让它像人类专家一样在文档里“翻页查证”。

整个索引链路由 Kafka 驱动、完全异步：上传 → 解析 → 切分 → 两级摘要 → 原子问答 / 知识图谱 → 多库写入，每一步都是独立 Worker，可独立扩缩。

### 🎯 Core Features

> 一个把“解析—索引—检索—对话—溯源”打通的 Agentic RAG 后端，强调多粒度、可解释、可溯源。

- **多格式解析**：PDF / PPT / Word 经 LibreOffice 转 PDF 后走 MinerU 2.0，保留真实 bbox；JSON / CSV 内联解析；Excel / TXT / Markdown / 图片为 stub。
- **多粒度索引**：chunk 向量、section 向量、section 摘要、file 摘要、atomic QA、知识图谱（SPO / Tag）分别落 Milvus 不同集合，自底向上两级摘要。
- **LLM 路由检索**：LLM₁ 规划路由 → 并行多路召回（语义 6 路 + 词法 3 路 + 导航 4 路）→ 跨粒度对齐 → 融合 → Rerank；高置信 atomic QA 直答短路。
- **Agentic 对话**：WebSocket 流式 + 会话管理 + 模型选择器；LLM 可调用 `search_knowledge_base` / `drill_down` / `roll_up` / `skeleton` / `context_window` / `grep_chunks` / `read_image_chunks` / `skills` 等工具自主查证。
- **bbox 溯源**：Word/PPT 转换 PDF 持久化到 MinIO，`/raw` `/preview` 默认下发转换 PDF，前端按 MinerU 0~1000 归一化坐标叠加高亮框。
- **Skill 技能系统**：可声明式注册的复用提示/工具集，对话中通过 `@skill` 调用。
- **统一模型网关**：所有 LLM / Embedding / Reranker 走 self-hosted LiteLLM Proxy，多 provider（OpenAI / DeepSeek / GLM / Qwen / Gemini / Anthropic …）统一路由、统一计费。

### 🛠️ Deployment Options

- **本地开发**：`uv run python main.py`（API）+ `uv run python scripts/start_all_workers.py`（Workers），依赖本地 / 远程的 Milvus / MongoDB / MySQL / Redis / Kafka / MinIO / MinerU / LiteLLM Proxy。
- **Docker Compose**：`docker compose up -d aks-api aks-workers`（见 `docker-compose.yml`，复用外部已建好的基础设网络）。
- **生产**：API 与 Workers 分进程部署，Kafka 消费组按 `KAFKA_GROUP_ID_PREFIX` 隔离 dev/prod，数据 namespace 由 `APP_ENV` 决定（`dev_*` / `default`）。

---

# 🌲 System Architecture

```
                        ┌──────────────────────── FastAPI (main.py, :8000) ─────────────────────────┐
                        │  /api/knowledge/*  (base/index/folder/file/chunk/trash/retrieve)            │
                        │  /api/chat/*       (sessions/models/ws)                                     │
                        └────────────────────────────────────────────────────────────────────────────┘
                                              │  上传 → Kafka(index.start)  │  检索/对话 → 同步 Pipeline
                                              ▼                            ▼
   ┌─────────────────────── Kafka 异步索引链路（10 个 Worker）─────────────────────┐   ┌──── 同步检索 Pipeline ────┐
   │ file_parser → text_splitter → section_summary → file_summary                   │   │ LLM₁ RoutePlanner         │
   │                                                    ├─► text_analyzer (atomic_qa)    │   │   ↓ ParallelRecall (6+3+4)│
   │                                                    └─► kg_extractor (SPO/Tag)       │   │   ↓ GranularityAlign     │
   │   DB Writers: embedding_milvus / neo4j / mysql / mongo                           │   │   ↓ Fusion → Rerank      │
   └──────────────────────────────────────────────────────────────────────────────────┘   └───────────────────────────┘
                                              │                                                    │
   ┌──── Milvus ────┐ ┌── MongoDB ──┐ ┌── MySQL ──┐ ┌── Neo4j ──┐ ┌── Redis ──┐ ┌── MinIO ──────────────────────┐
   │ chunk/section/  │ │ element/   │ │ kb/folder/│ │ KG(SPO/  │ │ 进度/缓存 │ │ 原始文件 + 转换 PDF(溯源)      │
   │ summary/qa/kg  │ │ chunk/section│ │ file 元数据│ │ tag)     │ │           │ │                               │
   │ 向量集合        │ │ 文档数据     │ │           │ │           │ │           │ │                               │
   └────────────────┘ └────────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────────────────────────┘
```

### 目录结构

```
agentic_knowledge_system/
├── main.py                          # FastAPI 入口（uvicorn :8000）
├── api/                             # API 层
│   ├── routers/                     # knowledge / chat 路由
│   ├── schemas/                     # 请求/响应模型
│   ├── dependencies/               # 鉴权 / DB 会话
│   └── middlewares/                  # CORS / 错误处理 / 日志
├── src/
│   ├── index/common_file_extract/   # 解析与切分
│   │   ├── parser/                  # base_parser / pdf / ppt / word / excel / txt / md / image
│   │   ├── splitter/                # 结构优先切分 + 表格切分
│   │   └── extract/                 # file/section 摘要、atomic QA、section tree
│   ├── retrieve/                   # 检索引擎
│   │   ├── planner/                 # LLM₁ 路由规划
│   │   ├── capabilities/            # semantic / lexical / navigation 各路召回
│   │   └── pipeline/                # parallel_recall / alignment / fusion / rerank
│   ├── service/                     # 业务编排
│   │   ├── knowledge/               # index / query / retrieve / move / delete / preview
│   │   ├── chat/                    # 会话 / 标题 / chunk enrich / tools
│   │   ├── memory/                  # Memory 知识库
│   │   └── skill/                   # 技能注册
│   ├── client/                      # mineru / llm(LiteLLM) / embedding(BGE-M3) / reranker
│   └── db/                          # milvus / mongodb / mysql / neo4j / redis / kafka / storage(MinIO)
├── config/                          # config.toml / components.json / 模型白名单
├── scripts/                         # start_all_workers.py + 各 DB 管理脚本
├── docs/                            # 设计文档（见下方 Resources）
└── docker-compose.yml               # aks-api + aks-workers
```

<details>
<summary>检索路由一览（semantic / lexical / navigation）</summary>

- **语义（Milvus 向量）**：`chunk_vector` / `enhanced_chunk_vector` / `section_vector` / `section_summary_vector` / `file_summary_vector` / `qa_vector`
- **词法**：`bm25_search` / `boolean_search` / `exact_match`
- **导航**：`context_window` / `drill_down` / `roll_up` / `skeleton`

</details>

---

# ⚙️ Quick Start

### 1. 安装依赖

```bash
# 需要 Python ≥ 3.13
uv sync
```

### 2. 配置环境

```bash
cp .env.example .env
# 填写 Milvus / MongoDB / MySQL / Redis / Kafka / MinIO / MinerU / LiteLLM Proxy 连接信息
```

`config/config.toml` 控制各组件参数（Milvus 索引类型、切分配置、Kafka batch 等）；`config/components.json` 控制每个索引组件的开关与 LLM preset。

### 3. 启动 API 与 Workers

```bash
# 终端 A：FastAPI（:8000）
uv run python main.py

# 终端 B：Kafka Workers（10 个：6 任务流转 + 4 DB 写入）
uv run python scripts/start_all_workers.py

# 只启动部分 Worker
uv run python scripts/start_all_workers.py --workers file_parser,text_splitter,embedding_milvus_writer
```

<details>
<summary>运行环境外部依赖</summary>

- **MinerU 2.0**：PDF / PPT / Word 解析（`MINERU_API_URL`）
- **LibreOffice**：Word / PPT 转 PDF（`soffice`，Docker 镜像需 `apt-get install libreoffice`）
- **LiteLLM Proxy**：统一 LLM / Embedding / Reranker 网关（`LITELLM_PROXY_URL`）
- **BGE-M3**：稀疏向量 Embedding（`SPARSE_EMBEDDING_API_BASE`，可选）
- **基础设施**：Milvus / MongoDB / MySQL / Redis / Kafka / MinIO / Neo4j

</details>

<details>
<summary>Docker 部署</summary>

```bash
docker compose up -d aks-api aks-workers
```

`docker-compose.yml` 假设基础设（mysql/mongodb/redis/kafka/milvus/neo4j/logto/litellm/bge-m3/vllm）已在外部网络就绪，AKS 仅起 API 与 Workers 两个容器。

</details>

---

# 🚀 Agentic Chat: An Example

对话通过 WebSocket 流式进行，LLM 在回答过程中可自主调用知识库工具查证：

```
ws://<host>:8000/api/chat/ws?token=<user_id>

Client → { type: "start", message: "...", knowledge_base_id: "..." }
Server → { type: "token", ... } / { type: "tool_call", name: "drill_down", ... } /
         { type: "citation", chunk_id: "...", page_index: 3, bbox: [...] } / { type: "done" }
```

可用工具：`search_knowledge_base` · `read_chunks` · `drill_down` · `roll_up` · `skeleton` · `context_window` · `grep_chunks` · `read_image_chunks` · `skills`（见 `src/service/chat/tools/handlers/`）。

---

# 📚 Resources

设计文档（`docs/`）：

- **组件策略设计**：[文档解析设计](docs/组件策略设计/文档解析设计.md) · [检索溯源方案设计](docs/组件策略设计/检索溯源方案设计.md) · [文本分块设计](docs/组件策略设计/文本分块设计.md)
- **通用文件知识库**：[索引高性能架构](docs/通用文件和工作空间文件知识库/通用文件索引高性能架构设计.md) · [多路检索召回](docs/通用文件和工作空间文件知识库/通用文件多路检索召回设计.md) · [高级语义索引召回](docs/通用文件和工作空间文件知识库/通用文件高级语义索引召回设计.md) · [多数据源格式适配](docs/通用文件和工作空间文件知识库/通用文件多数据源格式适配设计.md) · [工作空间与 Agent 交互](docs/通用文件和工作空间文件知识库/工作空间与agent交互设计.md) · [召回 Skills 设计](docs/通用文件和工作空间文件知识库/Agentic知识库召回Skills设计.md)
- **Memory 知识库**：[memory 与上下文工程](docs/memory知识库/memory与上下文工程设计.md) · [高性能架构](docs/memory知识库/memory索引高性能架构设计.md) · [高级语义检索召回](docs/memory知识库/memory高级语义检索召回设计.md) · [多消息类型适配](docs/memory知识库/memory多消息类型适配设计.md) · [memory 工具设计](docs/memory知识库/memory工具设计.md)
- **特殊功能**：[知识库对话设计](docs/特殊功能设计/知识库对话设计.md) · [Skill 技能系统](docs/特殊功能设计/Skill技能系统设计方案.md) · [PDF 文件翻译](docs/特殊功能设计/pdf文件翻译设计.md)
- **运维**：[回收站删除恢复逻辑](docs/API设计/回收站删除恢复逻辑.md) · [Scripts 目录](scripts/README.md) · [Splitter 模块](src/index/common_file_extract/splitter/README.md)

---

# 🧭 Tech Stack

| 层 | 选型 |
|---|---|
| API | FastAPI · uvicorn · Pydantic v2 |
| 异步管线 | Kafka（aiokafka）· 10 个 Worker |
| 向量库 | Milvus（HNSW / COSINE，1024 维，多集合） |
| 文档库 | MongoDB（element / chunk / section / document） |
| 关系库 | MySQL（知识库 / 文件夹 / 文件元数据） |
| 图库 | Neo4j（知识图谱 SPO / Tag） |
| 缓存/进度 | Redis |
| 对象存储 | MinIO（原始文件 + 转换 PDF） |
| 解析 | MinerU 2.0 · LibreOffice · pypdf |
| 模型网关 | LiteLLM Proxy（多 LLM）· BGE-M3（稀疏向量）· vLLM Reranker |
| Python | ≥ 3.13 · uv |

---

## 作者

蔡雄江 - 全栈开发工程师 · AI 架构师

## 许可证

见 [LICENSE](LICENSE)。
