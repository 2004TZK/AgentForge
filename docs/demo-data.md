# AgentForge 演示数据与操作指南

> 版本：2026-08-03（M4 收尾）
> 本文说明内置演示数据的内容，以及一套**从登录到完整功能验证**的可操作流程。

---

## 1. 演示数据概览

| 数据 | 内容 | 说明 |
|---|---|---|
| 账号 | `demo` / `demo123` | 演示用户，已登录态包含全部资源 |
| Agent A | **Java 专家**（id=1） | 对话模式，启用 calculator + github 工具 |
| Agent B | **知识库助手**（id=2） | 对话模式，绑定 Spring 知识库（`spring-notes.md`，已入库） |
| Agent C | **GitHub 分析官**（id=3） | 工作流模式，绑定"GitHub 项目分析"工作流 |
| 工作流 | **GitHub 项目分析**（id=1） | 3 节点：llm 提取仓库 → tool 查询 GitHub → llm 生成报告 |
| 会话 | 工具演示 / 知识库问答 / 工作流演示 | 三个 Agent 各一个，内含历史对话 |
| 知识库 | `spring-notes.md` | Spring Bean 生命周期 / 自动配置 / 依赖注入，向量存于 Qdrant |

---

## 2. 完整操作流程（从登录到验证）

### 步骤 1：启动并登录

```bash
docker compose up -d --build
```

打开 http://localhost，使用 **demo / demo123** 登录。

### 步骤 2：验证工具调用（Agent A「Java 专家」）

1. 进入"聊天" → 左侧选择 **Java 专家**
2. 会话"工具演示"中发送（或新建会话再发）：

```text
(128+64)/8
```

3. 预期结果：回答 **24**，且消息下方出现工具调用记录
   `calculator({"expression": "(128+64)/8"}) → 24.0`

> 说明：纯算式消息可被 LLM 自主决策或规则兜底稳定触发计算器。

### 步骤 3：验证知识库问答（Agent B「知识库助手」）

1. 聊天页选择 **知识库助手**
2. 在"知识库问答"会话中发送：

```text
Spring Bean 的生命周期是怎样的？
```

3. 预期结果：回答列出 Bean 生命周期阶段，并显示来源引用 **spring-notes.md**（可点击查看片段）

### 步骤 4：验证工作流（Agent C「GitHub 分析官」）

1. 聊天页选择 **GitHub 分析官**
2. 在"工作流演示"会话中发送：

```text
分析一下 github.com/spring-projects/spring-boot
```

3. 预期结果：回答为一份"GitHub 项目分析报告"（项目名 / Star 数 / 语言 / 简介 / 点评）
4. 也可到"工作流"页 → 打开 **GitHub 项目分析** → "运行记录"查看节点级日志（提取仓库 → 查询 GitHub → 生成报告）

> ⚠️ GitHub API 匿名限流 60 次/小时，若返回"工具调用失败"或报告含"[缺失]"，
> 按第 4 节配置 GitHub Token 后重试即可。

### 步骤 5：其他可操作功能

- **多会话**：任一 Agent 下点"＋新建"创建独立会话，历史互不混淆
- **文件管理**：文件页选中 Agent B，可查看/重试/删除 `spring-notes.md`（删除会同时移除向量）
- **智能体配置**：编辑 Agent A 可查看工具 Schema 表单（calculator / github 的配置项）
- **模型管理**：顶部"模型"页可查看内置千问云端 Provider，或新增其他 OpenAI 兼容云端 Provider
- **Agent 可见性**：Agent 详情/编辑中的 PUBLIC / PRIVATE 决定他人是否可见

---

## 3. 数据重建方法

数据可通过种子脚本一键重建（幂等，可重复执行）：

```bash
# 1.（可选）清空业务数据：user/agent/document/conversation/session/workflow 及 Qdrant 向量、Redis 记忆
#    手动清库后执行下面脚本即可

# 2. 重建演示数据（依赖 httpx，可直接用 agentforge-ai/.venv）
agentforge-ai\.venv\Scripts\python.exe scripts\seed-demo-data.py
```

脚本会依次：注册/登录 demo → 创建 3 个 Agent → 上传 Spring 知识库并等待入库 →
创建工作流并绑定 Agent C → 创建 3 个会话 → 执行 3 次真实对话验证（工具 / 知识库 / 工作流）。

---

## 4. GitHub Token 配置（可选，推荐演示前配置）

GitHub 未认证 API 限流 60 次/小时（共享 IP 可能已超限），配置 Token 后提升至 5000 次/小时。

**方式一（按智能体配置，推荐）**：
1. GitHub → Settings → Developer settings → Personal access tokens 生成 token（勾选 `public_repo` 只读即可）
2. 编辑 **Java 专家** 或 **GitHub 分析官** → 工具配置 → github → api_key 填入 token → 保存

**方式二（全局环境变量）**：
1. 在 `.env` 中填写：`GITHUB_TOKEN=ghp_xxx`
2. 重启 AI 服务：`docker compose up -d --build ai`

---

## 5. 常见问题

**Q：工具调用记录有时显示失败？**
A：0.8B 小模型决策存在随机性。纯算式消息（如 `(128+64)/8`）已通过规则兜底保证触发；
若 LLM 传入了 `÷`/`×` 等符号，计算器已支持 Unicode 符号容错（2026-08-03 修复）。

**Q：工作流报告显示"Star 数: 0 或未知"？**
A：github 工具调用被 GitHub 限流（403）。配置第 4 节的 Token 后重发消息即可。

**Q：如何彻底清空演示数据？**
A：清空 MySQL 业务表（user/agent/document/conversation/session/workflow 等）、
Qdrant 集合、Redis `memory:*` 键，再重新执行种子脚本即可得到一份干净一致的数据。
