# JustTranslate 思考模式官方注册表条目全景规范 (v3 Cleaned)

> **版本**：v3.0  
> **核验基准日**：2026-09-16  
> **四维主键架构**：`provider + protocol/endpoint + model_family + model_id/pattern`  
> **依据规范**：`思考模式机制纠正文档_v3.md`

---

## 一、 核心强制规则：能力解析 6 级优先级 (CapabilityResolver)

运行时严格按照以下 6 级优先级裁定模型的思考/推理控制行为：

```text
1. 用户手动覆盖（User Override）
2. 官方 Capability Registry
3. Provider 官方返回的模型 Metadata / Capability Metadata
4. 主动探测缓存（Probe Cache）
5. 模型名启发式（Heuristic Hint）
6. 保守默认（不注入任何非标准思考参数）
```

### 关键约束与安全防线：
1. **用户覆盖优先且严禁伪造**：用户显式指定“开启”或“关闭”时，Resolver 优先采用用户设置；若模型官方能力与用户设置冲突（例如对纯推理模型要求关闭，或对普通对话模型要求开启思考），必须向用户明确反馈能力不可满足，**严禁静默退化或伪造成功**。
2. **官方注册表基准确证**：注册表条目必须具备 `authority_url`、`authority_scope`、`evidence_level` 与 `verified_at`。探针结果不得覆盖官方已确认的 `forced_on` / `cannot_disable` 限制。
3. **启发式名称仅作提示**：模型名称中包含 `r1`、`reasoner`、`thinking`、`o3` 等关键字，仅生成探索性提示（`capability_hint`），绝对不决定具体请求字段。
4. **输出双通道物理隔离**：思维链输出（Reasoning Trace）与最终译文（Content）在底层流式处理中严格物理隔离，思维链默认不污染主译文区，不持久化至主翻译历史库。

---

## 二、 官方注册表条目全景对照表 (v3 最新主流基线)

| 序号 | Provider | Protocol / Endpoint | Model Family & ID Patterns | 控制方式 (`ControlKind`) | 开启与强度语法 | 能否彻底关闭？ | 官方关闭语法 / 降级策略 | 思维链输出解析路径 | 特殊约束与防踩坑要点 | 证据等级 & 官方权威来源 |
| :---: | :--- | :--- | :--- | :---: | :--- | :---: | :--- | :--- | :--- | :--- |
| **1** | `openai` | `openai_responses`<br>`/v1/responses` | `gpt-5.6*`<br>`gpt-5.6-sol*`<br>`gpt-5.6-terra*`<br>`gpt-5.6-luna*` | `effort_enum` | `reasoning: {"effort": "low"\|"medium"\|"high"\|"xhigh"\|"max"}` | **能** | `reasoning: {"effort": "none"}` | `output[type=reasoning].content`<br>`output[type=reasoning].summary`<br>`response.reasoning_text.delta` | 2026-09 最新主流家族；支持完整 6 档 effort | `official_family`<br>[OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) |
| **2** | `openai` | `openai_responses`<br>`/v1/responses` | `gpt-5-pro*` | `effort_enum` | `reasoning: {"effort": "high"}` | ❌ **不能** | 强制高推理，不可关闭 | `output[type=reasoning].content` | 仅支持 `"high"` 档位，传其他档位返回 400 | `official_exact`<br>[OpenAI Models](https://platform.openai.com/docs/models) |
| **3** | `openai` | `openai_responses`<br>`/v1/responses` | `gpt-5.1*`<br>`gpt-5.2*`<br>`gpt-5-turbo*` | `effort_enum` | `reasoning: {"effort": "low"\|"medium"\|"high"}` | **能** | `reasoning: {"effort": "none"}` | `output[type=reasoning].content` | 标为 legacy；支持 none 关闭 | `official_family`<br>[OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) |
| **4** | `openai` | `openai_chat`<br>`/v1/chat/completions` | `gpt-5.6*`<br>`gpt-5.6-sol*`<br>`gpt-5.6-terra*`<br>`gpt-5.6-luna*` | `effort_enum` | `reasoning_effort: "low"\|"medium"\|"high"\|"xhigh"\|"max"` | **能** | `reasoning_effort: "none"` | `choices[0].delta.content` | 协议独立条目；Chat Completions 端点官方支持 `none` 关闭 | `official_family`<br>[OpenAI Reasoning Guide](https://platform.openai.com/docs/guides/reasoning) |
| **5** | `openai` | `openai_chat`<br>`/v1/chat/completions` | `o1*`<br>`o3*`<br>`o4*` | `effort_enum` | `reasoning_effort: "low"\|"medium"\|"high"` | ❌ **不能** | 官方不支持关闭（Chat 拒绝 none/disabled） | `usage.completion_tokens_details.reasoning_tokens` | 标为 legacy；严禁自定义 `temperature`；不支持惩罚项 | `official_family`<br>[OpenAI Reasoning Guide](https://platform.openai.com/docs/guides/reasoning) |
| **6** | `openai` | `openai_chat`<br>`/v1/chat/completions` | `gpt-4o*`<br>`gpt-4.1*`<br>`gpt-4.5*` | `none` | 无思考能力 | **能** | 默认纯文本模式 | 无 | **严禁注入 `reasoning_effort`**，否则触发 400 报错 | `official_family`<br>[OpenAI Models](https://platform.openai.com/docs/models) |
| **7** | `anthropic` | `anthropic_messages`<br>`/v1/messages` | `claude-opus-4-6*`<br>`claude-sonnet-4-6*` | `adaptive_effort` | `thinking: {"type": "adaptive"}`<br>`output_config: {"effort": "low"\|"high"}` | **能** | **完全省略 `thinking` 参数** | `content_block_delta`<br>`delta.type="thinking_delta"` | 默认关闭；开启思考时 `temperature` 锁定为 1.0；忽略 `top_k` | `official_family`<br>[Claude Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) |
| **8** | `anthropic` | `anthropic_messages`<br>`/v1/messages` | `claude-opus-4-7*`<br>`claude-opus-4-8*` | `adaptive_effort` | `thinking: {"type": "adaptive"}`<br>`output_config: {"effort": "low"\|"high"}` | **能** | **完全省略 `thinking` 参数** | `content_block_delta`<br>`delta.type="thinking_delta"` | 默认关闭；**严禁传入 `budget_tokens`（4.7+ 必报错 400）** | `official_family`<br>[Claude Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) |
| **9** | `anthropic` | `anthropic_messages`<br>`/v1/messages` | `claude-sonnet-5*` | `adaptive_effort` | `thinking: {"type": "adaptive"}` | **能** | `thinking: {"type": "disabled"}` | `content_block_delta`<br>`delta.type="thinking_delta"` | **思考默认开启！省略不等于关闭，必须传 disabled 才能关闭** | `official_family`<br>[Claude Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) |
| **10** | `anthropic` | `anthropic_messages`<br>`/v1/messages` | `claude-opus-5*` | `adaptive_effort` | `thinking: {"type": "adaptive"}` | **能** | `thinking: {"type": "disabled"}` | `content_block_delta`<br>`delta.type="thinking_delta"` | 默认开启；仅在 effort <= high 时允许传 disabled 关闭 | `official_family`<br>[Claude Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) |
| **11** | `anthropic` | `anthropic_messages`<br>`/v1/messages` | `claude-fable-5*`<br>`claude-mythos-5*` | `adaptive_effort` | 强制自适应思考 | ❌ **不能** | 官方不支持关闭，思考为唯一模式 | `content_block_delta`<br>`delta.type="thinking_delta"` | 传 disabled 报错 400 | `official_family`<br>[Claude Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) |
| **12** | `anthropic` | `anthropic_messages`<br>`/v1/messages` | `claude-3-7-sonnet*` | `none` | 已退役 | — | — | — | **已于 2026-02-19 退役**，移出主流列表 | `official_exact`<br>[Claude Deprecations](https://docs.anthropic.com/en/docs/about-claude/model-deprecations) |
| **13** | `gemini` | `gemini_content`<br>`:streamGenerateContent` | `gemini-2.5-flash*` | `token_budget` | `thinkingConfig: {"thinkingBudget": N}` | **能** | `thinkingConfig: {"thinkingBudget": 0}` | `candidates[0].content.parts[]`<br>筛选 `thought: true` | 2.5 Flash 专属关闭语法；严禁将 0 推广至 Pro | `official_exact`<br>[Gemini Thinking Docs](https://ai.google.dev/gemini-api/docs/thinking) |
| **14** | `gemini` | `gemini_content`<br>`:streamGenerateContent` | `gemini-2.5-pro*` | `token_budget` | `thinkingConfig: {"thinkingBudget": N}` | ❌ **不能** | 设 0 必报 400 `INVALID_ARGUMENT` | `candidates[0].content.parts[]`<br>筛选 `thought: true` | Pro 纯推理不可关闭 | `official_exact`<br>[Gemini Thinking Docs](https://ai.google.dev/gemini-api/docs/thinking) |
| **15** | `gemini` | `gemini_content`<br>`:streamGenerateContent` | `gemini-3.8-flash*`<br>`gemini-3.7-flash*` | `effort_enum` | `thinkingConfig: {"thinkingLevel": "low"\|"medium"\|"high"}` | ❌ **不能** | 不支持 minimal；思考不可关闭 | `candidates[0].content.parts[]`<br>筛选 `thought: true` | 剔除 MED 枚举；支持 low, medium, high | `official_exact`<br>[Gemini Thinking Docs](https://ai.google.dev/gemini-api/docs/thinking) |
| **16** | `gemini` | `gemini_content`<br>`:streamGenerateContent` | `gemini-3.6-flash*`<br>`gemini-3.5-flash*` | `effort_enum` | `thinkingConfig: {"thinkingLevel": "minimal"\|"low"\|"medium"\|"high"}` | ❌ **不能** | **`minimal` 不等于关闭，官方保留基础推理** | `candidates[0].content.parts[]`<br>筛选 `thought: true` | 支持 4 档位；但不能关闭思考 | `official_exact`<br>[Gemini Thinking Docs](https://ai.google.dev/gemini-api/docs/thinking) |
| **17** | `gemini` | `gemini_content`<br>`:streamGenerateContent` | `gemini-3.1-pro*`<br>`gemini-3-pro*` | `effort_enum` | `thinkingConfig: {"thinkingLevel": "low"\|"high"}` | ❌ **不能** | 官方不支持关闭 | `candidates[0].content.parts[]`<br>筛选 `thought: true` | Pro 预览版仅支持 low 与 high 档位 | `official_exact`<br>[Gemini Thinking Docs](https://ai.google.dev/gemini-api/docs/thinking) |
| **18** | `deepseek` | `openai_chat`<br>`/v1/chat/completions` | `deepseek-flash*`<br>`deepseek-v4-pro*`<br>`deepseek-v4*` | `thinking_object` | `thinking: {"type": "enabled"}`<br>或 `reasoning_effort: "low"` | **能** | `thinking: {"type": "disabled"}`<br>或 `reasoning_effort: "none"` | `choices[0].delta.reasoning_content` | 2026 最新主模型；思考模式下温度惩罚项被忽略；`top_p >= 0.95` | `official_family`<br>[DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) |
| **19** | `deepseek` | `deepseek_responses`<br>`/v1/responses` | `deepseek-flash*`<br>`deepseek-v4-pro*` | `effort_enum` | `reasoning: {"effort": "low"\|"high"\|"max"}` | **能** | `reasoning: {"effort": "none"}` | `output[type=reasoning].content` | 规范运行时 endpoint；采用 Responses API 结构 | `official_family`<br>[DeepSeek API Guide](https://api-docs.deepseek.com/guides/thinking_mode/) |
| **20** | `dashscope` | `openai_chat`<br>`/compatible-mode/v1` | `qwen3.8*` | `effort_enum` | `reasoning_effort: "low"\|"medium"\|"xhigh"`<br>或 `enable_thinking: true` | **能** | `reasoning_effort: "none"`<br>或 `enable_thinking: false` | `choices[0].delta.reasoning_content` | **`reasoning_effort` 与 `thinking_budget` 严格互斥，禁同时传** | `official_family`<br>[阿里百炼 API 指南](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions) |
| **21** | `dashscope` | `dashscope_responses` | `qwen*` | `effort_enum` | `reasoning: {"effort": "low"\|"medium"\|"high"}` | **能** | `reasoning: {"effort": "none"}` | `output[type=reasoning].content` | 百炼新版 Responses 接口优先推荐 `reasoning.effort` | `official_family`<br>[阿里百炼 Responses 接口](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-responses) |
| **22** | `dashscope` | `openai_chat`<br>`/compatible-mode/v1` | `qwq*` | `boolean` | `enable_thinking: true` | ❌ **不能** | 专用思考模型，无明确关闭证据时不继承关闭能力 | `choices[0].delta.reasoning_content` | 独立条目，不盲目继承普通 Qwen 的 can_disable | `official_family`<br>[阿里百炼 API 指南](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions) |
| **23** | `zhipu` | `openai_chat`<br>`/api/paas/v4` | `glm-4.5*`<br>`glm-4.6*`<br>`glm-4.7*`<br>`glm-5*`<br>`glm-5.1*`<br>`glm-5.2*` | `thinking_object` | `thinking: {"type": "enabled"}` | **能** | `thinking: {"type": "disabled"}` | `choices[0].delta.reasoning_content` | **纠正：GLM-4.7 官方支持 type: disabled 关闭！** 与百炼托管 GLM 严格隔离 | `official_family`<br>[Z.AI Thinking 指南](https://docs.z.ai/guides/capabilities/thinking) |
| **24** | `zhipu` | `openai_chat`<br>`/api/paas/v4` | `glm-5.3*`<br>`glm-5.3-flash*` | `effort_enum` | `thinking: {"type": "enabled"}`<br>`reasoning_effort: "low"\|"high"\|"max"` | ❌ **不能** | **官方强制深度思考（Forced On）**；传 disabled 报错 400；快翻建议设 `reasoning_effort: "low"` | `choices[0].delta.reasoning_content` | **2026-08 最新发布**；包含 744B 旗舰与 320B 原生多模态 Flash；默认 effort 为 max；推荐 `top_p: 0.95` | `official_family`<br>[Z.AI 迁移与思考指南](https://docs.z.ai/guides/overview/migrate-to-glm-new) |
| **25** | `volcengine`| `openai_chat`<br>`/api/v3` | `doubao-1.5-pro*`<br>`doubao-seed*` | `effort_enum` | `reasoning_effort: "low"\|"high"` | **能** | `reasoning_effort: "none"`<br>或 `"minimal"` | `choices[0].delta.reasoning_content` | **删除 `ep-*` 通配！** 仅对明确 Doubao 型号生效；开启时 `top_p >= 0.95` | `official_family`<br>[火山引擎方舟文档](https://www.volcengine.com/docs/82379/1795150) |
| **26** | `ollama` | `ollama_native`<br>`/api/chat` | `qwen3*`<br>`deepseek-r1*`<br>`deepseek-v3.1*` | `boolean` | `think: true` | **能** | `think: false` | `message.thinking`<br>或 `thinking` 顶层字段 | 明确列举的本地思考家族支持布尔开关 | `official_family`<br>[Ollama Thinking](https://docs.ollama.com/capabilities/thinking) |
| **27** | `ollama` | `ollama_native`<br>`/api/chat` | `*gpt-oss*` | `effort_enum` | `think: "low"\|"medium"\|"high"` | ❌ **不能** | 官方不支持关闭 trace，仅可调强度 | `message.thinking` | 严禁向其发送布尔 `think: false` | `official_family`<br>[Ollama Thinking](https://docs.ollama.com/capabilities/thinking) |
| **28** | `ollama` | `ollama_native`<br>`/api/chat` | `*` (未知本地模型) | `none` | 降级为条件能力 | — | 默认保守不注入 | `message.thinking` | **消除 `*` 泛化通配**；未探针确证前不注入任何 think 字段 | `provider`<br>[Ollama Thinking](https://docs.ollama.com/capabilities/thinking) |
| **29** | `vllm` | `vllm_chat`<br>`/v1/chat/completions` | `*` (部署模型) | `model_template_dependent` | 映射 `reasoning_effort` 或 `chat_template_kwargs.enable_thinking: true` | ⚠️ **条件依赖** | 优先传 `reasoning_effort: "none"`，降级传 enable_thinking: false | `choices[0].delta.reasoning`<br>或 `reasoning_content` | **消除必定可关闭假设**；取决于后端模型模板是否声明 enable_thinking 变量 | `provider`<br>[vLLM Reasoning Outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/) |
| **30** | `generic` | `openai_chat`<br>`/v1/chat/completions` | 未知模型 / 自建中转反代 | `none` | 默认不注入任何参数 | — | 默认纯文本普通模式 | `choices[0].delta.content` | **保守默认防御基线**：未经设置页主动探针证实前，绝对不注入任何非标准参数 | 本地工程防御基线 |

---

## 三、 探针优化与验证策略 (关闭探针优先)

1. **“关闭探针”优先于“开启探针”**：
   - JustTranslate 的核心场景之一是快翻、OCR、词典查词需跳过思考过程以降低延迟与 Token 消耗；
   - 对未知模型探针优先验证其 **OFF capability**（如 `reasoning_effort="none"`、`think=false`、`type="disabled"` 等），既省 Token 又最贴合软件实际诉求。
2. **拒绝 200 误判**：
   - HTTP 200 仅代表请求被接受，若返回体中无实体思维链结构或消耗证明，严格判定为 `accepted_but_unverified`，禁止擅自升级为 `confirmed_supported`。

---

## 四、 关键参数约束与安全防护红线

1. **温度（Temperature）互斥性**：
   - Anthropic 开启思考时，`temperature` 必须锁定为 `1.0`；Claude 4.7+ 严禁传 `budget_tokens`。
   - DeepSeek 思考模式下，温度与惩罚项被服务端忽略或正规化，`top_p` 锁定下限为 `0.95`。
2. **Qwen3.8 参数互斥**：
   - `reasoning_effort` 与 `thinking_budget` 严禁同时出现在请求体中，否则直接报 400 错。
3. **HTTP 400 精确重试红线**：
   - 仅当 400 错误信息明确指出思考/推理参数不被支持且尚未输出内容时，允许剥离思考参数重试一次；
   - 用户明确选择“开启思考”（`on`）时，**严禁静默退化为普通模式**谎报成功，必须如实提示用户。
