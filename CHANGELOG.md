# Changelog

本项目变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本语义参考 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增（M5：用户自定义工具，文档《工具配置自定义开发文档 v3.0》）
- 工具库：`tool_definition` 表 + CRUD/复制/测试接口（`/tool-definitions`），创建者隔离、名称校验（格式/用户级唯一/不与内置重名）
- HTTP 工具执行器：URL/query/headers/body 模板渲染、认证注入（api_key/bearer/basic）、超时与响应体上限、SSRF 防护（内网/保留地址段拒绝 + DNS 二次校验）
- 代码工具 + sandbox 沙箱执行器：受限执行 Python/JavaScript（非 root、RLIMIT 内存/CPU、超时强杀、无外网出站拦截、输出截断、Token 鉴权 + 限流）
- Agent 绑定自定义工具：`agent_tool` 扩展 `tool_source`/`tool_definition_id`，聊天装配 `customTools` 透传 AI 服务请求级动态注册
- 密钥安全：自定义工具密钥字段 AES-GCM 加密入库（`enc:v1:` 前缀）、详情脱敏 `********`、编辑留空不修改（掩码合并）
- 前端：工具库列表/编辑器（HTTP 表单 + 代码编辑 + 参数 Schema 行式编辑 + 测试按钮）、AgentEdit 工具来源选择（内置/自定义）
- 新增测试：AI 侧自定义工具冒烟测试（9 项）、后端 ToolDefinition 集成测试

### 新增（M4 进行中）
- CI/CD：GitHub Actions 三端自动化验证（backend `mvn test` / ai `pytest` / web `npm run build`）+ GHCR 镜像构建
- 数据库迁移自动化：`migrate` 一次性容器 + `schema_migrations` 幂等记录，替代手动 `mysql <` 升级
- 公开/私有可见性：Agent `visibility` 字段（PUBLIC/PRIVATE 默认 PRIVATE），私有仅创建者可见
- 前端代码分割：Element Plus 按需引入 + `manualChunks` 分包，主包 1040KB→9KB
- 开源规范：MIT LICENSE、CONTRIBUTING、CODE_OF_CONDUCT、Issue/PR 模板

## [M3] - 2026-08-03

### 新增
- LLM 工具决策（OpenAI 兼容 tools 参数 + think 并存）+ LangGraph ReAct 多轮循环（上限 3 轮），规则触发保留兜底
- 工具 Schema 化注册表 + `GET /tools/meta`；新增 current_time / web_search 工具
- Memory 接线：`memory:agent:{agentId}:user:{userId}` 按用户隔离（TTL 24h，Redis 不可用降级）
- Workflow v1：定义 CRUD + LangGraph 编译执行 + 节点级日志 + Agent 运行模式（chat/workflow）
- SSE `tool` 事件：工具调用实时展示

## [M2] - 2026-08-03

### 新增
- RAG 知识库：上传 → 解析（pdf/docx/txt/md）→ bge-m3 Embedding → Qdrant 检索 → 来源引用
- 多会话：session 表 + 会话列表/新建/切换/删除
- 文件管理：状态机、重试、删除（含向量清理）

## [M1] - 2026-08-03

### 新增
- SSE 流式打字机输出（AI → 后端 → 前端全链路）
- AI 错误规范化（超时/不可用/模型错误）
- Java 集成测试基础

## [Phase 1] - 2026-08-03

### 新增
- Spring Boot 8 模块后端 + JWT 认证 + Agent CRUD
- Vue 3 登录/注册/Agent 管理
- Docker Compose 一键部署（MySQL/Redis/Qdrant/Ollama/AI/后端/前端/Nginx）
