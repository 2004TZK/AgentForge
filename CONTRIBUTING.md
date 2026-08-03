# 贡献指南（Contributing）

感谢你考虑为 AgentForge 贡献！请先阅读以下约定，让协作更顺畅。

## 项目结构

| 目录 | 说明 |
|---|---|
| `agentforge-backend` | Spring Boot 多模块后端（Java 21 + Maven + MyBatis Plus） |
| `agentforge-ai` | Python AI 服务（FastAPI + LangGraph + Qdrant + Redis） |
| `agentforge-web` | Vue 3 前端（Vite + TypeScript + Pinia） |
| `docker/` | Docker Compose 编排、MySQL 迁移、Nginx 配置 |
| `docs/` | 开发规划、API 文档 |

## 开发流程

1. **Fork 仓库**并克隆到本地
2. 从 `main` 检出功能分支：`git checkout -b feat/xxx`（`fix/xxx` 修复）
3. 按规范提交，完成后运行全部检查（见下）
4. 提交 Pull Request 到 `main`，CI 全绿后即可合并

## 提交前检查（CI 等价命令）

```bash
# 后端：集成测试（H2 内存库）
cd agentforge-backend && mvn test -pl agentforge-start -am

# AI 服务：单元测试
cd agentforge-ai && pip install -r requirements.txt pytest && pytest -q

# 前端：生产构建
cd agentforge-web && npm ci && npm run build
```

## 提交信息约定

- 前缀：`feat:` 新功能 / `fix:` 修复 / `refactor:` 重构 / `docs:` 文档 / `test:` 测试 / `ci:` CI / `chore:` 杂项
- 中文描述，一句话概括改动，可附要点列表

## 数据库变更

- 所有 schema 变更一律**新增** `docker/mysql/upgrade/YYYYMMDD-xxx.sql`（**不要修改**已发布的迁移文件）
- 脚本必须幂等（列/表存在时自动跳过，参考现有脚本）
- 同步更新 `agentforge-backend/agentforge-start/src/test/resources/sql/schema-h2.sql`（测试用）

## 测试要求

- 新功能必须带测试：后端 MockMvc 集成测试、AI 服务 pytest
- 新增接口同步更新 `docs/api.md`

## 行为准则

请阅读 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。尊重他人、有建设性、对事不对人。
