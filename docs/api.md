# AgentForge API 文档

> 与代码同步维护；完整交互式文档见后端 `/api/swagger-ui`。
> 基础约定：所有接口返回 `Result<T> {code, message, data}`；分页返回 `PageResult<T> {list, total, page, size}`；受保护接口需 `Authorization: Bearer <token>`；`code=0` 为成功。

## 1. 认证 /auth（公开：login、register）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/register | 注册 `{username(3-20), password(6-32), email?}` → UserVO |
| POST | /auth/login | 登录 `{username, password}` → LoginVO `{token, expiresIn, user}` |
| GET | /auth/me | 当前用户信息（需登录）→ UserVO |

错误码：20001 未登录、20004 用户名或密码错误、10004 用户名/邮箱冲突。

## 2. 智能体 /agent（需登录）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /agent/page?page&size&name | 分页（名称模糊；**PRIVATE 仅创建者可见**，PUBLIC 所有人可见）→ PageResult\<AgentVO\> |
| GET | /agent/{id} | 详情（含 systemPrompt/tools/mode/visibility/providerId）→ AgentDetailVO |
| POST | /agent | 创建 `{name, description?, systemPrompt, modelName?, providerId?, temperature?, tools[]?, mode?, workflowId?, visibility?}` |
| PUT | /agent/{id} | 更新（仅创建者） |
| DELETE | /agent/{id} | 删除（仅创建者，逻辑删除） |
| GET | /tools/meta | 工具元数据列表（名称/描述/参数/配置 Schema，前端按 Schema 渲染配置表单） |

> M3 运行模式：`mode` 取值 `chat`（默认，LLM 依据工具 Schema 自主决策 + ReAct 循环）/
> `workflow`（对话消息作为流程输入 `{message}`，答案取工作流输出）；工作流模式必须绑定
> 本人名下的工作流（`workflowId`），未绑定/绑定他人工作流分别返回 10001/20003。
> M3 工具配置：`tools[].toolConfig` 为智能体级工具配置（如 github/web_search 的 api_key），
> 由后端透传 AI 服务在工具执行时注入。
> M4 可见性：`visibility` 取值 PUBLIC（所有登录用户可见可用）/ PRIVATE（默认，仅创建者）。
> 列表过滤私有；详情与聊天对非创建者视为不存在（10003）。
> M4 多模型：`providerId` 绑定模型 Provider（NULL=内置千问云端）；聊天时后端将
> Provider 的 {type, baseUrl, apiKey} 透传 AI 服务，按 Provider 调用对应模型。

错误码：20003 非创建者操作、10003 智能体不存在、10001 参数错误。

## 3. 对话 /chat（需登录）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /chat | 发送消息 `{agentId, sessionId, message}` → ChatVO `{answer, sources[], toolCalls[]}`（同步） |
| POST | /chat/stream | 发送消息（SSE 流式回答，见下方事件协议） |
| GET | /chat/history?agentId&sessionId&page&size | 历史分页（倒序，按会话隔离）→ PageResult\<ConversationVO\>（含 `sources[]` 引用，M2 起落库可回溯） |
| GET | /chat/session/list?agentId | 会话列表（按最后活跃倒序）→ SessionVO[] |
| POST | /chat/session | 新建会话 `{agentId, name?}`（默认「新会话」，首条消息自动命名） |
| DELETE | /chat/session/{id} | 删除会话（逻辑删除，消息历史保留） |

> M2 多会话：`sessionId` 为可选参数，前端始终携带；省略时按旧版语义处理（不隔离历史）。
> 会话删除仅校验本人（20003）；会话名在首条消息成功后自动取消息前 20 字。
> M3 工作流模式：Agent `mode=workflow` 时，/chat 与 /chat/stream 均改为触发绑定工作流执行
> （消息作为输入 `{message}`），答案取流程输出；流式路径按块输出 delta 保持打字机效果。

### SSE 流式接口（POST /chat/stream）

请求体与 `/chat` 一致 `{agentId, sessionId, message}`；响应为 `text/event-stream`（`Cache-Control: no-cache`、`X-Accel-Buffering: no`，Nginx 已关闭缓冲）。事件以空行分隔，`data:` 行为 JSON：

| 事件 type | 字段 | 说明 |
|---|---|---|
| delta | `content` | 回答增量（逐块输出，前端打字机渲染） |
| tool | `name`、`arguments`、`result` | 工具执行完成（M3：ReAct 循环中实时展示工具活动，前端累积为调用记录） |
| done | `answer`、`sources[]`、`toolCalls[]` | 回答结束，携带完整数据（后端在此时落库） |
| error | `code`、`message` | 失败（错误码同下表）；流结束但未收到 done/error 视为连接中断 |

> M3 工具调用：`toolCalls` 为展示用字符串数组（如 `calculator({"expression": "2+3*4"}) → 14`）；
> LLM 依据工具 Schema 自主决策（OpenAI 兼容 tools 参数），
> 最多 3 轮工具循环后强制总结；规则触发（关键字启发式）保留为兜底；工具失败转为失败文本回填，
> 不阻断主链路。SSE 中另有 `tool` 事件实时推送每次工具执行。

长时间无增量时服务端发送 `: keepalive` 注释帧保活；前端可用 `AbortController` 主动中断（停止按钮）。

### 引用来源结构（M2 起）

`ChatVO.sources` 与 done 事件的 `sources` 均为对象数组，供前端展示引用与查看片段：

```json
[{"file": "rag.md", "snippet": "向量模型：千问云端 text-embedding-v3…", "score": 0.87}]
```

### 错误码

| code | 含义 | 触发场景 |
|---|---|---|
| 30001 | AI 服务调用超时 | 连接/读取超时（默认 60s） |
| 30002 | AI 服务不可用 | 服务未启动、连接拒绝、DNS 失败 |
| 30003 | 模型错误 | 模型未拉取/不存在、鉴权失败、返回格式异常 |

## 4. 文件 /file（需登录）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /file/upload?agentId | multipart 上传（pdf/docx/txt/md，≤20MB）→ DocumentVO；自动触发 RAG 入库 |
| GET | /file/list?agentId&page&size | 文档分页 |
| DELETE | /file/{id} | 删除（元数据 + 磁盘文件 + Qdrant 向量；向量删除失败则整体失败可重试） |
| POST | /file/{id}/retry | 重试 RAG 入库（PENDING/FAILED） |

> M2 同名覆盖：同名文件重复上传会先清理旧文档（元数据 + 向量）再入库，避免旧分块残留。
> 删除文档时 Qdrant 向量删除失败会返回 40004 并保留记录（保证集合一致，可重试删除）。
> M4 权限：删除/重试仅文档所属 Agent 的创建者可操作（20003）；列表按 Agent 隔离。

错误码：40001 类型不支持、40002 超 20MB、40003 空文件、40004 RAG 失败。

## 5. 工作流 /workflows（需登录，M3）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /workflows | 创建 `{name, description?, nodes[]}`；节点 `{nodeKey, nodeType(llm/tool), params, nextNode}` |
| GET | /workflows?page&size | 我的工作流分页 → PageResult\<WorkflowVO\>（含节点） |
| GET | /workflows/{id} | 详情（含节点） |
| PUT | /workflows/{id} | 更新（节点整体替换，仅创建者） |
| DELETE | /workflows/{id} | 删除（仅创建者，逻辑删除 + 节点级联） |
| POST | /workflows/{id}/run | 触发运行 `{input?}` → WorkflowRunVO（同步返回状态/输出/节点日志） |
| GET | /workflows/{id}/runs?page&size | 运行记录分页 |
| GET | /workflows/runs/{runId} | 运行详情（含节点级日志） |

> 节点类型（轻量限定）：`tool`（`params={"tool": 工具名, "payload": {参数}}`）执行注册表工具；
> `llm`（`params={"prompt": 提示词模板}`）调用模型生成。参数支持 `{var}` 模板 —— var 来自
> 运行输入（对话触发时含 `message`）或前置节点输出（以 nodeKey 引用）。
> 执行语义：线性链（nextNode 指向，NULL=结束），唯一起点且无环；节点失败 → 运行 FAILED
> 并携带节点错误日志（工具失败文本不中断链路）；节点日志含节点/类型/状态/输出/耗时。
> 错误码：20003 非创建者、10003 不存在、10001 参数错误（非法节点类型/空节点/循环等）。

## 5.5 模型 Provider /model/providers（需登录，M4）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /model/providers | Provider 列表（系统内置 + 本人创建，启用优先）→ ProviderVO[] |
| POST | /model/providers | 创建 `{name, providerType(ollama/openai), baseUrl, apiKey?, models[], enabled?}` |
| PUT | /model/providers/{id} | 更新（仅创建者；内置不可改） |
| DELETE | /model/providers/{id} | 删除（仅创建者；内置不可删） |

> M4 多模型配置：`providerType=ollama` 走本地原生 /api/chat（think 可控），
> `openai` 走 OpenAI 兼容 /v1/chat/completions（支持任意兼容服务如 DeepSeek）。
> Agent 通过 `providerId` 绑定；聊天时后端透传 {type, baseUrl, apiKey} 给 AI 服务，
> 未绑定（NULL）回落内置千问云端（API Key 取自 AI 服务环境变量）。内置 Provider（creator_id=0）全局可见不可改删。

## 6. 内部 AI 服务（不经 Nginx 对外，需 X-Internal-Token）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /health | `{status, redis, qdrant}` |
| POST | /agent/chat | `{agentId, message, history[], systemPrompt?, modelName?, temperature?, tools[], userId?, toolConfigs?}` → `{answer, sources[], toolCalls[]}`；`sources` 为 `[{file, snippet, score}]` |
| POST | /agent/chat/stream | 同请求体；SSE 流式（事件协议同第 3 节，done 事件携带完整 answer 供落库） |
| GET | /agent/tools/meta | 工具元数据（名称/描述/参数/配置 Schema；后端 /tools/meta 透传） |
| POST | /agent/workflow/run | `{definition: {nodes[]}, input}` → `{status, output, nodeLogs[], error}`（LangGraph 编译执行） |
| POST | /rag/ingest | `{agentId, fileName, filePath}` → `{status, chunkCount}` |
| POST | /rag/search | `{agentId, query, topK}` → `{chunks[]}` |
| DELETE | /rag/file?agentId&fileName | → `{deletedCount}` |

> M3 记忆：`userId` 透传后 Redis 短期记忆按 `memory:agent:{agentId}:user:{userId}` 隔离
> （最近 10 轮，TTL 24h，对话后写入；与 MySQL 历史去重后注入系统提示词作为跨会话回忆；
> Redis 不可用自动降级）；`toolConfigs` 为 `{tool_name: config}` 智能体工具配置。

AI 服务失败时返回结构化错误体 `{"code", "message"}`（错误码与第 3 节对齐，HTTP 502/504），后端 ai-gateway 据此映射用户侧错误码；流式接口的错误以 SSE `error` 事件下发。

## 7. 健康与文档

| 路径 | 说明 |
|---|---|
| /api/actuator/health | 后端健康检查 |
| /api/swagger-ui | springdoc 交互文档（Bearer 鉴权调试） |
| /ai/health | AI 服务健康检查 |
