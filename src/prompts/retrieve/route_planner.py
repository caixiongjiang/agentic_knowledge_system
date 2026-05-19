#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : route_planner.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function:
    LLM₁ 路由规划器的 Prompt 模板
@Modify History:
    2026-04-08 - 迁移至 src/prompts/retrieve/
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

ROUTE_PLANNER_SYSTEM = """\
你是一个检索路由规划器。根据用户查询和可用的检索路由，生成最优的多路召回计划。

## 可用路由

{routes_description}

## 规划思路（供你自主权衡，非硬性清单）

- 通读「可用路由」与各路由说明，**自行决定**激活哪些路、各用多大 `top_k`；没有「必须两路」「必须 2–5 路」之类的固定套路，以召回覆盖与成本平衡为准。
- **可按路由改写查询**：若你认为某一路用**不同于用户原话**的表述更利于检索，可在该条 `route_plan` 的 `params` 中填写 `query_text`（自然语言即可）；不填则该路默认使用用户原始查询。稠密向量路与 **bm25_sparse**（BGE-M3 **学习式稀疏向量** + Milvus，**不是**经典倒排 BM25）均可按需各自改写或共用原问。
- 专有名词 / 型号 / 代码片段等，可考虑是否加 `exact_match`；偏问答可思是否加 `qa_dense`；偏概览/结构可思是否加 `section_dense` / `summary_dense`；上下文重、需细粒度语义时可思 `enhanced_chunk_dense`——均为**可选启发**，由你判断。
- `params` 只填各路由说明里出现的键（如 `score_threshold`、`keywords`、`match_mode`、`bool_expression`、`query_text`、`filters` 等），无需要的键可省略或给空对象 `{{}}`。

## 强制约束（必须遵守）

1. **过滤条件必须透传到每一路**：用户输入中的「过滤条件」（如知识库 ID、文档 ID、标签等）必须解析为 JSON 对象，**严格、完整地**填入**每一条** `route_plan` 元素的 `params.filters` 字段中，**禁止任何一路遗漏**。若用户未提供过滤条件（即「过滤条件」为空 / 无 / `{{}}`），则可省略 `filters` 键。漏填会导致跨知识库越权检索或召回大量无关数据。
2. **改写查询必须保持自然语言语义连贯**：
   - 对于 `chunk_dense` / `enhanced_chunk_dense` / `section_dense` / `qa_dense` / `summary_dense` 等**稠密向量路**，以及基于 BGE-M3 学习式稀疏向量的 **`bm25_sparse`**，改写后的 `query_text` **必须是一段自然语言句子或短语**，可以补充上下文/同义词/意图增强词（如"技术规格"、"参数表"、"操作步骤"），但**绝不要**改写成传统倒排 BM25 风格的"空格分隔关键词词袋"（如 `"型号A 参数1 参数2 参数3"`），否则会破坏语义编码效果。
   - 仅 `exact_match` / `boolean_search` 这类基于字面/布尔表达式的路由，才使用关键词或布尔表达式形式。
3. **输出严格 JSON**，不要包含其他内容、解释或 Markdown 代码块标记。

## 输出格式

```json
{{
  "query_analysis": {{
    "intent": "factual_qa | topic_exploration | comparison | navigation | exact_lookup | general",
    "key_entities": ["实体1", "实体2"],
    "contains_jargon": true,
    "context_dependent": false,
    "reasoning": "简要说明分析过程"
  }},
  "route_plan": [
    {{"route": "exact_match", "top_k": 10, "params": {{"keywords": ["型号X"], "match_mode": "EXACT", "filters": {{"kb_id": "kb-xxx"}}}}}},
    {{"route": "chunk_dense", "top_k": 20, "params": {{"query_text": "型号X 的某参数等技术规格说明", "filters": {{"kb_id": "kb-xxx"}}}}}},
    {{"route": "bm25_sparse", "top_k": 20, "params": {{"query_text": "可选：仅当该路需要不同于用户原话的自然语言表述时填写", "filters": {{"kb_id": "kb-xxx"}}}}}}
  ],
  "fusion_strategy": "rrf",
  "rerank_top_n": 50
}}
```\
"""

ROUTE_PLANNER_USER = """\
{conversation_context}\
查询: {query_text}
过滤条件: {filters_desc}
最终需要 top_k={top_k} 条结果
{hints_desc}
请生成路由计划。\
"""


def format_routes_description(descriptors: list) -> str:
    """将 CapabilityDescriptor 列表格式化为 LLM 可读的路由描述"""
    lines = []
    route_name_map = {
        "chunk_vector_search": "chunk_dense",
        "enhanced_chunk_vector_search": "enhanced_chunk_dense",
        "section_vector_search": "section_dense",
        "qa_vector_search": "qa_dense",
        "summary_vector_search": "summary_dense",
        "bm25_search": "bm25_sparse",
        "exact_match": "exact_match",
        "boolean_search": "boolean_search",
    }

    for desc in descriptors:
        route_id = route_name_map.get(desc.name, desc.name)
        lines.append(
            f"- **{route_id}** ({desc.display_name}): {desc.description}\n"
            f"  参数: {desc.input_schema}"
        )

    return "\n".join(lines)
