# Agentic 知识库召回 Skills 设计

## 版本信息

- **版本号**: v1.0
- **创建日期**: 2026-02-28
- **设计目标**: 将传统的线性 RAG 召回流水线，升级为以 Agent 为核心、多粒度原子能力按需调用的动态知识获取体系。

## 1. 架构理念与转变

在传统的 RAG 架构中，检索通常是静态的、预定义的线性流程（如：用户 Query -> 多路召回(语义+BM25) -> 粗排 -> Reranker -> 知识图谱补充 -> 拼接入 Prompt）。这种模式对于复杂、多跳或需要探索性阅读的问题往往力不从心。

**Agentic 知识库召回的核心理念**是将检索能力下沉为一系列细粒度、专一化的 **Skills（原子能力）**。Agent 扮演**规划者**和**执行者**的角色，根据用户意图、数据库结构上下文以及阶段性检索结果，**自主决定**：
1. 生成何种查询语句（如 SQL、Cypher、BM25 Query）。
2. 调用哪个层级的检索接口（Element、Chunk、Section、Document 或是 Link）。
3. 组合使用哪些引擎（MySQL 元数据、Milvus 向量、Neo4j 图谱、ES 全文搜索）。
4. 是否需要顺藤摸瓜，进行上下文扩展或多跳推理。

通过将知识检索权和底层数据结构透传给 Agent，系统具备了“逐步求证（Step-by-step reasoning）”和“自我纠错”的能力。

---

## 2. 原子能力分层体系

为了让 Agent 能够精准地操控检索过程，我们将底层知识检索能力抽象为五个核心技能层。

### 2.1 结构化元数据查询层 (Metadata & SQL Skills)
基于关系型数据库 (MySQL) 和文档型数据库 (MongoDB)，Agent 可以直接以结构化查询的方式精确获取客观事实和骨架信息。

* **Skill 1: 精确属性与元数据检索 (Metadata Filter & SQL Query)**
  * **能力描述**: Agent 通过自主生成 SQL（或受限的 DSL），根据元数据进行精准过滤与匹配。
  * **适用场景**: 查询特定作者、特定时间范围、特定文件格式（如仅查 PDF）、特定页码或文件名的内容。
  * **输入示例**: `SELECT document_id FROM document_meta_info WHERE author = '张三' AND created_at > '2025-01-01'`
  
* **Skill 2: 文档骨架与目录提取 (Document Skeleton Extraction)**
  * **能力描述**: 不读取全文，仅通过查询 `text_level` 为 1/2/3 的 Element 或直接查询 `section_meta_info`，提取单篇或多篇文档的层级大纲。
  * **适用场景**: Agent 在深挖细节前，需要先纵览文档全貌，判断文档结构或决定后续阅读哪个章节。

* **Skill 3: 宏观统计与聚合洞察 (Aggregation & Statistics)**
  * **能力描述**: 对知识库中的元素进行聚合统计查询。
  * **适用场景**: 回答“这篇财报里有多少个数据表格？”或“关于项目A，库里共有多少份会议纪要？”。

### 2.2 语义向量检索层 (Semantic Vector Skills)
基于向量数据库 (Milvus) 及前台建立的三种不同 Embedding 策略，提供多维度、不同粒度的语义直觉召回。

* **Skill 4: 细粒度精准语义检索 (Base Chunk Retrieval)**
  * **能力描述**: 在基础 `chunk_store` 中检索。针对具体的问题或拆解后的 Sub-query，直接召回最相似的文本段落、图像 Chunk 或表格 Chunk。
  * **适用场景**: 事实性问答，精确定位单一知识点（如：“YOLOv5 的损失函数公式是什么？”）。

* **Skill 5: 上下文增强语义检索 (Enhanced Chunk Retrieval)**
  * **能力描述**: 在 `enhanced_chunk_embeddings` 中检索。此时的向量融合了 Section（章节标题）的背景语义，Agent 利用此能力处理容易产生歧义或指代不明的问题。
  * **适用场景**: 包含代词、强依赖上下文背景的查询（如：“该方法在测试集上的表现如何？”-> 增强向量包含“第3章 消融实验”背景）。

* **Skill 6: 宏观主题感知检索 (Macro Section/Topic Retrieval)**
  * **能力描述**: 在 `section_store` 中基于章节级别的向量进行检索，直接召回相关的完整章节（Section）信息及包含的 Chunk 列表。
  * **适用场景**: 探索性、宽泛性提问，需要了解一个大系统或大概念的全貌。

### 2.3 字面与关键词检索层 (Lexical & Keyword Skills)
基于全文检索引擎（如 Elasticsearch）或 BM25 算法，弥补语义模型在专有名词和长尾词上的缺陷。

* **Skill 7: 专有名词/代码字面精确匹配 (Exact Term/Code Match)**
  * **能力描述**: 跳过向量相似度计算，直接对 Token、特定参数名、日志代码片段、产品型号等进行字面精确匹配召回。
  * **适用场景**: 针对冷门专有名词（如某款特种芯片型号 `STM32G030C6`）或报错日志分析，避免语义检索泛化导致的幻觉。

* **Skill 8: 复杂布尔逻辑过滤 (Boolean Logic Search)**
  * **能力描述**: 允许 Agent 构造 `(A AND B) OR C NOT D` 类型的复杂查询。
  * **适用场景**: 用户给出明确且严格的限定条件组合。

### 2.4 知识图谱与逻辑推理层 (Graph & Reasoning Skills)
基于图数据库 (Neo4j) 中由 Chunk 抽取出的 SPO（Link/Node），进行结构化推理。

* **Skill 9: 实体关系多跳探索 (Multi-hop Entity Exploration)**
  * **能力描述**: 以某一实体（Node）为起点，查询其 1 度或 N 度关联的邻居节点和关系（Link）。Agent 可以借此顺藤摸瓜生成 Cypher 语句进行探查。
  * **适用场景**: 回答隐性关系或溯源问题，如“A 算法的改进版 B 算法，其核心作者还发表过哪些理论？”。

* **Skill 10: 路径发现与逻辑闭环 (Path Discovery)**
  * **能力描述**: 探索两个实体节点之间的连接路径。
  * **适用场景**: 揭示看似不相关的两个概念或业务组件之间的潜在联系。

* **Skill 11: 知识反向验证与溯源 (Knowledge Traceback)**
  * **能力描述**: 这是一个桥接能力。当 Agent 在图谱中拿到某个 Link (如 `(A, 依赖于, B)`) 时，利用关系属性中的 `chunk_id`，直接跳转查阅底层的原始文本 Chunk。
  * **适用场景**: 图谱信息过于简略时，Agent 回到原文进行事实核查和细节补充，防止过度脑补。

### 2.5 动态导航与上下文游走层 (Navigation & Context Walk Skills)
知识并非孤立存在，Agent 能够利用前台设计的从属与演化关系（Element -> Chunk -> Section -> Document），在不同粒度间自由穿梭。

* **Skill 12: 上下文自适应滑动扩充 (Context Sliding Window Expansion)**
  * **能力描述**: 当 Agent 评估当前召回的 Chunk（文本块）信息被截断或信息不足时，主动向左/向右滑动获取前后各 K 个 Chunk，或者直接请求获取该 Chunk 所在的完整 Section 内容。
  * **适用场景**: 发现一句话只说了一半，或者遇到“如上所述”、“接着前文的推导”等过渡句时。

* **Skill 13: 跨粒度下钻与聚焦 (Cross-granularity Drill-down)**
  * **能力描述**: Agent 从宏观开始（如通过 SQL 定位到一篇 Document，或通过 Topic 召回到一个 Section），逐步聚焦下钻，提取该范围内的所有图像 Elements 或特定的表格 Elements 进行深度阅读。
  * **适用场景**: “帮我对比一下这两篇论文中的所有实验结果表格。” -> 锁定两篇 Doc -> 提取所有 Table Element。

---

## 3. 典型 Agentic 检索工作流示例

传统的 RAG 是一步到底，而 Agentic 的召回是一个**循环探索**的过程：

**场景：用户提问“请对比分析 2025 年发布的内部架构白皮书中，关于分布式事务的两种新方案的性能数据。”**

1. **意图解析与规划**: 
   - Agent 判断该问题包含强元数据条件（2025年、内部架构白皮书），以及深度的语义对比需求。
2. **结构化查询 (Skill 1)**: 
   - Agent 生成 SQL，查询时间为 2025 年且标题包含“架构白皮书”的 `document_id`。
3. **宏观主题检索 (Skill 6)**: 
   - 携带过滤出的 `document_id` 作为限定范围，使用“分布式事务”查询 Section 向量，定位到《第4章：分布式事务新架构》及其 `section_id`。
4. **字面与语义结合下钻 (Skill 4 + Skill 7)**: 
   - Agent 发现需要“性能数据”，在目标 `section_id` 下，综合调用字面匹配（如查找“QPS”、“延迟”）和细粒度向量召回，重点提取包含相关数据的 Chunk 或表格 Element。
5. **图谱补充查漏 (Skill 9)**: 
   - 为了防止遗漏“两种新方案”的专有名称，Agent 调用图谱查询，以“分布式事务”为节点，查找“包含”关系的下级节点（如方案A、方案B）。
6. **信息评估与补全 (Skill 12)**: 
   - Agent 发现某个表格 Chunk 只有数据没有说明，触发上下文扩充技能，拉取该表格前后的文本 Chunk。
7. **综合回答生成**: 
   - Agent 汇总所有收集到的精准素材，生成高质量回复。