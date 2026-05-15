# 全流程检索集成测试 — 报告 (FRT075-33F.pdf)

- 执行时间: 2026-04-21 17:30:31
- 测试脚本: `test/retrieve/pipeline/test_full_retrieve_with_pdf.py`
- LangSmith: 已启用
- 定位文档: document_id=`document-06a2cd6a-aac6-4732-b08a-8d1f58528f06`, knowledge_base_id=`kb-7c84fcdc-881c-4e4a-8b53-77980099373c`
- 总耗时: 85.0s
- 结果: 5/6 通过

## 用例明细

| 用例 | 状态 |
|------|------|
| T1 HYBRID 全 Pipeline | PASS |
| T2 SearchMode=SEMANTIC | FAIL |
| T3 SearchMode=LEXICAL + filter 透传 | PASS |
| T4 FusionStrategy.WEIGHTED_SUM | PASS |
| T5 ExactMatch + MetadataFilter 透传 | PASS |
| T6 retrieve_custom + section_dense | PASS |
