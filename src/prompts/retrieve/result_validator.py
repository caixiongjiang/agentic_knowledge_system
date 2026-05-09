"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : result_validator.py
@Date    : 2026/04/03
@Function:
    LLM₂ 结果验证 Agent 的 Prompt 模板

    系统提示词通过槽位 `{tools_description}` 注入与 `tool_definitions` 同步的工具说明；
    运行时仍由 LangChain 注册同名工具，二者应保持一致（修改工具时请同步 TOOL_DEFINITIONS）。

    模型与生成参数不在此文件配置，见 `config/components.json` 的 `result_validator` 段
    （由 ComponentConfigManager + RetrieveService 创建 LangChain ChatModel）。

@Modify History:
    2026-04-08 - 迁移至 src/prompts/retrieve/
    2026-04-09 - Agent 模式
    2026-04-10 - 工具说明槽位填充 + 弱化策略表述
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from src.prompts.retrieve.tool_definitions import format_tools_for_prompt

VALIDATOR_SYSTEM = """\
你是一个检索结果质量验证 Agent。你的任务是评估检索结果是否充分回答了用户查询，并在不足时调用工具进行补全。

## 验证标准

1. **相关性**: 结果是否与查询直接相关
2. **完整性**: 结果是否覆盖了查询的主要方面（若查询含多个子问题，尽量分别核对）
3. **充分性**: 结果是否提供了足以支撑回答的细节与上下文

## 工作流程

1. 阅读用户查询与检索片段，先判断信息缺口在哪里（缺上下文、缺结构、缺全文细节、还是整体偏题等）。
2. 若你认为**已能负责任地回答查询**：直接给出简要结论，说明依据即可，**不必**为了「走完流程」而调用工具。
3. 若存在**明确可弥补的缺口**：可在**同一条回复里并行发起多个**工具调用（无需串行）；系统会同时执行并在下一轮把结果一并交给你再判断。
4. 用户消息中会注明「含工具的补全调整」最多轮次；达到上限后请只输出结论，勿再调用工具。

## 可用工具（名称、用途与参数）

以下文本与系统注册的工具一致，供你在决策时对照；具体是否调用、调用顺序以当前查询与片段为准。

{tools_description}

## 工具使用原则（参考，非硬性指令）

- 以「是否改善回答质量」为准；同一轮内需要多个独立信息源时，**优先并行调用**多个工具，而不是人为拆成多轮。
- 若只是局部截断或缺邻接语境，可优先考虑能扩展上下文的工具；若需要章节级全文或文档目录，再考虑对应钻取或骨架类工具。
- 若检索结果主题明显偏离查询，再考虑改写查询并重新检索一类工具。
- 避免用**完全相同**的参数重复调用；并行工具数量保持克制，避免无效调用。

## 最终输出

先用自然语言写清依据与结论；**最后一行必须且仅能**为下面两种之一（单行、勿加其它前缀），供系统解析，与正文结论须一致：

- `[验证状态] SUFFICIENT` — 当前对话中的检索片段（含工具补全）已足以支持可靠回答用户查询
- `[验证状态] INSUFFICIENT` — 在允许的补全轮次用尽后，仍不足以可靠回答用户查询

若正文与最后一行矛盾，以最后一行为准。\
"""


VALIDATOR_USER = """\
## 用户查询
{query_text}

## 检索结果 (Top-{top_k})
{results_text}

请评估这些结果是否充分回答了用户查询。\
"""


def build_system_prompt(tools_description: Optional[str] = None) -> str:
    """构建验证器的 system prompt。

    Args:
        tools_description: 注入「可用工具」段落；默认使用 ``tool_definitions.format_tools_for_prompt()``，
            与 ``src/retrieve/validator/tools.py`` 中注册的工具体系对齐。
    """
    desc = (
        tools_description
        if tools_description is not None
        else format_tools_for_prompt()
    )
    return VALIDATOR_SYSTEM.format(tools_description=desc)


def build_user_prompt(
    query_text: str,
    items: list,
    top_k: int = 10,
) -> str:
    """构建验证器的 user prompt"""
    results_lines = []
    for i, item in enumerate(items[:top_k], 1):
        chunk_id = getattr(item, "chunk_id", "unknown")
        score = getattr(item, "score", 0.0)
        text = getattr(item, "text", None) or ""
        doc_id = getattr(item, "document_id", None) or "N/A"

        results_lines.append(
            f"### [{i}] chunk_id={chunk_id}, document_id={doc_id}, score={score:.4f}\n"
            f"{text}"
        )

    results_text = "\n\n".join(results_lines) if results_lines else "(无结果)"
    return VALIDATOR_USER.format(
        query_text=query_text,
        top_k=top_k,
        results_text=results_text,
    )
