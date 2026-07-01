# Skill 技能系统设计方案（Hermes 范式 · agentic_knowledge_system）

> 版本：v0.4（方案稿）
> 范围：在后端 `agentic_knowledge_system` 中引入「Skill 技能」能力，对齐 Hermes Agent / agentskills.io 开放标准；含前端技能管理与 `/` 召唤；按端口-适配器拆出 runtime-无关内核以供 `agent_apps` 等多后端复用。
> 首期落地技能：**调研报告生成（research-report）**。
> 状态：待评审。
> v0.2 变更：新增前端「左侧技能栏（增删改查 + 启停，内置不可删）」与「输入框 `/` 按字母召唤技能」，及配套后端 CRUD API、自定义技能 DB 存储、`forced_skill_names` 强制召唤、创建期安全扫描。
> v0.3 变更：引入**端口-适配器架构**——内核 `skill_core`（runtime/ORM 无关）+ 每后端薄适配 + 持久化端口 `SkillRepository`；明确**共享 MySQL 技能表的 schema 单一所有者**与「禁止重复建模」。详见 §3.3 / §4.3。
> v0.4 变更：把组件切成**三层并定型本期形态**——`skill_core`（核心**包**，无状态纯逻辑）+ **独立 `SkillService`（管理服务进程，拥有存储/CRUD/REST/MCP）** + 各后端 Agent 薄适配；**读写都走 `SkillService` API**（两个后端作为客户端通过 REST 调用 skill-service，Level-0 索引在各后端进程内缓存以保持低延迟）；**写路径唯一入口为 `SkillService`**，前端对 skill-service 做技能 CRUD（可直连或经知识系统后端代理）；`SkillService` 独占共享 MySQL，是 schema 唯一所有者。详见 §3.3.2 / §3.3.5。

---

## 0. TL;DR

- **接入对话链路不造轮子**：技能在「对话侧」的接入完整复用本系统已有的「OpenAI 式工具调用 + 多轮 agent loop + 动态 system prompt」三件套——**对话链路只动两处**：① 新增 2 个工具 `skills_list` / `skill_view`；② 在 system prompt 里多注入一段「技能索引」。（技能的存储/CRUD/前端管理/`/` 召唤，以及供多后端复用的内核，是对话链路之外的新增模块，见 §3.2 / §3.3 / §11。）
- **照搬 Hermes 的灵魂——渐进式披露（Progressive Disclosure）**：system prompt 只放技能的 `name + description`（Level 0，约 3k token），完整正文由模型按需 `skill_view(name)` 拉取（Level 1），附带文件再按需 `skill_view(name, path)`（Level 2）。
- **不做服务端「触发路由」**：要不要加载某个技能，交给已经看到上下文的 LLM 自己用工具决定。这是 Hermes 规避「选错/漏选技能」这一最大失败源的关键决策。
- **Skill 站在 Tool 之上**：检索/导航的 8 个原语保持为 Tool（确定性、闭集、代码实现）；技能是「如何编排这些工具完成某类任务」的流程知识（markdown、开集、可增长、无需改代码）。
- **首期技能「调研报告生成」**：本质是「先用检索工具把证据捞齐 → 综合成带 `[cN]` 引用溯源的结构化报告 → （可选）导出文件」。带引用溯源是本系统相对通用 agent 的差异化优势，必须写进技能。
- **三层拆分（关键架构原则）——核心是包、管理是独立服务**：① **`skill_core`（核心包）**：解析/registry/索引渲染/安全扫描算法/持久化端口，无状态、**不依赖任何 agent 框架、不写死 ORM**；② **独立 `SkillService`（管理服务进程）**：技能 CRUD/启停/写入期安全扫描/REST/MCP，**拥有存储、独占共享 MySQL**，作为独立进程部署，前端与各后端都通过 API 调用它；③ **每后端一份 Agent 薄适配**：把 `skills_list`/`skill_view` 接进各自工具体系、把索引注入各自 prompt。**读写都走 `SkillService` API**，Level-0 索引在各后端进程内缓存以保持低延迟；知识系统与 `agent_apps` 复用同一核心包、调用同一 skill-service，无需重复实现，更无需合并两个后端。详见 §3.3。

---

## 1. 背景与目标

### 1.1 现状

本系统的 Chat Agent 已具备成熟的扩展底座：

- **工具调用**：`ToolDefinition` + `ALL_TOOL_DEFINITIONS` + `KnowledgeNavToolKit`，经 LiteLLM 流式 + 并行调用，现有 8 个工具（`search_knowledge_base` / `context_window` / `drill_down` / `skeleton` / `roll_up` / `read_chunks` / `read_image_chunks` / `grep_chunks`）。
- **动态 system prompt**：`build_chat_system_prompt(...)` 带 `{scope_summary}` / `{tools_description}` / `{custom_addendum}` 槽位。
- **多轮工具循环**：`agent_mode=True` 时 `_run_loop_real` 已支持 `astream(tools=...)` 多轮 tool 调用。
- **会话持久化**：MySQL `ChatSession`（`agent_mode` / `system_prompt` / `model` 等）+ MongoDB `ChatMessage`。

缺的只是一层「技能生命周期」：登记 → 索引 → 按需加载 → 执行其流程指令。

### 1.2 目标

1. 引入与 **agentskills.io 开放标准**兼容的 `SKILL.md` 技能格式，使技能可移植、可复用现有生态。
2. 以**最小侵入**方式接入对话链路：复用现有工具注册与 prompt 装配机制，不重写 agent loop。
3. **内核 runtime-无关、可多后端复用**：把技能逻辑沉到独立内核 `skill_core`，知识系统与 `agent_apps` 通过各自薄适配共用同一内核与技能数据（见 §3.3）。
4. 首期交付一个高价值技能：**调研报告生成**，验证整套机制。
5. 把 Hermes 验证过的「好用」要点全部接进来，避免自研版本出现「技能不被触发 / token 爆炸 / 选错技能 / 不可信」等典型缺陷。

### 1.3 范围与非目标

**本期包含**：
- runtime-无关内核 `skill_core` + 渐进式披露（`skills_list` / `skill_view`），及本系统适配层（见 §3.3）。
- 首期内置技能：调研报告生成。
- **前端技能管理**：左侧「技能」栏目可创建 / 启停 / 删除 / 查看自定义技能；内置技能不可删。
- **输入框 `/` 召唤**：按字母搜索并强制加载技能（对齐 Cursor）。

**本期不做**：
- 技能市场 / Hub / 远程安装（taps、skills.sh 等分发生态）。
- 技能自创建/自进化（`skill_manage`，**由 agent 自动写技能**）——留待后续；本期仅人工通过前端创建。
- 自定义技能的多文件附件（`templates/` 等 Level 2，仅内置技能支持）；按用户隔离的私有技能。
- 多 profile、跨平台平台门控——单服务端场景暂不需要。

---

## 2. 核心设计哲学（Hermes 要点，必须接进来）

以下每一条都是 Hermes 让技能「好用」的关键，缺一条都会导致自研版本难用。

### 2.1 渐进式披露（Progressive Disclosure）— 地基

```
Level 0  技能索引(name + description)   → 常驻 system prompt，约 3k token
Level 1  skill_view(name)              → 模型按需拉某个技能的完整正文
Level 2  skill_view(name, path)        → 再按需拉它的 references/templates 等附带文件
```

- system prompt **只放元数据**，不放正文 → token 经济。
- 正文用到才加载 → 上下文干净、不稀释注意力。

> Hermes 对应实现：`agent/prompt_builder.py::build_skills_system_prompt`（构建索引）+ `tools/skills_tool.py::skills_list / skill_view`（按需加载）。

### 2.2 索引进 prompt + 按需工具加载，**不做服务端预路由**

- 把所有技能的 description 摊给模型，由 LLM 自己判断是否 `skill_view`。
- **不要**在服务端用关键词/分类器去「猜该挂哪个技能」——那是技能系统最大的失败源（选错、漏选）。把决策交给已看到完整上下文的模型更鲁棒。

### 2.3 强制扫描 + 「宁可多加载」的提示语

索引块必须带强约束指令，否则模型会偷懒不加载技能（等于白做）。照搬 Hermes 的语气：

> Before replying, scan the skills below. If a skill matches or is even partially relevant, you MUST load it with `skill_view(name)` and follow its instructions. Err on the side of loading.

### 2.4 标准 SKILL.md 结构（agentskills.io）

- **Frontmatter（YAML）**：`name` / `description` / `version` / `metadata.tags` / 可选条件激活字段。
- **Body（Markdown）**：`When to Use`（触发契约）/ `Procedure`（步骤）/ `Pitfalls`（坑）/ `Verification`（自检）。
- `description` 是模型决定是否加载的**唯一依据**，必须精炼准确；`When to Use` 是触发契约；`Pitfalls` 是防错关键。

### 2.5 条件激活（Conditional Activation）

技能可声明依赖：`requires_tools` / `requires_toolsets`（缺失则隐藏）、`fallback_for_tools`（存在则隐藏，用于降级技能）。避免无关技能淹没索引。
> Hermes 对应：`agent/prompt_builder.py::_skill_should_show`。

### 2.6 两层缓存

技能多了之后，每轮都全盘扫描 `SKILL.md` 会拖垮首 token 延迟。采用：① 进程内 LRU；② 磁盘快照，按文件 mtime/size manifest 校验失效。
> Hermes 对应：`_load_skills_snapshot` / `_write_skills_snapshot` / `.skills_prompt_snapshot.json`。

### 2.7 永不彻底隐藏，只降级

需要压缩索引时，只去掉 description，**技能名始终保留可见、可 `skill_view`**。否则会出现「记得有这个技能却调不出来」。
> Hermes 对应：`prompt_builder.py` 的 category demotion（`[names only]`）。

### 2.8 安全：内容扫描 + 信任分级

一旦允许用户/第三方提供技能，必须扫描 prompt 注入、数据外泄、破坏性命令；并分 `builtin` / `official` / `community` 信任级。本期技能为内置（builtin），但机制需预留。
> Hermes 对应：`tools/skills_guard.py`。

### 2.9 Tool vs Skill 的分工（设计红线）

| 维度 | Tool | Skill |
|---|---|---|
| 本质 | 可执行函数（代码） | 知识文档（SKILL.md） |
| 执行 | 代码执行、确定性 | LLM 阅读后遵循、靠工具落地 |
| 入上下文 | schema 常驻 | 仅元数据常驻，正文按需加载 |
| 新增 | 写代码、改 agent | 写 markdown，无需改代码 |
| 适用 | 检索、读图、代码沙箱等原语 | 流程/SOP/产出编排 |

**红线**：现有 8 个检索/导航工具**保持为 Tool**，不改造成技能；技能只编排它们。

---

## 3. 整体架构

### 3.1 分层视图

```
┌──────────────────────────────────────────────────────────────┐
│  Chat Agent 多轮循环（已存在，零改动）                          │
│  _run_loop_real: client.astream(messages, tools=tools_schema)  │
└───────────────┬──────────────────────────────────────────────┘
                │ 注入                       ▲ 工具调用 / 结果
                ▼                            │
┌───────────────────────────┐   ┌───────────────────────────────┐
│ system prompt 装配（改 1 处）│   │ 工具层（加 2 个工具）           │
│ build_chat_system_prompt    │   │ skills_list() → 列技能(Level0)  │
│   + {skills_index} 技能索引  │   │ skill_view(name[,path])         │
│   (Level 0：name+desc 常驻)  │   │   → 加载技能正文(Level1/2)      │
└───────────────┬─────────────┘   └───────────────┬───────────────┘
                │                                  │ 读取
                ▼                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  本系统适配层（src/service/chat/tools/handlers/ + chat_service） │
│  把 skills_list/skill_view 接进 KnowledgeNavToolKit、注入索引    │
└───────────────┬──────────────────────────────────────────────┘
                ▼ 仅依赖内核稳定接口
┌──────────────────────────────────────────────────────────────┐
│  内核 skill_core（独立包，runtime/ORM 无关，多后端复用；见 §3.3）│
│  loader → registry(缓存,注入repo) → build_index / 正文读取      │
│  + SkillRepository 端口 + security 扫描                          │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│  技能存储（注册表合并两源）                                      │
│   · 内置 builtin：磁盘 skills/（只读、不可删）                   │
│   · 自定义 custom：MySQL skill 表（前端 CRUD）+ skill_state 启停 │
└──────────────────────────────────────────────────────────────┘

        前端（AI-site）
   ┌─────────────────────────┐   ┌──────────────────────────────┐
   │ 输入框 / 召唤（按字母搜索）│   │ 左侧「技能」栏：增/删/启停/查看 │
   │ → forced_skill_names     │   │ → api/routers/skill (CRUD)    │
   └─────────────────────────┘   └──────────────────────────────┘
```

### 3.2 改动清单（最小侵入）

> 模块归属遵循 §3.3 的端口-适配器划分：**核心包 `skill_core`**（runtime/ORM 无关，多后端复用）+ **独立管理服务 `SkillService`**（独立进程，拥有存储/CRUD/REST，独占 MySQL）+ **本系统 Agent 适配层**（耦合自研工具调用）。读写都走 skill-service API，Level-0 索引缓存在进程内（见 §3.3.5）。

**内核（`skill_core`，独立包 / 独立顶层目录，零业务依赖）**

| 类型 | 路径 | 改动 |
|---|---|---|
| 新增内核 | `skill_core/types.py` | `SkillDescriptor` / `Skill` / `CustomSkillRecord` 领域类型 |
| 新增内核 | `skill_core/loader.py` | 扫描内置目录、解析 frontmatter、读取正文/附件 |
| 新增内核 | `skill_core/registry.py` | `SkillRegistry`：合并 builtin + custom、索引构建、缓存（依赖注入 repository） |
| 新增内核 | `skill_core/ports.py` | `SkillRepository` 持久化端口（Protocol，零 ORM 依赖） |
| 新增内核 | `skill_core/security.py` | 内容安全扫描**算法**（纯函数，写入期由 `SkillService` 调用执行） |
| 新增内核 | `skill_core/adapters/mysql_repo.py` | 默认 MySQL repository 实现 + 表结构契约/DDL（session 由调用方注入） |

**本系统适配层（耦合自研 `KnowledgeNavToolKit` + prompt 装配）**

| 类型 | 路径 | 改动 |
|---|---|---|
| 新增工具 | `src/service/chat/tools/handlers/skills_list.py` | `skills_list` handler（调用内核 registry） |
| 新增工具 | `src/service/chat/tools/handlers/skill_view.py` | `skill_view` handler（调用内核 registry） |
| 改 1 处 | `src/service/chat/tools/handlers/__init__.py` | 把 2 个 DEFINITION 加入 `ALL_TOOL_DEFINITIONS` |
| 改 1 处 | `src/service/chat/chat_service.py::_resolve_turn_context` | ① `enabled_tools` 追加 `skills_list`/`skill_view`；② 注入技能索引到 system prompt；③ 处理 `forced_skill_names` |
| 改 1 处 | `src/prompts/chat/system_prompt.py::build_chat_system_prompt` | 模板新增 `{skills_index}`、`{forced_skills}` 槽位 |
| 改 1 处 | `src/service/chat/types.py::ChatRequest` | 新增可选 `forced_skill_names: list[str]`（slash 强制召唤） |
| 接线（读路径=调用 skill-service API） | 应用启动时从 skill-service 拉取 descriptors 构建本地 registry，Level-0 索引缓存在进程内 | 通过 REST 调用 skill-service 获取技能数据 |

**独立管理服务 `SkillService`（独立进程，拥有存储，独占共享 MySQL）**

| 类型 | 路径 | 改动 |
|---|---|---|
| 新增独立服务 | `skill-service/`（独立部署进程） | CRUD/启停编排 + 写入期安全扫描执行 + schema 迁移所有者 + REST/MCP API；基于 `skill_core` + MySQL repository |
| 新增路由 | `skill-service/api/` 技能 CRUD REST `/skills`（见 §6.5） | **前端与各后端都通过 API 调用 skill-service** |

**共享层（只建一次，两后端共用）**

| 类型 | 路径 | 改动 |
|---|---|---|
| 新增表 | 共享 MySQL `skill` / `skill_state` | 自定义技能正文与启停状态（见 §4.2）；**单一迁移所有者** = `SkillService`（DDL 随 `skill_core/adapters/mysql_repo.py`） |
| 新增内容 | `skills/research/research-report/SKILL.md` | 首期内置技能（磁盘，纯内容，无需改代码） |
| 前端 | `AI-site`：`app/skills/`、`components/skills/`、`lib/api/skills.ts` | `/` 召唤 + 左侧技能管理栏（见 §11） |

> 注：`BUILTIN_NAV_SCHEMAS` 与 `KnowledgeNavToolKit._handlers` 均由 `ALL_TOOL_DEFINITIONS` 自动派生（见 `registry.py`、`kit.py`），因此只要把 DEFINITION 加进 `ALL_TOOL_DEFINITIONS`，schema 注册与调度分发都会自动生效，**无需改 registry 与 kit**。

---

### 3.3 多后端共享与 runtime 适配（端口-适配器架构）

#### 3.3.1 背景：两个并列后端，运行时不同

当前工作区拓扑：

```
agent_infra_service   ← 共享基础设施（MySQL/Mongo/Milvus/Redis/Kafka/litellm proxy/鉴权/模型服务）
        ▲                         ▲
agentic_knowledge_system     agent_apps（通用/多 agent 后端：command/critic/research/write/...）
   （自研工具调用，无框架）        （更通用，未来可能使用第三方 agent 框架）
        ▲                         ▲
        └──────── AI-site ────────┘（同一前端）
```

- **知识系统**：全自研的工具调用（`KnowledgeNavToolKit` + 手写多轮循环），**不使用 agent 框架**。
- **agent_apps**：诉求更通用，未来**可能引入第三方 agent 框架**（LangGraph / LlamaIndex / AutoGen / OpenAI Agents SDK / Pydantic-AI 等）。

两个后端运行时不同，**正是采用端口-适配器（Hexagonal）的理由**：把「与 runtime 无关的内核」和「吸收 runtime 差异的适配层」彻底分开。

#### 3.3.2 分层职责（核心包 / 管理服务 / 适配，三者分清）

按「无状态核心逻辑」与「有状态管理面」拆开——**核心是包，管理是服务**：

| 组件 | 形态 | 内容 | 与 runtime/ORM 的关系 | 复用方式 |
|---|---|---|---|---|
| **`skill_core`（核心包）** | 库（无状态） | SKILL.md 解析/校验、`SkillRegistry`、descriptor、Level-0 索引**渲染**、安全扫描**算法**、`SkillRepository` 端口 + 默认 MySQL 适配 | **完全无关**（零 agent 框架、零写死 ORM/连接） | 服务与各后端都可 import |
| **独立 `SkillService`（管理服务进程）** | 服务（有状态，**拥有存储**） | 技能 CRUD、启停、**写入期**安全扫描执行、REST/MCP API、schema 单一所有者；写后 `registry.invalidate()` | 独占共享 MySQL | **只部署一份**（独立进程，见 §3.3.5） |
| **Agent 适配层** | 薄层 | 把 `skills_list`/`skill_view` 接进各自工具体系 + 注入索引 | 耦合各自 runtime | **每后端各写一份** |
| **共享存储** | 共享 MySQL `skill` / `skill_state` | 技能正文 + 启停状态 | — | 由 skill-service 独占，其它后端不直连 |

- **核心 = 包**：纯逻辑，被 `SkillService`（写校验/渲染）和各后端（运行时构建索引）共同 import。**不含 CRUD 编排、不开 HTTP、不拥有存储生命周期**。
- **管理 = 独立服务**：有状态、是技能数据的真源、独占 MySQL、对外开 REST/MCP API。**作为独立进程部署**（见 §3.3.5），前端与各后端都通过 HTTP 调用它。

> **关键事实**：渐进式披露只需要两个集成点——①「注册 2 个函数工具」②「往 system prompt 注入一段文本」。**任何 agent 框架都提供这两个扩展点**，所以 Hermes 范式在自研与框架运行时上都原样成立；差异全部落在薄薄的 Agent 适配里。

#### 3.3.3 两个集成点在不同 runtime 的映射

| 集成点 | 知识系统（自研） | agent_apps（任意框架） |
|---|---|---|
| ① 注册 `skills_list`/`skill_view` | `ToolDefinition` + `ALL_TOOL_DEFINITIONS` | 框架的 `@tool` / `Tool(...)` / function 注册 |
| ② 注入 Level-0 技能索引 | `build_chat_system_prompt` 的 `{skills_index}` 槽位 | 框架的 system prompt / context 注入口 |

#### 3.3.4 内核的稳定接口（适配层只依赖它）

```python
# skill_core：runtime-无关
class SkillRegistry:
    def list_descriptors(self, *, include_disabled=False) -> list[SkillDescriptor]: ...
    def get(self, name: str) -> Skill | None: ...
    def get_file(self, name: str, rel_path: str) -> str | None: ...
    def build_index(self, enabled_tools: set[str]) -> str: ...     # Level-0 文本块
    def invalidate(self) -> None: ...

class SkillRepository(Protocol):                                   # 持久化端口（零 ORM）
    def list_custom(self) -> list[CustomSkillRecord]: ...
    def get(self, name: str) -> CustomSkillRecord | None: ...
    def create(self, rec: CustomSkillRecord) -> None: ...
    def update(self, rec: CustomSkillRecord) -> None: ...
    def delete(self, name: str) -> None: ...
    def get_states(self) -> dict[str, bool]: ...
    def set_state(self, name: str, enabled: bool) -> None: ...

# registry 通过依赖注入拿 repository，自己绝不连库
registry = SkillRegistry(builtin_dir=..., repo=MySQLSkillRepository(session_factory=...))
```

- 内核**只**定义：领域类型 + 表结构契约（DDL）+ `SkillRepository` 接口 + 一个默认 MySQL 适配。
- 内核**不**写：写死的 ORM Base、连接池、`get_mysql_manager()` 等后端专有物——这些由各后端在启动时注入。

#### 3.3.5 本期落地形态（已定）：独立 SkillService + REST

**`SkillService` 作为独立服务进程部署**，独占共享 MySQL，对外暴露 REST API（未来可加 MCP）。两个后端（知识系统、agent_apps）都作为客户端通过 HTTP 调用它。

落地拓扑：

```
前端 AI-site ──CRUD/列表/启停──▶ skill-service REST API (独立进程)
                                         │ 独占
                                    共享 MySQL(skill/skill_state)
                                         ▲
知识系统后端 ──读(decriptors/正文)──▶ skill-service REST API
agent_apps   ──读(descriptors/正文)──▶ skill-service REST API（同上）
```

**读路径**：各后端启动时（或缓存失效时）调用 `GET /skills/descriptors` 拉取全部技能 descriptor + 版本号，在进程内构建 Level-0 索引缓存；正文按需通过 `GET /skills/{name}` 拉取。版本号由 skill-service 返回，变化时才重新拉取——**首次启动后读延迟与直连 DB 无异**。

**写路径**：前端 CRUD 请求走 skill-service REST API（可直连 skill-service，或经知识系统后端代理转发）。写后 skill-service 递增版本号，各后端下次读时感知变化并刷新缓存。

**为何选独立服务而非直连 DB + 包**：
- **schema 单一所有者**更彻底：MySQL 由 skill-service 独占，其它后端完全不触碰 DB，杜绝 ORM 漂移。
- **部署解耦**：skill-service 可独立扩缩容、独立发布，不绑定知识系统后端的发布周期。
- **跨语言就绪**：REST 契约天然支持非 Python 消费者（未来 agent_apps 若换框架/语言无需改造）。
- **延迟可控**：Level-0 索引缓存在各后端进程内，正文按需拉取（一次 HTTP 调用），首期技能个位数时延迟可忽略。

#### 3.3.6 红线

- **核心包绝不依赖任何 agent 框架，也不依赖写死的 ORM/连接**；一旦发现 `skill_core` 里 `import` 了 `KnowledgeNavToolKit`、检索 capability、或某框架/某后端的 ORM Base / `get_mysql_manager()`，即为架构破坏。
- **CRUD/HTTP/存储生命周期不进核心包**：这些属于独立 `SkillService`。核心包只做解析、渲染、索引、安全扫描算法、端口定义 + 默认适配。
- **写入只有一个入口**：所有技能写操作走独立 `SkillService`（前端 → skill-service REST API）。`agent_apps` 等其它后端**只读**，不得另开写口。
- **不要为了共享 skill 去合并两个后端**（不要把 agent_apps 写进知识系统）。共享用「核心包 + 共享表」解决；合并应用的耦合代价远大于收益。
- **schema 单一所有者**：技能表 DDL/迁移只有一个权威来源——`SkillService`（其依赖随 `skill_core` 的 MySQL 适配定义 DDL）。两个后端都**不得**各自重复定义 skill 的 ORM 模型（见 §4.3）。

---

## 4. 技能存储与目录结构

技能分两类来源，注册表在运行时合并：

| 来源 | 存储 | 可写 | 可删 | 由谁维护 |
|---|---|---|---|---|
| **内置（builtin）** | 磁盘 `skills/`（随仓库发布） | 否（只读） | **否** | 开发者 / 仓库 |
| **自定义（custom）** | MySQL `skill` 表 | 是 | 是 | 用户通过前端创建 |

> 之所以让自定义技能进 **DB 而非磁盘**：前端要支持创建/编辑/删除/启停，DB 比写文件系统更适合 Web CRUD（事务、并发、多实例一致、无需服务端文件写权限）。内置技能仍以磁盘为唯一真源（随代码版本走，不可删）。

### 4.1 内置技能目录（磁盘）

按类别组织，对齐 Hermes 的 `skills/<category>/<name>/SKILL.md` 布局：

```
agentic_knowledge_system/
└── skills/
    └── research/                      # 类别目录
        └── research-report/
            ├── SKILL.md               # 主指令（必需）
            └── templates/             # 可选：报告结构模板（Level 2 按需加载）
                └── report-outline.md
```

- **技能名**取自目录名（`research-report`），与 frontmatter `name` 一致。
- **类别**取自上层目录（`research`），用于索引分组。
- 预留 `config.skills.dir` 配置项（默认 `./skills`）。

### 4.2 自定义技能与状态（MySQL）

```sql
-- 自定义技能（前端创建）
CREATE TABLE skill (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    name         VARCHAR(64) UNIQUE NOT NULL,    -- 唯一；不得与内置技能重名
    description  VARCHAR(1024) NOT NULL,
    category     VARCHAR(64) DEFAULT 'custom',
    tags         JSON,
    version      VARCHAR(32) DEFAULT '1.0.0',
    requires_tools JSON,                          -- 可选条件激活
    body         MEDIUMTEXT NOT NULL,             -- SKILL.md 正文（含 frontmatter 或纯 body）
    created_by   VARCHAR(64),                     -- user_id
    created_at   DATETIME, updated_at DATETIME
);

-- 启停状态（内置 + 自定义统一）
CREATE TABLE skill_state (
    name     VARCHAR(64) PRIMARY KEY,
    enabled  BOOLEAN DEFAULT TRUE,
    updated_at DATETIME
);
```

- **重名规则**：创建自定义技能时若 `name` 与任一内置技能或已有自定义技能冲突，API 拒绝（避免遮蔽内置技能造成困惑）。
- **删除规则**：仅 `source=custom` 可删（删 `skill` 行）；对内置技能调用删除接口返回 `403 内置技能不可删除`，前端按钮置灰。
- **启停规则**：内置与自定义都可启停（写 `skill_state`）；停用后不进索引、也不可被 slash 召唤。
- **作用域**：首期技能为**部署级/全局**（所有用户共享）。按用户隔离的私有技能（`created_by` 过滤）列为后续增强。

### 4.3 持久化所有权与端口（多后端一致性）

这张表是**共享 MySQL**（位于 `agent_infra_service`），知识系统与 `agent_apps` 都会读它。为避免两后端各自定义模型导致 schema 漂移，遵循以下规则（与 §3.3 端口-适配器一致）：

- **schema 单一所有者**：上面的 DDL 是技能表的**唯一权威定义**，随 `skill_core/adapters/mysql_repo.py` 一起维护；建表/迁移**只由独立 `SkillService` 这一处负责**。其它后端完全不触碰 DB。
- **写入只有一个入口**：所有写操作走独立 `SkillService` 的 REST API（前端 → skill-service）。其它后端只读。
- **读走 skill-service API**：各后端通过 `GET /skills/descriptors` 等 REST 接口获取技能数据，不在本地定义任何 ORM 模型。
- **禁止重复建模**：知识系统、`agent_apps` **都不得**在各自代码里定义 `skill` / `skill_state` 的 ORM 模型；数据一律从 skill-service API 获取。
- **端口隔离 ORM**：内核只认 `SkillRepository` 接口；默认 `MySQLSkillRepository` 是 `SkillService` 内部的实现，仅供 skill-service 自身使用。其它后端不注入 repository，只调 API。

---

## 5. SKILL.md 格式规范（对齐 agentskills.io）

```markdown
---
name: research-report
description: 一句话说明技能用途——模型据此决定是否加载，必须精炼准确（≤1024 字符）
version: 1.0.0
metadata:
  tags: [research, report, multi-doc, citation]
  category: research
  requires_tools: [search_knowledge_base, read_chunks]   # 可选：缺失则该技能不进索引
  # fallback_for_tools: [...]                              # 可选：存在则隐藏（降级技能用）
---

# 技能标题

## When to Use
触发契约：什么情况下模型应该加载并遵循本技能。

## Procedure
分步骤的操作流程（编排已有工具）。

## Pitfalls
已知坑与规避方式。

## Verification
完成前的自检清单。
```

要点（同 §2.4）：`description` 是**唯一触发依据**；`When to Use` 是触发契约；`Pitfalls` 决定鲁棒性。Frontmatter 用 `CSafeLoader` 解析，解析失败回退到 `key:value` 简析（与 Hermes `skill_utils.parse_frontmatter` 一致的容错策略）。

---

## 6. 核心实现设计

### 6.1 核心包 `skill_core`（runtime/ORM 无关，独立包；详见 §3.3）

> ⚠️ 核心包**不放在** `src/service/chat/skills/` 下（那会绑死本系统），而是独立成 `skill_core` 包，供两个后端复用。三层在代码上的落点：

```
skill_core/                           # ① 核心包：无状态、纯逻辑（两后端 + SkillService 共用）
├── __init__.py                       #    暴露 SkillRegistry / SkillRepository / 领域类型 / scan_content
├── types.py                          #    SkillDescriptor / Skill / CustomSkillRecord 领域类型
├── loader.py                         #    扫描内置目录、解析 frontmatter（CSafeLoader+容错）、读正文/附件
├── registry.py                       #    SkillRegistry：合并 builtin+custom、缓存、build_index（注入 repo）
├── ports.py                          #    SkillRepository 持久化端口（Protocol，零 ORM）
├── security.py                       #    scan_content() 安全扫描算法（纯函数，不做拦截决策）
└── adapters/
    └── mysql_repo.py                 #    默认 MySQLSkillRepository + 表 DDL（仅 SkillService 内部使用）

skill-service/                        # ② 独立管理服务 SkillService（独立进程，拥有存储，独占 MySQL）
├── skill_service.py                  #    CRUD/启停编排 + 写入期调 scan_content + invalidate（§6.5）
├── api/
│   └── routers/
│       └── skill.py                  #    技能 CRUD REST（前端与各后端通过 HTTP 调用，§6.5）
└── main.py                           #    服务启动入口

agentic_knowledge_system/
└── src/service/chat/tools/handlers/
    ├── skills_list.py                # ③ 本系统 Agent 适配：两个只读工具（§6.3）
    └── skill_view.py
```

- **依赖方向**：②③ 都只依赖 ①；① 不反向依赖任何后端。`SkillService`（②）内部有自用的 `SkillRegistry` 单例（写后 `invalidate`）；各后端 Agent 适配（③）有各自的本地 `SkillRegistry`（从 skill-service API 拉取数据构建，版本号变化时刷新）。

**类型定义（`types.py`）**

```python
@dataclass(frozen=True)
class SkillDescriptor:
    name: str
    description: str
    category: str
    tags: tuple[str, ...]
    version: str
    requires_tools: tuple[str, ...]
    fallback_for_tools: tuple[str, ...]
    source: str                     # "builtin" | "custom"
    enabled: bool                   # 启用状态（前端可切换）
    deletable: bool                 # = (source == "custom")；内置技能不可删
    path: Path | None               # builtin：SKILL.md 路径；custom：None（正文在 DB）

@dataclass(frozen=True)
class Skill:
    descriptor: SkillDescriptor
    body: str                       # SKILL.md 正文（Level 1）
    files: tuple[str, ...]          # 可加载的附件相对路径（Level 2，仅 builtin）

@dataclass(frozen=True)
class CustomSkillRecord:            # 自定义技能的 DB 行（持久化端口的传输对象，零 ORM）
    name: str
    description: str
    category: str
    tags: tuple[str, ...]
    version: str
    requires_tools: tuple[str, ...]
    fallback_for_tools: tuple[str, ...]
    body: str                       # 完整 SKILL.md 正文
    created_at: datetime
    updated_at: datetime
```

**持久化端口（`ports.py`）与安全算法（`security.py`）**

```python
class SkillRepository(Protocol):    # 端口：零 ORM，由各后端注入具体实现
    def list_custom(self) -> list[CustomSkillRecord]: ...
    def get(self, name: str) -> CustomSkillRecord | None: ...
    def create(self, rec: CustomSkillRecord) -> None: ...
    def update(self, rec: CustomSkillRecord) -> None: ...
    def delete(self, name: str) -> None: ...
    def get_states(self) -> dict[str, bool]: ...          # {name: enabled}
    def set_state(self, name: str, enabled: bool) -> None: ...
    def table_version(self) -> int: ...                   # 供 registry 失效键（§9）

@dataclass(frozen=True)
class ScanResult:
    ok: bool
    hits: tuple[str, ...]           # 命中的风险规则（供 SkillService 决定告警/拦截）

def scan_content(body: str) -> ScanResult: ...            # 纯函数；不抛异常、不做拦截决策
```

> 核心包只提供 `scan_content` 的**判定**；**是否拦截/告警的策略由 `SkillService` 在写入期决定**（§6.5 / §10）。`MySQLSkillRepository`（`adapters/mysql_repo.py`）是端口的默认实现，自带 `skill` / `skill_state` 的 DDL（schema 单一所有者，§4.3），session 由调用方注入。

**注册表（`registry.py`）**：进程内单例，**合并两个来源**——① 内置技能（从磁盘 `skills/` 扫描，只读、不可删）；② 自定义技能（经注入的 `SkillRepository` 从共享 MySQL 读取，前端可增删改）。以「磁盘目录指纹 + 自定义技能表版本号」为键做失效（首期实现），磁盘快照见 §9。**registry 通过依赖注入拿 `repo`，自身绝不直接连库**（见 §3.3.4 / §4.3）。

```python
class SkillRegistry:
    def __init__(self, builtin_dir: Path, repo: SkillRepository): ...   # 持久化经端口注入
    def list_descriptors(self, *, include_disabled: bool = False) -> list[SkillDescriptor]: ...
    def get(self, name: str) -> Skill | None: ...
    def get_file(self, name: str, rel_path: str) -> str | None: ...     # Level 2，带路径穿越防护
    def build_index(self, enabled_tools: set[str]) -> str: ...          # Level 0 文本块（§6.2）
    def invalidate(self) -> None: ...                                    # 自定义技能 CRUD 后调用
```

> 本系统在应用启动处构造单例，注入一个从 skill-service 拉取数据的 repository 实现：
> `registry = SkillRegistry(builtin_dir=config.skills.dir, repo=SkillServiceRepository(skill_service_url=config.skill_service.url))`。
> `agent_apps` 用同样的内核、配置同一个 skill-service URL。
> `SkillService` 自身内部则使用 `MySQLSkillRepository` 直连 MySQL（它独占 DB）。

> **enabled 状态**：所有技能（含内置）的启用/停用状态统一记录在 MySQL `skill_state(name, enabled)` 表（默认启用）；自定义技能的正文/元数据存 `skill` 表（见 §4.2）。索引构建（§6.2）默认只取 `enabled=True` 的技能。

### 6.2 索引构建（Level 0，注入 prompt）

内核方法 `registry.build_index(enabled_tools)`（§3.3.4）的逻辑：

1. 取 `registry.list_descriptors()`。
2. **条件激活过滤**（§2.5）：`requires_tools` 必须全在 `enabled_tools` 内；`fallback_for_tools` 任一在则隐藏。
3. 按 category 分组，渲染为紧凑文本，并包裹强制扫描指令（§2.3）。
4. 结果带缓存（§9）。

> 命名统一：构建 Level-0 索引的唯一入口是内核的 `registry.build_index(enabled_tools)`；适配层不再单独定义 `build_skills_index` 自由函数。

渲染样例（注入 system prompt 的内容）：

```
## 技能（强制扫描）
回答前必须扫描下列技能。若某技能与当前任务相关（哪怕部分相关），你**必须**用
`skill_view(name="<技能名>")` 加载其完整指令并严格遵循。宁可多加载，也不要漏掉
关键步骤、坑位或既定流程。仅当确实无任何技能相关时，才直接作答。

<available_skills>
  research:
    - research-report: 把一个调研问题综合成带 [cN] 引用溯源的结构化调研报告……
</available_skills>
```

### 6.3 两个新工具（本系统 Agent 适配层 · 对齐 Hermes `skills_tool.py`）

> §6.3 / §6.4 属于 §3.3 划分中的**本系统适配层**（耦合自研 `KnowledgeNavToolKit` 与 prompt 装配）；它们只调用内核 `skill_core` 的稳定接口。`agent_apps` 会用框架原生的等价物各写一份，但同样只依赖内核接口。

handler 严格沿用现有范式（`NAME` / `SCHEMA` / `async def handle(kit, ...)` / `DEFINITION`，见 `handlers/skeleton.py`）。它们**不产出 chunk**，只返回文本（作为 `role=tool` 消息回灌给模型）；内部调用 `skill_core` 的注入式 registry。

**`skills_list`**

```python
NAME = "skills_list"
SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "列出当前可用技能（仅 name + description）。需要某技能的完整指令时用 skill_view(name) 加载。",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "description": "可选：按类别过滤"}}},
    },
}

async def handle(kit, category: str | None = None) -> str:
    return render_skills_list(get_registry(), enabled_tools=kit.enabled_tools, category=category)

DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
```

**`skill_view`**

```python
NAME = "skill_view"
SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "加载某个技能的完整指令（Level 1）；传 path 可加载其附带参考文件（Level 2，如 'templates/report-outline.md'）。",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "技能名（见 skills_list / 技能索引）"},
            "path": {"type": "string", "description": "可选：技能目录下的相对文件路径"}},
            "required": ["name"]},
    },
}

async def handle(kit, name: str, path: str | None = None) -> str:
    reg = get_registry()
    if path:
        content = reg.get_file(name, path)
        return content or f"技能 {name} 下未找到文件 {path}。"
    skill = reg.get(name)
    return skill.body if skill else f"未找到技能 {name}（用 skills_list 查看可用技能）。"

DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
```

### 6.4 接入 `_resolve_turn_context`（`chat_service.py`）

当前 `agent_mode=True` 时的 `enabled_tools`（约 chat_service.py:390）追加两个技能工具，并在构造 system prompt 时注入技能索引：

```python
_enabled_tools = (
    ("search_knowledge_base", "context_window", "drill_down", "skeleton",
     "roll_up", "read_chunks", "read_image_chunks", "grep_chunks",
     "skills_list", "skill_view")            # ← 新增
    if _agent_mode else None
)

# 仅 agent_mode 下注入技能索引（RAG 单轮模式无工具循环，不挂技能）
# get_registry() 取应用启动时注入好 MySQL session 的 skill_core 单例（见 §6.1）
_skills_index = get_registry().build_index(set(_enabled_tools)) if _agent_mode else None

sys_prompt = (
    request.custom_system_prompt
    or session.system_prompt
    or build_chat_system_prompt(
        enabled_tools=_enabled_tools,
        scope=scope_dict,
        skills_index=_skills_index,          # ← 新增槽位
    )
)
```

`build_chat_system_prompt` 模板增加 `{skills_index}` 槽位（默认空串，向后兼容）：放在 `{tools_description}` 之后、`{custom_addendum}` 之前。

> **设计取舍**：技能索引只在 `agent_mode=True` 注入。纯 RAG 单轮路径（`agent_mode=False`）没有工具循环，模型无法 `skill_view`，故不挂技能，保持其轻量。

**Slash 强制召唤（explicit invocation）**：当用户在输入框用 `/research-report ...` 显式指定技能时，`ChatRequest` 携带 `forced_skill_names: list[str]`。此时**绕过「模型自主决定是否加载」的路径，直接把这些技能正文注入**（作为高优先级指令块拼到 system prompt，或作为前置 `role=user` 提示），确保模型必定遵循——这等价于 Hermes 的 `/skill-name` 语义（用户显式 = 显式同意 = 强制加载）。停用/不存在的强制技能跳过并附一行说明。

```python
# _resolve_turn_context 内，构造 system prompt 前
_reg = get_registry()
_forced = [n for n in (request.forced_skill_names or []) if _reg.get(n)]
_forced_block = build_forced_skills_block(_forced) if _forced else None
# build_chat_system_prompt(..., skills_index=_skills_index, forced_skills=_forced_block)
```

### 6.5 技能管理与召唤（CRUD API + Slash 接口）

> 本节是 §3.3.2 的**独立管理服务 `SkillService`**：对核心包 `skill_core`（registry + repository + 安全扫描算法）的封装，**不含任何 agent 运行时逻辑**。**作为独立进程部署**，独占共享 MySQL，对外暴露 REST API（见 §3.3.5）；前端与各后端都通过 HTTP 调用它；写后调用 `registry.invalidate()` 触发索引重建，版本号递增。

`SkillService` 作为独立服务进程（`skill-service/`），承载技能的全部读写逻辑，写操作后调用 `registry.invalidate()` 让索引重建并递增版本号。

**`SkillService`（`skill-service/skill_service.py`，独立进程）**——管理面唯一编排者，路由层只做参数校验与序列化：

```python
class SkillService:
    def __init__(self, registry: SkillRegistry, repo: SkillRepository):
        self._registry = registry      # 进程内单例（skill-service 自己用）
        self._repo = repo              # 独占 MySQL（MySQLSkillRepository，仅 skill-service 内部使用）

    # —— 读（侧栏 / slash / 详情）——
    def list(self, *, q: str | None = None, enabled_only: bool = False) -> list[SkillDescriptor]:
        ...                            # 经 registry.list_descriptors() 合并 builtin+custom 后过滤
    def get(self, name: str) -> Skill: ...          # 含 body；不存在 → NotFound

    # —— 写（仅作用于 custom；写后必 invalidate）——
    def create(self, raw_md: str) -> SkillDescriptor:
        rec = parse_skill_md(raw_md)                # 解析 frontmatter+body（skill_core.loader）
        self._assert_valid_name(rec.name)           # ^[a-z][a-z0-9_-]*$ 且全局唯一（含 builtin）
        scan = scan_content(rec.body)               # 写入期安全扫描（§10）
        if not scan.ok: raise SkillRejected(scan.hits)
        self._repo.create(rec); self._registry.invalidate(); return ...

    def update(self, name: str, raw_md: str) -> SkillDescriptor:
        self._assert_custom(name)                   # 内置 → Forbidden(403)
        ...                                          # 同 create 的校验/扫描，再 repo.update + invalidate

    def set_enabled(self, name: str, enabled: bool) -> None:
        self._assert_exists(name)                   # builtin 与 custom 均可启停
        self._repo.set_state(name, enabled); self._registry.invalidate()

    def delete(self, name: str) -> None:
        self._assert_custom(name)                   # 内置 → Forbidden(403 内置技能不可删除)
        self._repo.delete(name); self._registry.invalidate()
```

> 异常映射（路由层统一处理）：`NotFound→404`、`Forbidden→403`、`SkillRejected→422`（含命中规则）、`DuplicateName→409`。`agent_apps` 等只读后端**不实例化 `SkillService`**，因此天然没有写入口（§3.3.6 红线）。

| 方法 & 路径 | 用途 | 备注 |
|---|---|---|
| `GET /skills` | 列出全部技能（侧栏 + slash 自动补全） | 返回 descriptor（name/description/category/source/enabled/deletable）；支持 `?q=` 前缀过滤 |
| `GET /skills/{name}` | 技能详情（含正文 body） | 侧栏「查看」 |
| `POST /skills` | 创建自定义技能 | 校验 frontmatter / name 唯一 / 安全扫描（§10）；`source=custom` |
| `PUT /skills/{name}` | 编辑自定义技能 | 内置技能 → `403` |
| `PATCH /skills/{name}/enabled` | 启用 / 停用 | 写 `skill_state`，内置与自定义均可 |
| `DELETE /skills/{name}` | 删除自定义技能 | 内置技能 → `403 内置技能不可删除` |

- **slash 召唤数据源**：前端输入 `/` 时调用 `GET /skills?enabled=true` 拿到技能名 + description 列表，在前端做按字母前缀/模糊匹配的自动补全（数据量小，无需服务端搜索）。
- **创建校验**：解析提交的 SKILL.md（frontmatter + body）；`name` 必须匹配 `^[a-z][a-z0-9_-]*$` 且全局唯一；`description` 非空；过安全扫描后入库。

---

## 7. 渐进式披露的完整时序（本系统）

```
用户提问「帮我把 X 主题综合成一份调研报告」
  │
  ▼
_resolve_turn_context：system prompt 注入技能索引(Level0) + 启用 skills_* 工具
  │
  ▼
第1轮 astream：模型看到 research-report 的 description → 判断相关
  → tool_call: skill_view(name="research-report")
  │
  ▼
skill_view 返回 SKILL.md 正文(Level1) 作为 role=tool 消息
  │
  ▼
第2~N轮：模型遵循 Procedure，编排既有工具
  → search_knowledge_base / drill_down / read_chunks ... 捞证据
  → （可选）skill_view(name, "templates/report-outline.md") 取结构模板(Level2)
  │
  ▼
最终轮：按模板综合成带 [cN] 引用的结构化报告并输出，执行 Verification 自检
```

---

## 8. 首期技能：调研报告生成（research-report）

### 8.1 定位

把一个调研性问题，**先用检索工具把多文档证据捞齐，再综合成一份结构化、带 `[cN]` 引用溯源的调研报告**。这是相对通用 agent 的差异化点：**报告每个论断都可溯源到知识库片段**。

### 8.2 产出形态（首期）

- **本期**：在对话流里直接输出**带引用的结构化 Markdown 报告**（前端已支持 markdown + KaTeX + `[cN]` 引用渲染），**无需任何新底座**。
- **未来**：导出 Word/PDF/PPT 需要先补一个通用「代码执行/沙箱」Tool（见 §13 演进），届时报告技能可追加「导出」步骤。本期不做。

### 8.3 报告结构（写进技能 / 模板）

1. 摘要（结论先行）
2. 背景与范围
3. 分主题论述（每段论断后标 `[cN]`）
4. 横向对比 / 关键发现（适当用 markdown 表格）
5. 结论与不确定性（证据不足处明确标注「知识库未覆盖」）
6. 参考片段清单（列出用到的 `cN` → 来源文档）

### 8.4 完整 SKILL.md 见附录 A。

---

## 9. 缓存与性能

- **Level 0 索引缓存**：进程内字典，key = `(内置目录指纹, 自定义技能表版本号, enabled_tools 集合)`（与 §6.1 注册表失效键一致）。内置目录指纹由各 `SKILL.md` 的 `mtime/size` 聚合（对齐 Hermes manifest 思路）；自定义技能表版本号在每次 CRUD（`registry.invalidate()`）时递增。
- **磁盘快照**（增强项，可后置，仅缓存内置技能）：把解析后的 descriptor 落 `./skills/.skills_prompt_snapshot.json`，冷启动复用，按 manifest 校验失效。自定义技能来自 DB，不进磁盘快照。
- 首期技能数量个位数，索引构建成本可忽略；缓存主要为后续技能增长预留。
- **不破坏 prompt 缓存**：技能索引在 `_resolve_turn_context` 内确定性生成，内容稳定时上游 LLM 的 prompt 缓存仍可命中。

---

## 10. 安全

> ⚠️ 本期已开放**用户通过前端创建自定义技能**，等于引入了「用户可写的、会进 prompt 的内容」。因此内容安全不再是「后续」，而是创建接口的**必做校验**。

| 风险 | 首期措施 | 后续 |
|---|---|---|
| 自定义技能 = prompt 注入面 | `POST /skills` 创建时做内容扫描（对齐 `skills_guard.py`：检测越权指令、数据外泄、可疑命令模式），命中告警/拦截 | 信任分级、人工审核队列 |
| 自定义技能诱导滥用工具 / 越权 | 技能只能「编排已有工具」，无法新增能力；工具层 `_enforce_scope`、`max_tool_rounds`、权限照常生效，技能无法绕过 | 为技能声明建议轮数 |
| 路径穿越（`skill_view` 的 path） | `get_file` 仅允许内置技能目录内相对路径，拒绝 `..` / 绝对路径；自定义技能无文件附件 | — |
| 重名遮蔽 / 误删内置 | 创建时 name 全局唯一校验；删除接口对内置技能硬性 `403` | — |
| scope 越界 | 技能只编排已有工具，工具层 `_enforce_scope` 守卫照常生效 | — |
| 权限（谁能管理技能） | 复用现有鉴权中间件；技能管理接口要求登录用户 | 区分管理员 / 普通用户的技能权限 |

---

## 11. 前端改动（`AI-site`）

技能机制本身全自动（模型自主 `skill_view`）即可工作；本节是按产品要求新增的**两个交互能力**：① 输入框 `/` 召唤；② 左侧「技能」栏目做技能 CRUD。

### 11.1 输入框 `/` 召唤技能（对齐 Cursor）

- **触发**：在对话输入框（`components/knowledge/KnowledgeChatPanel.tsx` 一带）行首键入 `/` 时，弹出技能自动补全浮层。
- **数据源**：`GET /skills?enabled=true`（首次打开缓存即可）。
- **搜索**：随用户继续输入 `/res...` 按**技能名字母前缀 + 模糊匹配**实时过滤、键盘上下选择、回车选中（Cursor 体验）。每项展示 `name` + 一行 `description`，并标注来源徽标（内置 / 自定义）。
- **选中效果**：把所选技能绑定到本次发送（chip 形式展示在输入框，可取消）；发送时在请求体带 `forced_skill_names: ["research-report"]`。
- **后端语义**：见 §6.4「Slash 强制召唤」——被显式召唤的技能正文强制注入，模型必定遵循。
- **API 客户端**：在 `lib/api/` 下新增 `skills.ts`（封装上述 REST 接口）；`lib/api/chat.ts` 的发送参数增加可选 `forced_skill_names`。

### 11.2 左侧「技能」栏目（自定义技能管理）

在左侧导航新增「技能」入口（与「知识库」并列），对应新页面 `app/skills/page.tsx` + `components/skills/`：

- **技能列表**：分组展示「内置」「自定义」；每项显示 name / description / 类别 / 启停开关 / 来源徽标。
- **查看**：点击进入详情，渲染 SKILL.md（frontmatter + 正文 Markdown）。
- **创建**：表单 / Markdown 编辑器填写 `name`、`description`、正文（按 §5 结构提供模板骨架），提交 `POST /skills`。
- **启用 / 停用**：开关调 `PATCH /skills/{name}/enabled`；停用后该技能不进索引、不可被 `/` 召唤。
- **删除**：仅自定义技能可删（`DELETE /skills/{name}`）；**内置技能的删除按钮置灰并提示「内置技能不可删除」**（前端按 `deletable=false` 判定，后端 `403` 兜底）。

| 组件（新增） | 职责 |
|---|---|
| `components/skills/SkillList.tsx` | 内置/自定义分组列表 + 启停开关 + 删除 |
| `components/skills/SkillDetail.tsx` | 查看技能详情（Markdown 渲染） |
| `components/skills/SkillEditor.tsx` | 创建 / 编辑自定义技能（带 SKILL.md 模板） |
| `components/skills/SlashSkillMenu.tsx` | 输入框 `/` 自动补全浮层 |

### 11.3 流式提示（建议增强）

在流式事件里增加「已加载技能 research-report」提示条（复用现有 tool 调用事件流，新增一种 skill 事件类型），让用户感知技能被触发。

---

## 12. 实施计划

| 阶段 | 内容 | 预估 |
|---|---|---|
| P1 | 核心包 `skill_core`：types/loader/registry/index 渲染 + `SkillRepository` 端口 + 默认 MySQL 适配（含 DDL）+ 安全扫描算法；合并 builtin + custom 两源 | 1.5~2 天 |
| P2 | 本系统 Agent 适配：`skills_list` / `skill_view` 两个工具 + 注册 + 启动处构建 registry（从 skill-service 拉取 descriptors，Level-0 索引缓存在进程内） | 0.5 天 |
| P3 | 接入 `_resolve_turn_context` + `build_chat_system_prompt` 槽位 + `forced_skill_names` | 0.5 天 |
| P4 | 编写 `research-report/SKILL.md` + 模板 | 0.5 天 |
| P5 | 独立服务 `SkillService`（`skill-service/`）：封装核心包 + REST API + MySQL 独占 + 表迁移单一所有者；前端与各后端通过 HTTP 调用 | 1.5~2 天 |
| P6 | 前端：左侧技能栏（增删改查启停） | 1~1.5 天 |
| P7 | 前端：输入框 `/` 召唤自动补全 + `forced_skill_names` 接线 | 0.5~1 天 |
| P8 | 缓存 + 单元/集成测试 | 0.5~1 天 |
| 合计（含内核 + 前端 + 管理后台） | 完整可用 | **约 6.5~10 天** |

> 若要先验证核心机制，可只做 P1~P4 + P8（约 3~4 天）跑通自动触发的内置技能，再迭代 P5~P7 的管理/召唤能力。
> `agent_apps` 后续接入：**复用 P1 的核心包**，配置同一个 skill-service URL（调 REST API 获取技能数据），只新增「框架原生 tool 适配 + 各 agent 注入索引」一份薄层（约 0.5~1 天），无需重做核心包/存储/管理服务/前端。

---

## 13. 测试方案

- **单元**：frontmatter 解析（正常 / 畸形回退）；条件激活过滤（requires/fallback）；`get_file` 路径穿越防护；索引渲染快照；builtin+custom 合并与重名校验；安全扫描命中用例。
- **API**：技能 CRUD 全流程（创建→列出→详情→启停→删除）；内置技能删除/编辑返回 `403`；创建重名拒绝；停用技能不进索引。
- **集成（自动触发）**：`agent_mode=True` 提调研类问题 → 断言模型发起 `skill_view(research-report)` → 断言后续编排检索工具 → 断言最终回答含 `[cN]` 引用。
- **集成（slash 召唤）**：请求带 `forced_skill_names=["research-report"]` → 断言技能正文被强制注入、模型遵循。
- **前端**：`/` 自动补全按字母过滤；内置技能删除按钮置灰；创建/启停/删除回链。
- **回归**：`agent_mode=False`（纯 RAG）不受影响；现有 8 工具行为不变。

---

## 14. 风险与权衡

- **模型不主动加载技能**：靠 §2.3 强制扫描提示语缓解；测试中重点验证触发率。
- **技能正文过长稀释上下文**：控制 `SKILL.md` 正文精炼，详尽内容下沉到 `templates/` 用 Level 2 按需取。
- **与 `custom_system_prompt` 冲突**：当会话使用了完全自定义 system prompt（`request.custom_system_prompt` / `session.system_prompt`）时，技能索引不会自动注入——这是预期行为（用户显式接管了 prompt）。如需兼容，可在文档中提示其手动保留技能索引槽位。

---

## 15. 后续演进（非本期）

1. **代码执行/沙箱 Tool**：解锁报告/图表/PPT 的**文件导出**，一次投入解锁一批产出类技能。
2. **更多技能**：知识结构图（mermaid，复用 skeleton）、多文档对比表、单文档精读、强制溯源核验等（零底座优先）。
3. **`skill_manage` 自创建/自进化**：agent 自动沉淀流程为技能（本期已支持人工前端创建，此项是让 agent 自动写）。
4. **自定义技能增强**：多文件附件（Level 2）、按用户隔离的私有技能、管理员审核队列。
5. **技能 Hub / taps**：导入 agentskills.io 生态（openai/skills、anthropics/skills 等），配合信任分级。
6. **磁盘快照缓存**：技能规模增长后启用。

---

## 附录 A：`skills/research/research-report/SKILL.md`（完整草案）

```markdown
---
name: research-report
description: >-
  把一个调研性问题综合成结构化、带 [cN] 引用溯源的调研报告。先用检索工具在知识库内
  广泛取证（可多文档），再按「摘要→背景→分主题论述→横向对比→结论与不确定性→参考清单」
  组织成报告。当用户要求"调研/综述/汇总/出一份报告/系统梳理某主题"时加载。
version: 1.0.0
metadata:
  tags: [research, report, multi-doc, citation, synthesis]
  category: research
  requires_tools: [search_knowledge_base, read_chunks]
---

# 调研报告生成

## When to Use
当用户的诉求是「**综合性梳理 / 调研 / 综述 / 汇总成一份报告**」而非单点问答时加载本技能，例如：
- "帮我调研一下 X，出一份报告"
- "把知识库里关于 Y 的内容系统梳理一下"
- "对比一下这几篇文档在 Z 上的异同并总结"
普通单点事实问答**不要**加载本技能，直接回答即可。

## Procedure
1. **拆解主题**：把用户问题拆成 3~6 个子主题/调研维度，明确报告范围。
2. **广泛取证**：对每个子主题用 `search_knowledge_base` 检索（可用不同角度多次检索）；
   命中文档后，必要时用 `drill_down` / `skeleton` 定位章节，用 `read_chunks` 取关键片段全文。
   - 证据要覆盖多文档；注意去重与时效（同一事实有新旧版本时优先新的，并在报告中标注）。
3. **（可选）取结构模板**：`skill_view(name="research-report", path="templates/report-outline.md")`。
4. **综合成报告**，严格按下列结构输出（Markdown）：
   1. **摘要**：3~5 句，结论先行。
   2. **背景与范围**：本报告调研了什么、覆盖哪些来源。
   3. **分主题论述**：每个子主题一节；**每条论断后标注 `[cN]` 引用**，可多标 `[c1][c3]`。
   4. **横向对比 / 关键发现**：信息适合对比时用 markdown 表格。
   5. **结论与不确定性**：给出结论；证据不足处**明确写「知识库未覆盖」**，不得编造。
   6. **参考片段**：列出报告中用到的每个 `cN` 对应的来源文档/章节。
5. **自检**（见 Verification）后再输出最终报告。

## Pitfalls
- **不要凭空编造引用号**：`cN` 必须确实来自工具返回结果；不确定就不标，绝不杜撰。
- **不要只检索一次就下笔**：调研报告需要多角度、多文档取证；但也要**适可而止**，证据足够即停，避免无意义反复检索。
- **不要把 preview 当全文**：`search_knowledge_base` 等返回的是约 200 字预览；关键论据被截断时用 `read_chunks` 取全文再引用。
- **公式格式**：行内 `$...$`、块级 `$$...$$`，禁用 `\( \)` / `\[ \]`（否则前端无法渲染）。
- **范围守卫**：folder/单文档会话下，只在允许范围内取证，越界文档会被服务端拒绝。
- **本期不导出文件**：直接在对话里输出 Markdown 报告，不要尝试生成 .docx/.pdf（暂无导出工具）。

## Verification
输出前逐项确认：
- [ ] 每个子主题都有至少一条带 `[cN]` 的证据支撑？
- [ ] 所有 `cN` 都真实出现在工具返回结果里，无杜撰？
- [ ] 证据不足的部分是否如实标注「知识库未覆盖」？
- [ ] 报告结构完整（摘要/背景/论述/对比/结论/参考）？
- [ ] 公式与引用格式符合前端渲染约束？
```

> 附带模板 `templates/report-outline.md` 可放一份更详细的小标题清单，供模型在长报告时按 Level 2 加载，保持 `SKILL.md` 正文精炼。
