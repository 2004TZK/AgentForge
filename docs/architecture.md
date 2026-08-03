# AgentForge 总体架构

> 与代码同步维护；Phase 1 现状记录，后续演进按设计文档 v0.2 执行。

## 1. 架构总览

```text
浏览器
  │ HTTPS /api/*（Bearer JWT）
  ▼
Nginx（边缘网关，唯一对外入口）
  ├── /        → web（SPA 静态资源，容器内 nginx）
  ├── /api/*   → backend:8080（后端 context-path=/api，原样透传）
  └── /ai/*    → ai:8000（内网，X-Internal-Token）

backend（Spring Boot 3.3 / Java 21，Maven 多模块）
  ├── MySQL（业务数据：用户/Agent/对话/文档元数据）
  ├── Redis（会话缓存 session:user:{id}）
  └── ai（HTTP，X-Internal-Token，连接 5s / 读取 60s）

ai（FastAPI / Python 3.12）
  ├── Redis（短期记忆 memory:agent:{agentId}，TTL 24h）
  ├── Qdrant（向量，collection 按智能体隔离 agent_{agentId}）
  └── LLM（HTTP，OpenAI 兼容：千问云端 Qwen / DeepSeek 等；未配置 Key 走 Mock）
```

## 2. 后端模块

| 模块 | 职责 |
|---|---|
| agentforge-common | Result/PageResult/错误码/业务异常/常量 |
| agentforge-framework | Security+JWT、Redis、全局异常、CORS、MyBatis Plus 配置 |
| agentforge-system | 注册/登录/JWT 签发/会话缓存 |
| agentforge-module-agent | Agent CRUD + 工具配置 |
| agentforge-module-conversation | 聊天保存/历史查询，经 ai-gateway 调 AI |
| agentforge-module-file | 上传落盘、document 状态机、RAG 编排 |
| agentforge-module-ai-gateway | AI HTTP 客户端（X-Internal-Token、超时映射） |
| agentforge-start | 启动入口 + 全局配置 |

依赖方向：业务模块 → framework → common（禁止反向/循环依赖）。

## 3. 关键约定

- 统一响应 `Result<T> {code, message, data}`，分页 `PageResult<T> {list, total, page, size}`。
- 错误码分段：10xxx 参数/业务、20xxx 认证/授权、30xxx AI、40xxx 文件/RAG、50xxx 系统。
- 逻辑删除：所有业务表 `deleted` 字段，MyBatis Plus 全局配置。
- 配置外置：数据库/Redis/Qdrant/AI/JWT 全部环境变量注入，禁止硬编码。
- 安全边界：外部流量仅经 Nginx → 后端（JWT）；AI 服务不暴露宿主机端口；内部服务用 `INTERNAL_TOKEN`。

## 4. Phase 演进路线

| Phase | 内容 |
|---|---|
| Phase 1（当前） | 用户/Agent 全链路、对话（Mock/真实 LLM）、文件上传 + RAG 入库、单机 compose |
| Phase 2 | 对话双表/多会话、Flyway 迁移基线、Mem0 型长期记忆、Mock 完善 |
| Phase 3 | SSE 流式对话（/chat/stream）、多会话前端、Embedding 配置化 |
| Phase 4 | LangGraph 完整 Agent 循环（planner → 工具分支 → LLM）、工具调用前端化 |
