"""
Pipeline — 确定性检索管道组件

Phase 2: ParallelRecallExecutor  — 多路并行召回
         （qa_dense 高置信 → 置顶 QA + 依据 chunk，不短路）
Phase 3: GranularityAligner     — 跨粒度对齐到 Chunk
Phase 4: RRFFusion              — Reciprocal Rank Fusion + 去重
Phase 5: RerankStage            — Cross-Encoder 精排
         （置顶依据 chunk 已从候选中剔除）
"""
