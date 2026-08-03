"""生成 RAG 质量验证测试语料（AgentForge 项目主题，含明确可检索事实）。

用法（在 agentforge-ai 目录下）：
    python scripts/make_test_corpus.py [--out ./corpus]

生成 3 篇 md 文档到输出目录。验证流程：
1. 启动全套服务（docker compose up -d --build），前端上传这些文档到某 Agent
2. 对该 Agent 提问下列问题，检查回答是否引用正确文档、片段是否准确：
   - "后端默认端口是多少？"            → 8080（architecture.md）
   - "JWT 令牌有效期多久？"            → 24 小时（auth.md）
   - "向量维度是多少？"                → 1024（rag.md）
   - "不支持的文件类型上传会怎样？"    → 40001 错误（file.md）
3. 回答应附带来源引用（文件名），点击可查看片段

若检索结果不准确：调小 chunk_size_tokens（如 300）、调大 rag_top_k（如 6），
或确认 EMBEDDING_MODEL 已配置（未配置时哈希 Mock 向量检索质量有限）。
"""
import argparse
from pathlib import Path

CORPUS = {
    "architecture.md": """# AgentForge 系统架构

AgentForge 采用前后端分离与 AI 服务独立的架构，共三端：
- 后端 agentforge-backend：Spring Boot 3 多模块 Maven 项目，默认端口 8080，统一 API 前缀 /api。
- 前端 agentforge-web：Vue 3 + Vite 构建的单页应用，开发环境通过 Vite 代理访问后端。
- AI 服务 agentforge-ai：FastAPI 实现对话、RAG 与工具调用，默认端口 8000，仅内网访问。

边缘网关使用 Nginx，是唯一对外入口：/ 指向前端静态资源，/api/ 转发后端，/ai/ 转发 AI 服务。
所有外部请求经 Nginx 统一收敛，中间件（MySQL、Redis、Qdrant）不直接暴露到公网。

数据库使用 MySQL 8.0，包含用户表、智能体表、文档表、对话记录与会话表。
向量数据库使用 Qdrant，按智能体隔离集合，命名规则为 agent_{智能体ID}。
""",
    "auth.md": """# AgentForge 认证与权限

AgentForge 使用 JWT 无状态认证：用户登录成功后签发令牌，默认有效期 24 小时，
过期后需要重新登录。请求需携带 Authorization: Bearer <token> 请求头。

认证接口包括：
- POST /auth/register 注册，用户名 3-20 位字母数字下划线，密码 6-32 位。
- POST /auth/login 登录，成功后返回 token 与用户信息。
- GET /auth/me 获取当前用户信息。

智能体权限规则：所有登录用户可查看智能体列表与详情，但只有创建者可以修改或删除智能体，
非创建者操作会返回 20003 无权限错误。密码使用 BCrypt 加密存储，数据库不保存明文密码。
""",
    "rag.md": """# AgentForge 知识库（RAG）

AgentForge 的知识库基于检索增强生成（RAG）：上传文档后自动解析、切分、向量化并入库。

- 支持的文档类型：pdf、docx、txt、md，单文件不超过 20MB。
- 向量模型：千问云端 text-embedding-v3，向量维度 1024，多语言检索效果良好。
- 切分策略：默认每块 500 token，相邻块重叠 50 token，可配置调整。
- PDF 解析按页注入页码标记，检索结果可追溯来源页码。

对话时系统先对问题做向量检索（默认取前 4 条），把命中片段注入提示词后生成回答，
回答会附带引用来源。未上传任何文档的智能体（空知识库）自动降级为普通对话。
""",
    "file.md": """# AgentForge 文件上传与错误码

AgentForge 统一错误码约定：0 表示成功，10xxx 参数或业务错误，20xxx 认证授权错误，
30xxx AI 服务错误，40xxx 文件或知识库错误，50xxx 系统内部错误。

文件上传相关错误：
- 40001 不支持的文件类型：仅允许 pdf、docx、txt、md。
- 40002 文件大小超出限制：单文件最大 20MB。
- 40003 文件内容为空：无法解析出任何文本。
- 40004 知识库处理失败：入库流程异常。

同名文件重复上传会覆盖旧版本：旧文档与旧向量被清理，新内容重新入库。
文档删除时元数据、磁盘文件与向量三处一并清理，保证知识库一致。
""",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 RAG 测试语料")
    parser.add_argument("--out", default="./corpus", help="输出目录（默认 ./corpus）")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in CORPUS.items():
        target = out_dir / name
        target.write_text(content, encoding="utf-8")
        print(f"已生成: {target}（{len(content)} 字符）")
    print(f"\n共 {len(CORPUS)} 篇文档。验证流程见脚本头部注释。")


if __name__ == "__main__":
    main()
