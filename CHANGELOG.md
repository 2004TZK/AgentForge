# Changelog

本项目变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本语义参考 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
