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
| GET | /agent/page?page&size&name | 分页（名称模糊）→ PageResult\<AgentVO\> |
| GET | /agent/{id} | 详情（含 systemPrompt/tools）→ AgentDetailVO |
| POST | /agent | 创建 `{name, description?, systemPrompt, modelName?, temperature?, tools[]?}` |
| PUT | /agent/{id} | 更新（仅创建者） |
| DELETE | /agent/{id} | 删除（仅创建者，逻辑删除） |

错误码：20003 非创建者操作、10003 智能体不存在、10001 参数错误。

## 3. 对话 /chat（需登录）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /chat | 发送消息 `{agentId, message}` → ChatVO `{answer, sources[], toolCalls[]}`（同步） |
| POST | /chat/stream | 发送消息（SSE 流式回答，见下方事件协议） |
| GET | /chat/history?agentId&page&size | 历史分页（倒序）→ PageResult\<ConversationVO\> |

### SSE 流式接口（POST /chat/stream）

请求体与 `/chat` 一致 `{agentId, message}`；响应为 `text/event-stream`（`Cache-Control: no-cache`、`X-Accel-Buffering: no`，Nginx 已关闭缓冲）。事件以空行分隔，`data:` 行为 JSON：

| 事件 type | 字段 | 说明 |
|---|---|---|
| delta | `content` | 回答增量（逐块输出，前端打字机渲染） |
| done | `answer`、`sources[]`、`toolCalls[]` | 回答结束，携带完整数据（后端在此时落库） |
| error | `code`、`message` | 失败（错误码同下表）；流结束但未收到 done/error 视为连接中断 |

长时间无增量时服务端发送 `: keepalive` 注释帧保活；前端可用 `AbortController` 主动中断（停止按钮）。

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
| DELETE | /file/{id} | 删除（元数据 + 磁盘文件 + Qdrant 向量） |
| POST | /file/{id}/retry | 重试 RAG 入库（PENDING/FAILED） |

错误码：40001 类型不支持、40002 超 20MB、40003 空文件、40004 RAG 失败。

## 5. 内部 AI 服务（不经 Nginx 对外，需 X-Internal-Token）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /health | `{status, redis, qdrant}` |
| POST | /agent/chat | `{agentId, message, history[], systemPrompt?, modelName?, temperature?, tools[]}` → `{answer, sources[], toolCalls[]}` |
| POST | /agent/chat/stream | 同请求体；SSE 流式（事件协议同第 3 节，done 事件携带完整 answer 供落库） |
| POST | /rag/ingest | `{agentId, fileName, filePath}` → `{status, chunkCount}` |
| POST | /rag/search | `{agentId, query, topK}` → `{chunks[]}` |
| DELETE | /rag/file?agentId&fileName | → `{deletedCount}` |

AI 服务失败时返回结构化错误体 `{"code", "message"}`（错误码与第 3 节对齐，HTTP 502/504），后端 ai-gateway 据此映射用户侧错误码；流式接口的错误以 SSE `error` 事件下发。

## 6. 健康与文档

| 路径 | 说明 |
|---|---|
| /api/actuator/health | 后端健康检查 |
| /api/swagger-ui | springdoc 交互文档（Bearer 鉴权调试） |
| /ai/health | AI 服务健康检查 |
