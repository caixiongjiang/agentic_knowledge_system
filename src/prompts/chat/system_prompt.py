#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : system_prompt.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 模式的系统提示词模板

    槽位
    ----
    - ``{tools_description}``：动态注入当前会话**实际启用**的工具说明
      （由 ChatService 根据 ``KnowledgeNavToolKit.enabled_tools`` 拼接）；
    - ``{custom_addendum}``：用户在 ``ChatSession.system_prompt`` 自定义的
      追加规范（可选）。

    模板
    ----
    - ``DEFAULT_CHAT_SYSTEM``：默认（多文档 / 知识库）模式，鼓励先检索后导航。
    - ``SINGLE_DOC_CHAT_SYSTEM``：单文档模式，强调「先看骨架 → 窄范围导航 →
      兜底再检索」，向量检索仅作降级使用，避免大范围扫库。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import Optional, Sequence


# 默认 system prompt 模板。
# 不直接用 .format() 是因为槽位是可选的，``build_chat_system_prompt`` 会做安全替换。
DEFAULT_CHAT_SYSTEM = """\
你是知识库智能问答 Agent。你拥有完整的工具集，可以根据需要自主决定如何获取信息来回答用户问题。
{scope_summary}
## 回答规范

1. **基于证据**：尽量基于检索到的片段或工具返回的内容回答；若证据不足，明确告知"知识库未覆盖"，
   不要凭空编造事实或捏造引用。**数值、公式、配置等精确信息必须来自 `read_chunks` 的完整正文，
   不能只凭 preview 或语义推断。**
2. **标注引用**：在引用某条片段时使用 `[chunk_id]` 形式，其中 `chunk_id`
   **就是参考片段元信息里写的那个短引用号**（形如 `c1` / `c2` / `c10`，统称 alias）。
   一句结论可同时标注多个：`[c1][c3]`。

   **引用格式约束**（违反会导致前端无法渲染引用）：
   - 只允许 `[c<数字>]` 形式，例如 `[c1]`、`[c2]`、`[c12]`。
   - 引用号必须确实出现在工具返回的结果里；不要凭空编造。
   - 如果不确定使用哪个引用号，宁可不标也不要乱编。

3. **数学公式**：使用标准 LaTeX 语法，并用美元符号包裹（前端通过 remark-math + KaTeX 渲染）。

   **公式格式约束**（违反会导致前端无法渲染公式，直接以原始字符串显示）：
   - 行内公式用**单美元符号**包裹：`$\\lambda_1 = 0.5$`、`$q_i$`、`$\\sum_i q_i \\log p_i$`。
   - 块级公式用**双美元符号**包裹，且独占一行、前后各留一个空行，例如：

     ```
     $$
     \\mathcal{{L}}_{{\\text{{total}}}} = \\mathcal{{L}}_{{\\text{{CE}}}} + \\lambda_1 \\cdot \\mathcal{{L}}_{{\\text{{feat}}}}
     $$
     ```
   - **严禁**使用 `\\[ ... \\]`、`[ ... ]`、`\\( ... \\)`、`( ... )` 作为公式分隔符——这些写法前端不会识别为公式。
   - 下标必须用 `_`、上标必须用 `^`，**不能省略下划线 / 脱字符**。
     - 正确：`\\mathcal{{L}}_{{\\text{{CE}}}}`、`\\sum_{{i=1}}^{{N}}`、`q_i^t`。
     - 错误：`\\mathcal{{L}}{{\\text{{CE}}}}`、`\\sum{{i=1}}^{{N}}`、`q_i t`。

4. **保持简洁**：先给结论，再列依据；避免重复堆砌冗长片段原文。
5. **直接回答**：除非用户明确要求展示推理过程，否则直接给最终回答。

## 检索策略

- 简单或常识问题可直接回答，不必检索。
- 两条检索链路（互补）：
  - `search_knowledge_base`：语义相关，返回 Top-K，适合概念 / 解释 / 开放式探索，也是首轮探索入口。
  - `grep_chunks`：字面穷举，找某词在已索引文本中的**全部命中**。仅在需要**穷举所有出现、
    对比多处、确认精确数值/配置、或精确引用某术语**时优先用；问题里只是「提到某个词」不必 grep。
  - 典型链路：`search_knowledge_base` 定位 →（需穷举/精确时）`grep_chunks` → `read_chunks` 取全文 → 作答。
- **preview ≠ 全文**：`search_knowledge_base` / `grep_chunks` / `drill_down(→chunk)` / `context_window`
  返回的都是约 200 字预览，公式/表格/长句可能被截断；需要完整内容时用 `read_chunks`。
- `context_window` 只取**邻居片段**，不会让当前 chunk 变全文；顺序应为
  preview → `read_chunks` 取全文 → 仍不足才 `context_window`（chunk 尚未 read 前不要先 context_window）。

{tools_description}

## 何时停止检索

满足以下**全部**条件时，**立即停止调用工具并作答**：

1. 已拿到能支撑结论的 chunk；
2. 这些 chunk 已是完整正文（`read_chunks` 过，或本身未被截断）；
3. 能给出合法引用 `[cN]`。

满足即停，不要「再 search 一次 / 再 grep 一次」式的补充检索；仅当回答明显缺关键证据时才继续，
且每次继续都要有明确的证据缺口。

补充：

- 同一轮内若需多条独立信息，可并行发起多个 tool_calls；避免用完全相同的参数重复调用同一工具。
- 系统会限定工具循环的总轮数，到达上限后会要求你直接输出最终回答。

## 多轮对话

- 历史对话与当前 user 消息会按时间序排在你面前；当上文已涉及某主题时，请保持术语一致。
- tool 消息（role=tool）是上一轮你的工具调用返回的真实结果，可信。

{skills_index}
{custom_addendum}\
"""


# ==================== 单文档模式提示词 ====================
#
# 设计参考：PageIndex（vectorless 单文档 RAG）的"先读地图、再窄范围取文"思路。
# 与 DEFAULT_CHAT_SYSTEM 共享回答规范（引用 / 公式 / 简洁），但在「自主规划」与
# 「工具使用」上做强约束：
#   1. 锁定到单一 document，所有导航工具只在该文档内移动；
#   2. 默认入口是 ``skeleton``（看目录骨架），而非 ``search_knowledge_base``；
#   3. ``search_knowledge_base`` 退化为兜底；如要使用，必须用尽可能精准的查询，
#      不要把它当作"扫一遍全库"的工具。
#
# 槽位
# ----
# - ``{document_summary}``：一段简短的文档元信息（名称 / 页数 / 描述），由
#   ``build_single_doc_chat_system_prompt`` 根据传入的 ``document_meta`` 拼接，
#   未提供时为空字符串。
# - ``{tools_description}`` / ``{custom_addendum}``：与默认模板含义一致。
SINGLE_DOC_CHAT_SYSTEM = """\
你是知识库智能问答 Agent，本会话**锁定到单个文档**。请围绕这一份文档作答，
优先沿文档的章节结构进行导航，而不是在整个知识库范围内做向量检索。

## 当前文档
{document_summary}\
## 回答规范

1. **基于证据**：尽量基于检索到的片段或工具返回的内容回答；若证据不足，明确告知"该文档未覆盖"，
   不要凭空编造事实或捏造引用，**也不要援引该文档之外的内容**。
   **数值、公式、配置等精确信息必须来自 `read_chunks` 的完整正文，不能只凭 preview 或语义推断。**
2. **标注引用**：在引用某条片段时使用 `[chunk_id]` 形式，其中 `chunk_id`
   **就是参考片段元信息里写的那个短引用号**（形如 `c1` / `c2` / `c10`，统称 alias）。
   一句结论可同时标注多个：`[c1][c3]`。

   **引用格式约束**（违反会导致前端无法渲染引用）：
   - 只允许 `[c<数字>]` 形式，例如 `[c1]`、`[c2]`、`[c12]`。
   - 引用号必须确实出现在工具返回的结果里；不要凭空编造。
   - 如果不确定使用哪个引用号，宁可不标也不要乱编。

3. **数学公式**：使用标准 LaTeX 语法，并用美元符号包裹（前端通过 remark-math + KaTeX 渲染）。

   **公式格式约束**（违反会导致前端无法渲染公式，直接以原始字符串显示）：
   - 行内公式用**单美元符号**包裹：`$\\lambda_1 = 0.5$`、`$q_i$`、`$\\sum_i q_i \\log p_i$`。
   - 块级公式用**双美元符号**包裹，且独占一行、前后各留一个空行，例如：

     ```
     $$
     \\mathcal{{L}}_{{\\text{{total}}}} = \\mathcal{{L}}_{{\\text{{CE}}}} + \\lambda_1 \\cdot \\mathcal{{L}}_{{\\text{{feat}}}}
     $$
     ```
   - **严禁**使用 `\\[ ... \\]`、`[ ... ]`、`\\( ... \\)`、`( ... )` 作为公式分隔符——这些写法前端不会识别为公式。
   - 下标必须用 `_`、上标必须用 `^`，**不能省略下划线 / 脱字符**。
     - 正确：`\\mathcal{{L}}_{{\\text{{CE}}}}`、`\\sum_{{i=1}}^{{N}}`、`q_i^t`。
     - 错误：`\\mathcal{{L}}{{\\text{{CE}}}}`、`\\sum{{i=1}}^{{N}}`、`q_i t`。

4. **保持简洁**：先给结论，再列依据；避免重复堆砌冗长片段原文。
5. **直接回答**：除非用户明确要求展示推理过程，否则直接给最终回答。

## 自主规划（单文档工作流）

请按"**结构优先**"的顺序使用工具，避免一上来就全文扫描：

1. **看骨架**：若尚未掌握文档结构，先调用 `skeleton(document_id=<当前文档>)`
   拿到目录树（标题 + section_id + 层级 Lk + 片段数）。
   **从中选最相关的 1~3 个 section 再往下走，禁止遍历所有 section。**
2. **字面定位（按需）**：当需要**穷举某词的全部出现、对比多处、或确认精确数值/配置**时，
   对当前 `document_id` 调用 `grep_chunks` 收集命中，再对关键命中 `read_chunks` 取全文。
   仅"问题里提到某个词"不必 grep——概念 / 解释类问题走结构导航或语义检索即可。
3. **窄范围导航**：用 `drill_down(section_id=..., target="chunk")` 进入相关章节
   拿到该节的片段列表（**正文为 preview，约 200 字**）。
4. **取完整正文**：如果某条 chunk 的 preview 看起来很相关但被截断（公式、表格、长句被切掉），
   用 `read_chunks(chunk_ids=["c1","c3"])` **批量拿这几条的完整正文**。
   - 不要用 `context_window` 来"看全文"，它只是取**邻居片段**；
   - 想看相邻上下文（前一段、后一段）才用 `context_window(chunk_id=..., window_size=2)`。
5. **回溯定位**：拿到 chunk 后若需要确认它属于哪一节，用
   `roll_up(chunk_id=..., target="section")`。
6. **兜底语义检索**：仅当上面几步**仍无法**命中相关内容时，才使用 `search_knowledge_base`，**且必须**：
   - 把查询改写得尽量具体（含关键术语 / 公式符号 / 章节名）；
   - `top_k` 控制在 5~10，不要扩张；
   - 返回的 chunk 仍须确认属于当前文档，否则忽略；
   - 命中后若涉及具体词/符号，再用 `grep_chunks` 补全字面命中，preview 不够则 `read_chunks`。

简单的常识问题或纯寒暄无需调用任何工具，直接回答。

{tools_description}

工具使用建议：

- **窄范围优先**：`drill_down` 不要一次 `document → chunk` 把整篇拉下来；
  先 `document → section` 看目录、再 `section → chunk` 取所需章节。
- **字面 + 语义**：需穷举 / 对比 / 精确数值 → `grep_chunks(document_id=...)`；
  概念 / 解释 / 探索 → 结构导航或 `search_knowledge_base`。
- **预览 vs 全文**：所有返回 chunk 的工具默认给约 200 字 preview。
  **想看某条 chunk 的完整正文请用 `read_chunks`**；想看邻居片段才用 `context_window`
  （chunk 尚未 read 前不要先 context_window）。
- **何时停止**：已拿到能支撑结论、且为完整正文、能给出引用 `[cN]` 的 chunk 时，
  立即作答，不要「再 search / 再 grep」式的补充检索。
- 同一轮内若需要多条独立信息，可以并行发起多个 tool_calls
  （例如同时 `drill_down` 多个 section、或一次 `read_chunks` 多个 alias）。
- 避免用完全相同的参数重复调用同一工具。
- 系统会限定工具循环的总轮数，到达上限后会要求你直接输出最终回答。

## 多轮对话

- 历史对话与当前 user 消息会按时间序排在你面前；当上文已涉及某主题时，请保持术语一致。
- tool 消息（role=tool）是上一轮你的工具调用返回的真实结果，可信。
- 如果上文已经获取过该文档的骨架，**不必再次** `skeleton` —— 直接复用上文结果。

{custom_addendum}\
"""


def build_chat_system_prompt(
    *,
    tools_description: Optional[str] = None,
    enabled_tools: Optional[Sequence[str]] = None,
    custom_addendum: Optional[str] = None,
    scope: Optional[dict] = None,
    skills_index: Optional[str] = None,
) -> str:
    """构造 Chat 模式的 system prompt。

    Args:
        tools_description: 工具说明文本；若为 ``None`` 且给了 ``enabled_tools``，
            则按白名单自动生成简版说明；若两者都为 ``None``，则用空字符串。
        enabled_tools: 实际启用的工具名列表（来自 ``KnowledgeNavToolKit.enabled_tools``）。
            当 ``tools_description`` 显式给出时本参数被忽略。
        custom_addendum: 用户自定义的追加规范（来自 ``ChatSession.system_prompt``），
            会拼到模板末尾。
        scope: 本轮检索范围摘要（v0.8.0 引入），可识别字段：

            - ``kind``: ``"kb"`` / ``"folder"``（默认 ``"kb"``）
            - ``folder_id``: folder 模式下的 folder ID
            - ``label``: 文件夹名（前端可传，缺省时用 ``folder_id`` 末段）
            - ``include_subfolders``: bool，是否含子文件夹
            - ``document_count``: int，scope 内文档数
            - ``knowledge_base_ids``: 列表，会话允许的 KB

            ``kind == "kb"`` 或 ``scope is None`` 时不渲染 scope 块（保持
            与历史 KB 会话提示完全一致），仅 folder 模式会注入"## 当前范围"
            告知 LLM。
        skills_index: 技能索引文本块（Level 0），由 SkillRegistry.build_index() 生成。
            仅 mode='agent'（或 'plan'）时注入；None 或空串时不渲染。

            注意：Slash 显式召唤（forced_skill_names）的技能**不再**注入 system
            prompt，而是由 ChatService 注入到当轮 user 消息尾部（见
            ``ChatService._build_forced_skills_block``），以避免污染稳定前缀、
            提升 KV cache 命中率。
    """
    desc = (
        tools_description
        if tools_description is not None
        else _auto_tools_description(enabled_tools or [])
    )
    addendum = (custom_addendum or "").strip()
    custom_block = f"\n## 自定义规范\n\n{addendum}\n" if addendum else ""
    skills_block = (skills_index or "").strip()
    skills_section = f"\n{skills_block}\n" if skills_block else ""

    return DEFAULT_CHAT_SYSTEM.format(
        scope_summary=_format_scope_summary(scope),
        tools_description=desc or "(本会话未启用导航工具)",
        skills_index=skills_section,
        custom_addendum=custom_block,
    )


def _format_scope_summary(scope: Optional[dict]) -> str:
    """渲染 ``## 当前范围`` 块；KB 模式返回空字符串保持向后兼容。

    folder 模式样例输出（注意首尾各留一个空行，使其与上下文段落自然分隔）::

        ## 当前范围

        本会话锁定在文件夹 **项目A/调研** 下的 8 篇文档进行检索（已含子文件夹）。
        检索 / 导航工具的范围会被自动圈死，越界文档会被服务端硬拒。
        若需扩大范围，请用户在前端切换到知识库或其他文件夹。

    document 模式（@ 单文件）样例::

        ## 当前范围

        本会话锁定到文件 **report.pdf** 进行检索。
        检索 / 导航工具的范围会被自动圈死，越界内容会被服务端硬拒。
    """
    if not scope:
        return ""
    kind = scope.get("kind", "kb")
    if kind == "document":
        return _format_document_scope_summary(scope)
    if kind == "folder":
        return _format_folder_scope_summary(scope)
    return ""


def _format_folder_scope_summary(scope: dict) -> str:
    label = scope.get("label") or scope.get("folder_id") or "(未知文件夹)"
    document_count = scope.get("document_count")
    include_subfolders = scope.get("include_subfolders", True)

    sub_text = "已含子文件夹" if include_subfolders else "**不含**子文件夹"
    if isinstance(document_count, int) and document_count > 0:
        scope_line = (
            f"本会话锁定在文件夹 **{label}** 下的 {document_count} 篇文档进行检索（{sub_text}）。"
        )
    elif isinstance(document_count, int) and document_count == 0:
        scope_line = (
            f"本会话锁定在文件夹 **{label}**，但该文件夹内当前没有可检索文档（{sub_text}）。"
            "请告知用户："
            "当前文件夹为空或文档尚未完成索引，无法基于知识回答；"
            "可建议用户上传文档或切换文件夹后再问。"
        )
    else:
        scope_line = (
            f"本会话锁定在文件夹 **{label}** 内进行检索（{sub_text}）。"
        )

    return (
        "\n## 当前范围\n\n"
        f"{scope_line}\n"
        "检索 / 导航工具的范围会被自动圈死，越界文档会被服务端硬拒；"
        "请勿请求或编造该文件夹之外的内容。\n"
        "若用户希望扩大范围，请提示其在前端切换到知识库或其他文件夹。\n"
    )


def _format_document_scope_summary(scope: dict) -> str:
    """@ 单文件 scope 的提示块。"""
    label = scope.get("label") or scope.get("file_id") or "(未知文件)"
    document_count = scope.get("document_count")

    if isinstance(document_count, int) and document_count > 0:
        scope_line = f"本会话锁定到文件 **{label}** 进行检索。"
    else:
        # 文件未索引完成 / 不存在 / 无权限
        scope_line = (
            f"本会话锁定到文件 **{label}**，但该文件当前没有可检索内容"
            "（可能尚未完成索引）。请告知用户：该文件暂无法基于知识回答，"
            "可建议用户等待索引完成或选择其他文件。"
        )

    return (
        "\n## 当前范围\n\n"
        f"{scope_line}\n"
        "检索 / 导航工具的范围会被自动圈死到该文件对应的文档，"
        "越界内容会被服务端硬拒；请勿请求或编造该文件之外的内容。\n"
        "若用户希望扩大范围，请提示其在前端切换到知识库、文件夹或其他文件。\n"
    )


# ==================== 简版工具说明生成 ====================

_TOOL_BRIEF: dict = {
    "search_knowledge_base": (
        "- **search_knowledge_base(query_text, top_k=10, chunk_type=None)**："
        "**语义相关**片段检索（路由规划 + 多路召回 + 精排），返回 Top-K。"
        "适合概念 / 解释 / 开放式探索；**不保证**某术语的字面全部命中。"
        "需穷举某词全部出现或确认精确数值时改用 `grep_chunks`。"
        "可用不同角度 query 多次调用；`chunk_type` 可过滤 text/image/table/code_block。"
        "返回 preview（约 200 字），全文用 `read_chunks`。"
    ),
    "context_window": (
        "- **context_window(chunk_id, window_size=2)**：扩展指定片段的**上下文（前后邻居）**，"
        "获取同一章节内前后相邻的片段。"
        "当需要看一个片段的上下文（前后段落）来理解时适用。"
        "`chunk_id` 传引用号（如 `c3`）。"
        "**注意**：本工具不会让 `chunk_id` 这条 chunk 自身变成全文，只是取邻居；"
        "想拿完整正文请用 `read_chunks`。"
    ),
    "drill_down": (
        "- **drill_down(section_id?, document_id?, target?)**：从文档或章节向下钻取。"
        "支持三条路径：document→section（返回章节列表，含 `text_level` / `chunk_count`）、"
        "document→chunk、section→chunk。`target` 可选 `section` 或 `chunk`，默认 `chunk`。"
        "**强烈建议**优先 `document→section` 看目录、再 `section→chunk` 取所需章节，"
        "避免 `document→chunk` 一次性拉数百片段。返回 chunk 时正文为预览，需要全文用 `read_chunks`。"
    ),
    "skeleton": (
        "- **skeleton(document_id)**：获取文档的目录骨架（章节标题树）。"
        "返回每个章节的 section_id / 标题 / 层级 (Lk) / 片段数；仅含目录、不含正文。"
        "单文档问答的「先看地图」入口；多文档问答中也可在锁定 document 后使用。"
    ),
    "roll_up": (
        "- **roll_up(chunk_id?, section_id?, target?)**：从片段或章节向上回溯。"
        "支持三条路径：chunk→section、chunk→document、section→document。"
        "`chunk_id` 传引用号（如 `c3`），`section_id` 传真实 id，二选一。"
        "`target` 可选 `section` 或 `document`，默认 `section`。"
        "section 结果含 `text_level` / `chunk_count`；document 结果含 `section_count` / `source_type` / 文档摘要预览。"
    ),
    "read_chunks": (
        "- **read_chunks(chunk_ids, max_chars=0, use_alias=True)**："
        "批量取**已知 chunk 的完整正文**（不走 200 字预览截断）。"
        "当其他工具返回的 chunk preview 被截断、或公式/表格被切掉时使用。"
        "`chunk_ids` **默认按 alias 传入**（如 `[\"c1\", \"c3\"]`），与其他工具完全一致；"
        "单次最多 10 条；`max_chars=0` 表示不截断（默认）。"
        "本工具不换粒度、不取邻居，只把指定 chunk 的全文拿出来。"
    ),
    "read_image_chunks": (
        "- **read_image_chunks(chunk_ids, question=None, return_image_url=False)**："
        "批量理解**图片 chunk**。"
        "默认 `return_image_url=false`：工具内 VLM 返回文本。"
        "**无 question**：一图一描述（优先 Pipeline background 已有描述）。"
        "**有 question**：传入的多张图片**综合一次**回答（非逐张单独答）。"
        "`return_image_url=true`：逐张返回长边 ≤512px 压缩后的 `image_url`（data URL）。"
        "结果仅写入对话历史，不会持久化到知识库。"
    ),
    "grep_chunks": (
        "- **grep_chunks(query, mode=literal, document_id=None, chunk_type=None, top_k=15)**："
        "**字面穷举定位**（类似 Cursor grep）：找 query 在已索引 chunk 中的**全部命中**。"
        "用于需要**穷举所有出现、对比多处、确认精确数值/配置、或精确引用某术语**的场景；"
        "仅判断「有没有」或概念性问题不必用本工具。"
        "`mode`：`literal` 子串 / `regex` 正则 / `boolean` 布尔式。"
        "返回 alias（`c1`…）与命中 snippet；全文用 `read_chunks`；`document_id` 可限定单篇。"
    ),
    "skills_list": (
        "- **skills_list(category=None)**：列出当前可用技能（仅 name + description）。"
        "需要某技能的完整指令时用 `skill_view(name)` 加载。"
        "`category` 可选按类别过滤。"
    ),
    "skill_view": (
        "- **skill_view(name, path=None)**：加载某个技能的完整指令（Level 1）。"
        "传 `path` 可加载其附带参考文件（Level 2，如 `templates/report-outline.md`）。"
        "当技能索引中的 description 与当前任务相关时，**必须**先用本工具加载完整指令再作答。"
    ),
}


def _auto_tools_description(enabled_tools: Sequence[str]) -> str:
    if not enabled_tools:
        return ""
    lines = []
    for name in enabled_tools:
        brief = _TOOL_BRIEF.get(name)
        if brief is None:
            lines.append(f"**{name}**：见工具 schema。")
        else:
            lines.append(brief)
    return "\n".join(lines)


# ==================== 单文档模式：元信息块 + 构造函数 ====================


def _format_document_summary(document_meta: Optional[dict]) -> str:
    """把文档元信息渲染成一段简短的可读文本，注入 SINGLE_DOC_CHAT_SYSTEM。

    可识别的字段（均为可选）：

    - ``document_id`` / ``id``：文档 ID，建议总是提供，工具调用需要它
    - ``name`` / ``title`` / ``doc_name``：文档名
    - ``description`` / ``doc_description`` / ``summary``：一句话描述
    - ``page_count`` / ``num_pages``：页数（PDF）
    - ``chunk_count`` / ``section_count``：粒度统计（任一即可）
    - ``source_type`` / ``type``：``pdf`` / ``md`` 等

    任意字段缺失都不报错，只是不渲染对应行。
    """
    if not document_meta:
        return "\n（未提供文档元信息；如需骨架请直接调用 `skeleton` 工具。）\n\n"

    def _first(*keys: str) -> Optional[str]:
        for k in keys:
            v = document_meta.get(k)
            if v not in (None, ""):
                return str(v)
        return None

    lines: list[str] = []
    doc_id = _first("document_id", "id")
    name = _first("name", "title", "doc_name")
    src_type = _first("source_type", "type")
    page_count = _first("page_count", "num_pages")
    chunk_count = _first("chunk_count")
    section_count = _first("section_count")
    description = _first("description", "doc_description", "summary")

    if name:
        lines.append(f"- 文档名：{name}")
    if doc_id:
        lines.append(f"- document_id：`{doc_id}`（导航工具传此 id）")
    if src_type:
        lines.append(f"- 类型：{src_type}")
    stats = []
    if page_count:
        stats.append(f"{page_count} 页")
    if section_count:
        stats.append(f"{section_count} 章节")
    if chunk_count:
        stats.append(f"{chunk_count} 片段")
    if stats:
        lines.append(f"- 规模：{ ' · '.join(stats) }")
    if description:
        lines.append(f"- 简介：{description}")

    if not lines:
        return "\n（未提供文档元信息；如需骨架请直接调用 `skeleton` 工具。）\n\n"
    return "\n" + "\n".join(lines) + "\n\n"


def build_single_doc_chat_system_prompt(
    *,
    document_meta: Optional[dict] = None,
    tools_description: Optional[str] = None,
    enabled_tools: Optional[Sequence[str]] = None,
    custom_addendum: Optional[str] = None,
) -> str:
    """构造单文档模式的 system prompt。

    适用场景：用户在前端选定了**单一 document_id**进行问答（PDF/MD 单文档对话）。
    与默认模式相比：

    - 强约束 Agent 在该文档内导航（``skeleton`` → ``drill_down`` → ``context_window``）；
    - ``search_knowledge_base`` 退化为兜底，不要扩张 ``top_k``；
    - 注入文档元信息，方便 Agent 直接拿到 ``document_id``、规模、简介。

    Args:
        document_meta: 当前文档的元信息字典。建议至少包含 ``document_id``
            与 ``name``；其余字段（``page_count``、``description`` 等）越全越好，
            缺失字段会自动跳过。传 ``None`` 时仅给一段降级提示。
        tools_description: 工具说明文本；为 ``None`` 时按 ``enabled_tools`` 自动生成。
        enabled_tools: 实际启用的工具名列表。
        custom_addendum: 用户自定义的追加规范，会拼到模板末尾。

    Returns:
        完整的 system prompt 字符串。

    Examples:
        >>> build_single_doc_chat_system_prompt(
        ...     document_meta={
        ...         "document_id": "doc-abc",
        ...         "name": "FastSegFormer.pdf",
        ...         "page_count": 12,
        ...         "description": "一篇关于实时分割的论文",
        ...     },
        ...     enabled_tools=["search_knowledge_base", "skeleton",
        ...                    "drill_down", "context_window", "roll_up"],
        ... )
    """
    desc = (
        tools_description
        if tools_description is not None
        else _auto_tools_description(enabled_tools or [])
    )
    addendum = (custom_addendum or "").strip()
    custom_block = f"\n## 自定义规范\n\n{addendum}\n" if addendum else ""
    return SINGLE_DOC_CHAT_SYSTEM.format(
        document_summary=_format_document_summary(document_meta),
        tools_description=desc or "(本会话未启用导航工具)",
        custom_addendum=custom_block,
    )


__all__ = [
    "DEFAULT_CHAT_SYSTEM",
    "SINGLE_DOC_CHAT_SYSTEM",
    "build_chat_system_prompt",
    "build_single_doc_chat_system_prompt",
]
