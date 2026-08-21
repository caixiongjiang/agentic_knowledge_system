# 配置档案

公共策略只在 `config/config.toml` 和 `config/components.json`。
随网关变化的模型身份、角色采样参数、思考/多模态/窗口放在本目录。

| 档案 | 目录 | 何时使用 |
|---|---|---|
| LiteLLM | `profiles/litellm/` | `MODEL_GATEWAY_TYPE=litellm` |
| Model Lake | `profiles/model_lake/` | `MODEL_GATEWAY_TYPE=model_lake` |

切换：

```bash
# 设置模型网关类型（配置档案将自动切换到对应 profile）
MODEL_GATEWAY_TYPE=model_lake
```

每个档案包含：

- `models.toml`
  - `[presets.<role>]`：抽取 pipeline / 检索组件 / 工具用的角色（`model` + temperature / max_tokens / timeout / thinking_level）
  - `[visible].models`：前端对话主模型白名单（`/api/chat/models` 只返回这些）
- `thinking_models.json`：思考白名单。`supports_thinking_effort=true` 才填 `default` / `thinkingLevelMap`；否则只写 `reasoning` + `supports_thinking_effort=false`。
- `multimodal_models.json` / `long_context_models.json`

不要把网关 URL、Auth、密钥写进档案。那些只属于 `.env`。
