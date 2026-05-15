# Pipeline 确定性管道 — 测试报告

- **执行时间**: 2026-04-08 14:41:02
- **测试文件**: `test/retrieve/pipeline/test_deterministic_pipeline.py`
- **测试范围**: Phase 2-5 (ParallelRecall → Alignment → Fusion → Rerank)
- **总耗时**: 1.3s
- **结果**: 6/6 通过

## 用例明细

| 用例 | 状态 |
|------|------|
| 1.1 双路基础联调 (chunk_dense + bm25_sparse) | ✅ 通过 |
| 1.2 三路 + Section 粒度对齐 | ✅ 通过 |
| 1.3 含 exact_match 参数透传 | ✅ 通过 |
| 1.4 跳过 Rerank | ✅ 通过 |
| 1.5 MetadataFilter 过滤 | ✅ 通过 |
| 1.6 chunk + enhanced_chunk 混合召回 | ✅ 通过 |
