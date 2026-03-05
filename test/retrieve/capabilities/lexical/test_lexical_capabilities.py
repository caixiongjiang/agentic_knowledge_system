#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_lexical_capabilities.py
@Author  : caixiongjiang
@Date    : 2026/03/04
@Function: 
    lexical 检索能力效果测试

    分为三部分:
    Part 1 — BooleanExpressionParser 纯逻辑测试（无外部依赖）
        验证 AST 解析正确性、运算符优先级、括号嵌套、特殊字符处理，
        以及生成的 MongoDB 查询是否符合预期。

    Part 2 — BM25Search 端到端效果测试（需要 Milvus + BGE-M3 服务）
        在真实 Milvus 中插入带稀疏向量的测试文档，
        验证稀疏向量检索的排序质量、关键词敏感性和过滤功能。

    Part 3 — ExactMatch 正则构建逻辑测试（无外部依赖）
        验证各种 MatchMode 下生成的正则表达式是否符合预期。

@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import asyncio
import sys
import time
import uuid
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.retrieve.capabilities.lexical.boolean_search import (
    BooleanExpressionParser,
    TermNode, AndNode, OrNode, NotNode,
)
from src.retrieve.capabilities.lexical.exact_match import ExactMatch
from src.retrieve.types.enums import MatchMode


# ======================================================================
#  Part 1: BooleanExpressionParser 纯逻辑测试
# ======================================================================


class BooleanParserTests:
    """布尔表达式解析器效果测试

    不依赖 MongoDB，仅验证:
    - AST 结构正确性
    - 生成的 MongoDB 查询语义正确
    - 运算符优先级和括号处理
    - 边界情况和错误处理
    """

    def __init__(self) -> None:
        self.parser = BooleanExpressionParser()
        self.passed = 0
        self.failed = 0

    def _assert(self, condition: bool, msg: str) -> None:
        if condition:
            self.passed += 1
            print(f"    通过: {msg}")
        else:
            self.failed += 1
            print(f"    失败: {msg}")

    def run_all(self) -> None:
        print("=" * 80)
        print("Part 1: BooleanExpressionParser 纯逻辑测试")
        print("=" * 80)
        print()

        self.test_single_term()
        self.test_and_expression()
        self.test_or_expression()
        self.test_not_expression()
        self.test_operator_precedence()
        self.test_parentheses_grouping()
        self.test_nested_complex_expression()
        self.test_quoted_string()
        self.test_mongo_query_structure()
        self.test_real_world_expressions()
        self.test_error_handling()

        print()
        print(f"  结果汇总: 通过 {self.passed}, 失败 {self.failed}")
        print()

    def test_single_term(self) -> None:
        """单个关键词"""
        print("  测试 1.1: 单个关键词")
        ast = self.parser.parse("Transformer")
        self._assert(isinstance(ast, TermNode), "解析为 TermNode")
        self._assert(ast.keyword == "Transformer", "关键词正确")

        query = ast.to_mongo_query()
        self._assert("text" in query, "MongoDB 查询包含 text 字段")
        self._assert("$regex" in query["text"], "使用 $regex 匹配")
        print()

    def test_and_expression(self) -> None:
        """AND 表达式"""
        print("  测试 1.2: AND 表达式")
        ast = self.parser.parse("深度学习 AND 图像识别")
        self._assert(isinstance(ast, AndNode), "解析为 AndNode")
        self._assert(isinstance(ast.left, TermNode), "左子节点为 TermNode")
        self._assert(isinstance(ast.right, TermNode), "右子节点为 TermNode")
        self._assert(ast.left.keyword == "深度学习", "左关键词正确")
        self._assert(ast.right.keyword == "图像识别", "右关键词正确")

        query = ast.to_mongo_query()
        self._assert("$and" in query, "MongoDB 查询使用 $and")
        self._assert(len(query["$and"]) == 2, "$and 包含两个条件")
        print()

    def test_or_expression(self) -> None:
        """OR 表达式"""
        print("  测试 1.3: OR 表达式")
        ast = self.parser.parse("CNN OR RNN")
        self._assert(isinstance(ast, OrNode), "解析为 OrNode")

        query = ast.to_mongo_query()
        self._assert("$or" in query, "MongoDB 查询使用 $or")
        print()

    def test_not_expression(self) -> None:
        """NOT 表达式"""
        print("  测试 1.4: NOT 表达式")
        ast = self.parser.parse("NOT 入门教程")
        self._assert(isinstance(ast, NotNode), "解析为 NotNode")
        self._assert(isinstance(ast.child, TermNode), "子节点为 TermNode")

        query = ast.to_mongo_query()
        self._assert("text" in query, "MongoDB 查询包含 text 字段")
        self._assert("$not" in query["text"], "使用 $not 取反")
        print()

    def test_operator_precedence(self) -> None:
        """运算符优先级: NOT > AND > OR"""
        print("  测试 1.5: 运算符优先级 (NOT > AND > OR)")

        ast = self.parser.parse("A AND B OR C")
        self._assert(isinstance(ast, OrNode), "A AND B OR C → 顶层为 OR")
        self._assert(isinstance(ast.left, AndNode), "左子树为 AND(A, B)")

        ast2 = self.parser.parse("A OR NOT B AND C")
        self._assert(isinstance(ast2, OrNode), "A OR NOT B AND C → 顶层为 OR")
        right = ast2.right
        self._assert(isinstance(right, AndNode), "右子树为 AND(NOT B, C)")
        self._assert(isinstance(right.left, NotNode), "AND 左子节点为 NOT")
        print()

    def test_parentheses_grouping(self) -> None:
        """括号分组改变优先级"""
        print("  测试 1.6: 括号分组")

        ast = self.parser.parse("(A OR B) AND C")
        self._assert(isinstance(ast, AndNode), "(A OR B) AND C → 顶层为 AND")
        self._assert(isinstance(ast.left, OrNode), "左子树为 OR(A, B)")
        self._assert(isinstance(ast.right, TermNode), "右子树为 TermNode(C)")

        ast2 = self.parser.parse("A AND (B OR C)")
        self._assert(isinstance(ast2, AndNode), "A AND (B OR C) → 顶层为 AND")
        self._assert(isinstance(ast2.right, OrNode), "右子树为 OR(B, C)")
        print()

    def test_nested_complex_expression(self) -> None:
        """复杂嵌套表达式"""
        print("  测试 1.7: 复杂嵌套表达式")

        expr = "(YOLO AND 实时检测) OR (SSD AND NOT 低精度)"
        ast = self.parser.parse(expr)
        self._assert(isinstance(ast, OrNode), f"'{expr}' → 顶层为 OR")
        self._assert(isinstance(ast.left, AndNode), "左子树为 AND")
        self._assert(isinstance(ast.right, AndNode), "右子树为 AND")
        self._assert(isinstance(ast.right.right, NotNode), "右子树的右节点为 NOT")

        query = ast.to_mongo_query()
        self._assert("$or" in query, "MongoDB 查询结构正确: $or 在顶层")
        print()

    def test_quoted_string(self) -> None:
        """引号包裹的多词关键词"""
        print("  测试 1.8: 引号包裹多词关键词")

        ast = self.parser.parse('"deep learning" AND "image classification"')
        self._assert(isinstance(ast, AndNode), "解析为 AndNode")
        self._assert(ast.left.keyword == "deep learning", "左关键词含空格")
        self._assert(ast.right.keyword == "image classification", "右关键词含空格")
        print()

    def test_mongo_query_structure(self) -> None:
        """验证生成的 MongoDB 查询可以正确表达业务语义"""
        print("  测试 1.9: MongoDB 查询语义验证")

        import re

        expr = "Transformer AND Attention AND NOT 入门"
        ast = self.parser.parse(expr)
        query = ast.to_mongo_query()

        def _query_matches_text(q: dict, text: str) -> bool:
            """简易模拟 MongoDB $regex 匹配"""
            if "$and" in q:
                return all(_query_matches_text(sub, text) for sub in q["$and"])
            if "$or" in q:
                return any(_query_matches_text(sub, text) for sub in q["$or"])
            if "$nor" in q:
                return not any(_query_matches_text(sub, text) for sub in q["$nor"])
            if "text" in q:
                text_cond = q["text"]
                if "$not" in text_cond:
                    inner = text_cond["$not"]
                    pattern = inner.get("$regex", "")
                    flags = re.IGNORECASE if "i" in inner.get("$options", "") else 0
                    return not bool(re.search(pattern, text, flags))
                pattern = text_cond.get("$regex", "")
                flags = re.IGNORECASE if "i" in text_cond.get("$options", "") else 0
                return bool(re.search(pattern, text, flags))
            return False

        should_match = "Transformer使用Self-Attention机制实现并行计算"
        should_not_match_1 = "CNN是经典的图像处理模型"
        should_not_match_2 = "Transformer入门教程：从零开始学习Attention"

        self._assert(
            _query_matches_text(query, should_match),
            f"应匹配: '{should_match}'"
        )
        self._assert(
            not _query_matches_text(query, should_not_match_1),
            f"不应匹配（缺少关键词）: '{should_not_match_1}'"
        )
        self._assert(
            not _query_matches_text(query, should_not_match_2),
            f"不应匹配（含 NOT 词）: '{should_not_match_2}'"
        )
        print()

    def test_real_world_expressions(self) -> None:
        """真实业务场景的布尔表达式"""
        print("  测试 1.10: 真实业务场景表达式")

        expressions = [
            ("LLM AND RAG AND 知识库", "知识库问答场景"),
            ("(向量检索 OR 全文检索) AND Milvus", "检索方案选型"),
            ("Agent AND NOT 游戏 AND 基础设施", "Agent 架构文档"),
            ('(BERT OR GPT OR "T5模型") AND 微调', "模型微调文档"),
            ("Kubernetes AND (部署 OR 运维) AND NOT 入门", "K8s 运维进阶"),
        ]

        for expr, desc in expressions:
            try:
                ast = self.parser.parse(expr)
                query = ast.to_mongo_query()
                self._assert(True, f"场景 '{desc}': 表达式解析成功")
            except Exception as e:
                self._assert(False, f"场景 '{desc}': 解析失败 - {e}")
        print()

    def test_error_handling(self) -> None:
        """错误处理"""
        print("  测试 1.11: 错误处理")

        error_cases = [
            ("AND", "孤立的 AND"),
            ("(A AND B", "未闭合的括号"),
            ("A AND", "尾部悬挂 AND"),
        ]

        for expr, desc in error_cases:
            try:
                self.parser.parse(expr)
                self._assert(False, f"应该报错: {desc} → '{expr}'")
            except (ValueError, Exception):
                self._assert(True, f"正确报错: {desc} → '{expr}'")
        print()


# ======================================================================
#  Part 2: BM25Search 端到端效果测试（Milvus + BGE-M3）
# ======================================================================


TEST_PREFIX = f"bm25_test_{uuid.uuid4().hex[:6]}"

CORPUS = [
    {
        "id": f"{TEST_PREFIX}_001",
        "text": "Transformer模型使用自注意力机制实现序列到序列的建模，在NLP任务中取得了突破性成果",
        "topic": "NLP",
    },
    {
        "id": f"{TEST_PREFIX}_002",
        "text": "BERT是一种基于Transformer的预训练语言模型，通过双向编码器实现上下文理解",
        "topic": "NLP",
    },
    {
        "id": f"{TEST_PREFIX}_003",
        "text": "知识图谱通过三元组（实体-关系-实体）结构化地表示领域知识",
        "topic": "KG",
    },
    {
        "id": f"{TEST_PREFIX}_004",
        "text": "向量数据库如Milvus使用HNSW和IVF索引加速近似最近邻搜索",
        "topic": "VectorDB",
    },
    {
        "id": f"{TEST_PREFIX}_005",
        "text": "RAG检索增强生成通过外部知识库降低大语言模型的幻觉问题",
        "topic": "RAG",
    },
    {
        "id": f"{TEST_PREFIX}_006",
        "text": "卷积神经网络CNN在图像分类和目标检测任务中表现优异",
        "topic": "CV",
    },
    {
        "id": f"{TEST_PREFIX}_007",
        "text": "强化学习Agent通过与环境交互获得奖励信号来学习最优策略",
        "topic": "RL",
    },
    {
        "id": f"{TEST_PREFIX}_008",
        "text": "注意力机制允许模型在处理序列时动态关注最相关的部分",
        "topic": "NLP",
    },
    {
        "id": f"{TEST_PREFIX}_009",
        "text": "稀疏检索利用词频统计特征进行关键词匹配，BM25是经典算法",
        "topic": "IR",
    },
    {
        "id": f"{TEST_PREFIX}_010",
        "text": "多模态大模型可以同时处理文本、图像、音频等多种数据类型",
        "topic": "Multimodal",
    },
]

QUERY_SCENARIOS = [
    {
        "name": "精确关键词匹配",
        "query": "Transformer自注意力机制",
        "expected_top_ids": [f"{TEST_PREFIX}_001", f"{TEST_PREFIX}_008"],
        "description": "查询包含 Transformer 和 注意力机制 两个关键词，应优先命中文档 001 和 008",
    },
    {
        "name": "领域专有术语",
        "query": "向量数据库Milvus HNSW索引",
        "expected_top_ids": [f"{TEST_PREFIX}_004"],
        "description": "查询包含非常具体的技术术语，应精准命中文档 004",
    },
    {
        "name": "宽泛语义查询",
        "query": "深度学习模型",
        "expected_top_ids": [],
        "description": "宽泛查询，稀疏检索可能命中多个文档，观察排序是否合理",
    },
    {
        "name": "跨领域查询",
        "query": "BM25稀疏检索关键词匹配",
        "expected_top_ids": [f"{TEST_PREFIX}_009"],
        "description": "直接查询 BM25 相关内容，应命中文档 009",
    },
]


async def run_bm25_e2e_tests() -> None:
    """BM25Search 端到端效果测试"""
    print("=" * 80)
    print("Part 2: BM25Search 端到端效果测试 (Milvus + BGE-M3)")
    print("=" * 80)
    print()

    try:
        from src.client.embedding import create_sparse_embedding_client, create_embedding_client
        from src.db.milvus.connection.factory import get_milvus_manager, reset_manager
        from src.db.milvus.repositories.base.chunk_repository import ChunkRepository
        from src.retrieve.capabilities.lexical.bm25_search import BM25Search
        from src.retrieve.types.query import LexicalQuery, MetadataFilter
    except ImportError as e:
        print(f"  跳过: 依赖不满足 — {e}")
        return

    import os
    os.environ["MILVUS_AUTO_CREATE_COLLECTION"] = "true"

    repo: Optional[ChunkRepository] = None
    inserted_ids: List[str] = []

    try:
        # 1. 初始化基础设施
        print("  [准备] 初始化 Milvus 连接和 BGE-M3 客户端...")
        reset_manager()
        milvus_manager = get_milvus_manager()
        print(f"    Milvus 连接: {type(milvus_manager).__name__}")

        if not milvus_manager.check_connection():
            print("    Milvus 连接失败，终止测试")
            return

        repo = ChunkRepository(manager=milvus_manager)
        sparse_client = create_sparse_embedding_client()
        dense_client = create_embedding_client()
        bm25_search = BM25Search(
            milvus_manager=milvus_manager,
            sparse_embedding_client=sparse_client,
        )

        # 2. 准备测试数据 — 生成稠密向量 + 稀疏向量
        print(f"  [准备] 为 {len(CORPUS)} 条文档生成向量...")
        texts = [doc["text"] for doc in CORPUS]

        with dense_client:
            dense_vectors = dense_client.embed_batch(texts)
        with sparse_client:
            sparse_vectors = sparse_client.embed_sparse_batch(texts)

        print(f"    稠密向量维度: {len(dense_vectors[0])}")
        sparse_dims = [len(sv) for sv in sparse_vectors]
        print(
            f"    稀疏向量非零维度: min={min(sparse_dims)}, "
            f"max={max(sparse_dims)}, avg={sum(sparse_dims)/len(sparse_dims):.0f}"
        )

        # 3. 插入测试数据
        import time as _time
        now_ts = int(_time.time())
        insert_records = []
        for i, doc in enumerate(CORPUS):
            insert_records.append({
                "id": doc["id"],
                "vector": dense_vectors[i],
                "sparse_vector": sparse_vectors[i],
                "user_id": "test_user",
                "text": doc["text"],
                "type": "text",
                "knowledge_base_id": TEST_PREFIX,
                "create_time": now_ts,
                "update_time": now_ts,
            })

        print(f"  [准备] 插入 {len(insert_records)} 条测试数据到 chunk_store...")
        result_ids = repo.insert(insert_records)
        inserted_ids = [str(rid) for rid in result_ids]
        print(f"    插入成功: {len(inserted_ids)} 条")

        # 等待索引构建
        print("  [准备] 等待索引构建...")
        await asyncio.sleep(2)

        # 4. 执行检索测试
        print()
        print("  [测试] 开始检索效果评估:")
        print()

        for scenario in QUERY_SCENARIOS:
            print(f"  --- 场景: {scenario['name']} ---")
            print(f"  查询: {scenario['query']}")
            print(f"  说明: {scenario['description']}")

            query = LexicalQuery(
                query_text=scenario["query"],
                top_k=5,
                filters=MetadataFilter(knowledge_base_id=TEST_PREFIX),
            )

            start = time.time()
            result = await bm25_search.execute(query=query)
            elapsed = time.time() - start

            print(f"  耗时: {elapsed:.3f}s, 命中: {result.total_count} 条")

            if result.items:
                for rank, item in enumerate(result.items, 1):
                    marker = ""
                    if scenario["expected_top_ids"]:
                        if item.chunk_id in scenario["expected_top_ids"]:
                            marker = " <-- 期望命中"
                    text_preview = (item.text or "")[:60]
                    print(f"    #{rank} [score={item.score:.4f}] {item.chunk_id}: {text_preview}{marker}")

                if scenario["expected_top_ids"]:
                    top_ids = {item.chunk_id for item in result.items[:3]}
                    expected = set(scenario["expected_top_ids"])
                    hit = expected & top_ids
                    print(
                        f"  Top-3 命中率: {len(hit)}/{len(expected)} "
                        f"({'通过' if hit else '未命中期望'})"
                    )
            else:
                print("    无命中结果")
            print()

        # 5. 对比测试：相同文本的稀疏向量自检索
        print("  --- 场景: 自检索验证 (文档自身作为查询) ---")
        test_doc = CORPUS[0]
        query = LexicalQuery(
            query_text=test_doc["text"],
            top_k=3,
            filters=MetadataFilter(knowledge_base_id=TEST_PREFIX),
        )
        result = await bm25_search.execute(query=query)
        if result.items and result.items[0].chunk_id == test_doc["id"]:
            print(f"  通过: 文档自身作为查询时排在第1位 (score={result.items[0].score:.4f})")
        elif result.items:
            print(f"  警告: 文档自身未排在第1位, 第1位是 {result.items[0].chunk_id}")
        else:
            print("  失败: 自检索无结果")
        print()

    except Exception as e:
        print(f"\n  BM25 端到端测试异常: {e}")
        traceback.print_exc()

    finally:
        # 6. 清理测试数据
        if repo and inserted_ids:
            print(f"  [清理] 删除 {len(inserted_ids)} 条测试数据...")
            try:
                repo.delete_by_ids(inserted_ids)
                print("    清理完成")
            except Exception as e:
                print(f"    清理失败: {e}")

        try:
            reset_manager()
        except Exception:
            pass
        os.environ.pop("MILVUS_AUTO_CREATE_COLLECTION", None)

    print()


# ======================================================================
#  Part 3: ExactMatch 正则构建逻辑测试
# ======================================================================


class ExactMatchTests:
    """ExactMatch 正则逻辑测试

    不依赖 MongoDB，仅验证各 MatchMode 下构建的正则表达式是否正确。
    """

    def __init__(self) -> None:
        self.exact_match = ExactMatch()
        self.passed = 0
        self.failed = 0

    def _assert(self, condition: bool, msg: str) -> None:
        if condition:
            self.passed += 1
            print(f"    通过: {msg}")
        else:
            self.failed += 1
            print(f"    失败: {msg}")

    def run_all(self) -> None:
        print("=" * 80)
        print("Part 3: ExactMatch 正则构建逻辑测试")
        print("=" * 80)
        print()

        self.test_exact_mode()
        self.test_prefix_mode()
        self.test_fuzzy_mode()
        self.test_regex_mode()
        self.test_special_characters()
        self.test_mongo_query_multi_keywords()

        print()
        print(f"  结果汇总: 通过 {self.passed}, 失败 {self.failed}")
        print()

    def test_exact_mode(self) -> None:
        """EXACT 模式"""
        print("  测试 3.1: EXACT 匹配模式")
        import re

        pattern = ExactMatch._build_regex_pattern("Transformer", MatchMode.EXACT)
        self._assert(pattern == r"^Transformer$", f"正则: {pattern}")
        self._assert(bool(re.search(pattern, "Transformer")), "匹配完整词")
        self._assert(not bool(re.search(pattern, "Transformer模型")), "不匹配包含词")
        print()

    def test_prefix_mode(self) -> None:
        """PREFIX 模式"""
        print("  测试 3.2: PREFIX 匹配模式")
        import re

        pattern = ExactMatch._build_regex_pattern("深度", MatchMode.PREFIX)
        self._assert(pattern.startswith("^"), "以 ^ 开头")
        self._assert(bool(re.search(pattern, "深度学习")), "匹配前缀")
        self._assert(not bool(re.search(pattern, "学习深度")), "不匹配非前缀")
        print()

    def test_fuzzy_mode(self) -> None:
        """FUZZY 模式（大小写不敏感包含匹配）"""
        print("  测试 3.3: FUZZY 匹配模式")
        import re

        pattern = ExactMatch._build_regex_pattern("bert", MatchMode.FUZZY)
        self._assert(bool(re.search(pattern, "BERT模型", re.IGNORECASE)), "大小写不敏感")
        self._assert(bool(re.search(pattern, "使用bert进行微调", re.IGNORECASE)), "包含匹配")
        print()

    def test_regex_mode(self) -> None:
        """REGEX 模式（用户自定义正则）"""
        print("  测试 3.4: REGEX 匹配模式")
        import re

        pattern = ExactMatch._build_regex_pattern(r"v\d+\.\d+", MatchMode.REGEX)
        self._assert(pattern == r"v\d+\.\d+", "保留原始正则")
        self._assert(bool(re.search(pattern, "version v2.0 released")), "匹配版本号")
        self._assert(not bool(re.search(pattern, "no version here")), "不匹配无版本号")
        print()

    def test_special_characters(self) -> None:
        """特殊字符转义"""
        print("  测试 3.5: 特殊字符转义")
        import re

        pattern = ExactMatch._build_regex_pattern("C++", MatchMode.FUZZY)
        self._assert(bool(re.search(pattern, "C++编程语言")), "匹配包含 C++ 的文本")
        self._assert(not bool(re.search(pattern, "C语言")), "不匹配不含 C++ 的文本")

        pattern2 = ExactMatch._build_regex_pattern("$100.00", MatchMode.EXACT)
        self._assert(r"\$" in pattern2, "$ 被正确转义")
        self._assert(r"\." in pattern2, ". 被正确转义")
        print()

    def test_mongo_query_multi_keywords(self) -> None:
        """多关键词 OR 查询"""
        print("  测试 3.6: 多关键词 MongoDB 查询结构")

        query = self.exact_match._build_mongo_query(
            ["Transformer", "BERT", "GPT"],
            MatchMode.FUZZY,
        )
        self._assert("$or" in query, "多关键词使用 $or")
        self._assert(len(query["$or"]) == 3, "$or 包含 3 个条件")
        self._assert(query.get("deleted") == 0, "包含 deleted=0 过滤")

        query_single = self.exact_match._build_mongo_query(
            ["单个词"],
            MatchMode.FUZZY,
        )
        self._assert("$or" not in query_single, "单关键词不使用 $or")
        self._assert("text" in query_single, "单关键词直接使用 text 字段")
        print()


# ======================================================================
#  运行入口
# ======================================================================


def run_parser_tests() -> None:
    tests = BooleanParserTests()
    try:
        tests.run_all()
    except Exception as e:
        print(f"\n  布尔解析器测试异常: {e}")
        traceback.print_exc()


def run_exact_match_tests() -> None:
    tests = ExactMatchTests()
    try:
        tests.run_all()
    except Exception as e:
        print(f"\n  ExactMatch 测试异常: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" Lexical 检索能力效果测试")
    print("=" * 80 + "\n")

    # Part 1: 纯逻辑测试（无外部依赖）
    run_parser_tests()

    # Part 3: ExactMatch 纯逻辑测试（无外部依赖）
    run_exact_match_tests()

    # Part 2: BM25 端到端测试（需要 Milvus + BGE-M3）
    print("是否运行 BM25 端到端测试？(需要 Milvus 和 BGE-M3 服务)")
    print("如需跳过请直接 Ctrl+C")
    try:
        asyncio.run(run_bm25_e2e_tests())
    except KeyboardInterrupt:
        print("\n  已跳过 BM25 端到端测试")

    print("\n" + "=" * 80)
    print(" Lexical 检索能力测试 — 全部完成！")
    print("=" * 80)
