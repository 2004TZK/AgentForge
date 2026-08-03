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

    # ---- LLM（OpenAI 兼容，决策 v1.2：本地 Ollama qwen2.5:7b，本地模型无需 Key） ----
    llm_api_key: str = ""                    # 本地模型留空；远端模型（如 DeepSeek）需填写
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_timeout_seconds: int = 60
    sse_ping_interval_seconds: int = 10      # SSE 无事件超过该间隔时发送保活注释帧

    # ---- Embedding（OpenAI 兼容 /embeddings，决策 v1.2：本地 bge-m3） ----
    embedding_base_url: str = ""             # 缺省复用 llm_base_url
    embedding_api_key: str = ""              # 本地模型留空
    embedding_model: str = ""                # 如 bge-m3；未配置走本地哈希 Mock（降级）
    embedding_dim: int = 1024                # 与模型维度一致（bge-m3=1024）

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
