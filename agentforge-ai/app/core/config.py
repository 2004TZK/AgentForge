"""全局配置：pydantic-settings 读取环境变量 / .env 文件，禁止硬编码。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- 服务 ----
    app_name: str = "agentforge-ai"
    internal_token: str = "dev-internal-token"

    # ---- LLM（OpenAI 兼容） ----
    llm_api_key: str = ""                    # 未配置则进入 Mock 模式
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 60
    sse_ping_interval_seconds: int = 10      # SSE 无事件超过该间隔时发送保活注释帧

    # ---- Embedding（未配置模型时使用本地哈希 Mock 向量） ----
    embedding_model: str = ""
    embedding_dim: int = 384

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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
