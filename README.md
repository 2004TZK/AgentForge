# AgentForge

智能体（Agent）快速搭建与对话平台。用户可注册登录、创建配置 Agent（系统提示词/模型/工具）、与 Agent 对话（后续支持 RAG 知识库与工具调用）。

## 技术栈

| 端 | 技术 | 说明 |
|---|---|---|
| agentforge-web | Vue 3 + TypeScript + Vite + Pinia | 前端 SPA |
| agentforge-backend | Spring Boot 3.3 (Java 21) + MyBatis Plus + Spring Security/JWT + Redis | 后端，Maven 多模块 |
| agentforge-ai | Python 3.12 + FastAPI + LangGraph + Qdrant | AI 服务（对话/RAG/工具） |
| 中间件 | MySQL 8 / Redis 7 / Qdrant | Docker Compose 一键启动 |

## 目录结构

```text
AgentForge/
├── agentforge-web/       # 前端
├── agentforge-backend/   # 后端（8 个 Maven 模块）
├── agentforge-ai/        # Python AI Service
├── docs/                 # 架构/数据库/API 文档
├── docker/               # nginx 网关、mysql init SQL
├── docker-compose.yml    # 一键启动（生产/演示形态）
├── docker-compose.dev.yml# 本地开发形态（仅中间件）
└── .env.example          # 环境变量样例
```

## 快速开始

> 前置：Docker + Docker Compose（本机无 Docker 时的开发方式见「本地开发」）。

```bash
# 1. 准备环境变量
cp .env.example .env        # 并填写 .env 中的密码与密钥

# 2. 一键启动全部服务（mysql/redis/qdrant/ai/backend/web/nginx）
docker compose up -d --build

# 3. 访问
#   Web 入口       http://localhost
#   后端 API 文档  http://localhost/api/swagger-ui
#   健康检查       http://localhost/api/actuator/health
```

默认演示账号：`admin` / `admin123`（仅限本地开发，生产部署后请立即改密）。

## 本地开发

```bash
# 1. 仅启动中间件
docker compose -f docker-compose.dev.yml up -d

# 2. 后端（端口 8080，连接 localhost 中间件）
cd agentforge-backend && mvn -pl agentforge-start -am spring-boot:run

# 3. AI 服务（端口 8000，未配置 LLM Key 时自动进入 Mock 模式）
cd agentforge-ai && pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload

# 3.5 本地联调注意：AI 服务默认读取 /data/uploads（Docker 共享卷），
#     Windows/macOS 本地无此目录，需先设置 UPLOAD_DIR 指向后端上传目录：
#     set UPLOAD_DIR=..\agentforge-backend\data\uploads      （PowerShell）
#     export UPLOAD_DIR=../agentforge-backend/data/uploads   （Linux/macOS）
#     后端本地上传目录默认 ./data/uploads（相对 agentforge-backend）

# 3.6 运行 AI 服务测试（仓库根目录下也可直接执行）
cd agentforge-ai && pytest tests -q

# 4. 前端（端口 5173，/api 由 Vite proxy 转发到 8080）
cd agentforge-web && npm install && npm run dev
```

## 文档

- [总体架构](docs/architecture.md)
- [数据库设计](docs/database.md)
- [API 文档](docs/api.md)
- [项目开发规划](docs/项目开发规划.md)
- [用户使用指南](docs/user-guide.md)
- [项目初始化设计方案 v0.2](docs/项目初始化设计方案-v0.2.md)

## 开发规范

- 单文件不超过 500 行；统一 `Result<T>` 响应与异常处理；配置外置，禁止硬编码。
- Commit 约定：`feat` / `fix` / `docs` / `chore` / `refactor` + 简短描述。
