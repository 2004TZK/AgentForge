"""全局配置：pydantic-settings 读取环境变量 / .env 文件，禁止硬编码。"""
from pathlib import Path

from pydantic_settings import BaseSettings

# .env 固定指向 AI 服务包根目录，避免受启动/测试时工作目录影响
# （例如从仓库根目录运行 pytest 时误加载根目录 .env）
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # ---- 服务 ----
    app_name: str = "agentforge-ai"
    internal_token: str = "dev-internal-token"

    # ---- LLM（OpenAI 兼容，决策 v1.4：千问云端 API，无本地模型） ----
    llm_api_key: str = ""                    # 千问/DashScope 兼容模式 API Key
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_local: bool = False                  # 默认远端模型（False）；自建 Ollama 可置 True 走原生 /api/chat
    llm_model: str = "qwen3.7-plus"
    llm_think: bool = False                  # 仅本地推理模型（如 qwen3.5）使用；远端模型忽略
    llm_timeout_seconds: int = 120           # 云端推理较快，超时收敛到 2 分钟
    sse_ping_interval_seconds: int = 10      # SSE 无事件超过该间隔时发送保活注释帧

    # ---- Embedding（OpenAI 兼容 /embeddings，决策 v1.4：千问 text-embedding-v3） ----
    embedding_base_url: str = ""             # 缺省复用 llm_base_url
    embedding_api_key: str = ""              # 缺省复用 llm_api_key
    embedding_model: str = "text-embedding-v3"  # 未配置走本地哈希 Mock（降级）
    embedding_dim: int = 1024                # text-embedding-v3 可选 768/1024/1536，此处取 1024

    # ---- Qdrant ----
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    rag_top_k: int = 4

    # ---- Redis（短期记忆） ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    memory_rounds: int = 10                   # 最近 N 轮对话
    memory_ttl_hours: int = 24                # TTL 24 小时

    # ---- RAG 切分 ----
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50

    # ---- 共享文件卷 ----
    upload_dir: str = "/data/uploads"

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "extra": "ignore",
    }


settings = Settings()
