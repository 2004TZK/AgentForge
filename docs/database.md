# AgentForge 数据库设计

> 与 `docker/mysql/init/01-schema.sql` 同步维护。Phase 2 起以 Flyway 迁移版本管理。

## 1. 约定

- 数据库 `agentforge`，utf8mb4 / utf8mb4_0900_ai_ci，InnoDB。
- 全部业务表含 `deleted` 逻辑删除（0-否 1-是），配合 MyBatis Plus 逻辑删除，不物理删除业务数据。
- 时间字段统一 DATETIME：`created_time` 默认当前时间，`updated_time` 自动更新。
- 外键保留保证完整性；查询走索引（idx_*）。

## 2. 表清单

| 表 | 说明 |
|---|---|
| user | 用户（唯一：username、email） |
| agent | 智能体（创建者外键 user.id） |
| agent_tool | 工具配置（唯一：(agent_id, tool_name)，JSON 列 tool_config） |
| document | 文档元数据（文件内容不落库：原始文件在共享卷、向量在 Qdrant） |
| conversation | 对话记录（一问一答一行；Phase 3 演进多会话双表） |

## 3. 字段速览

### user
id / username(50, uk) / email(100, uk) / password_hash(BCrypt) / avatar / deleted / created_time / updated_time

### agent
id / name(100) / description(500) / system_prompt(TEXT) / model_name(50, 默认 deepseek-chat) / temperature(DECIMAL(3,2), 默认 0.70) / creator_id(uk 索引 + 外键) / deleted / created_time / updated_time

### agent_tool
id / agent_id(外键) / tool_name(100) / tool_config(JSON) / enabled(默认 1) / deleted / created_time / updated_time

### document
id / agent_id(idx) / file_name(255) / file_path(500, 相对路径 agentId/uuid.ext) / file_type(pdf|docx|txt|md) / status(PENDING|PROCESSING|READY|FAILED, idx) / deleted / created_time / updated_time

### conversation
id / agent_id / user_id / user_message(TEXT) / assistant_message(TEXT) / deleted / created_time / updated_time
索引：idx_agent_user_time(agent_id, user_id, created_time)

## 4. 存储边界

| 数据 | 存储 | 读写方 |
|---|---|---|
| 用户/Agent/对话/文档元数据 | MySQL | 后端 |
| 会话缓存 `session:user:{id}`、Agent 配置缓存 `cache:agent:{id}` | Redis | 后端 |
| 短期记忆 `memory:agent:{agentId}`（最近 10 轮，TTL 24h） | Redis | AI 服务 |
| 向量 + payload（agentId/file/page/content） | Qdrant，collection `agent_{agentId}` | AI 服务 |
| 原始文件 | 共享卷 `/data/uploads/{agentId}/{uuid}.ext` | 后端写、AI 读 |
