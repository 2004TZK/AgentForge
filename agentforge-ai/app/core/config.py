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
    llm_remote_disable_thinking: bool = True  # 远端 qwen3 系列（DashScope）默认产出 reasoning_content，
    # 拖慢首 token 与工具决策；置 True 时对 DashScope 兼容接口传 enable_thinking=false 提速
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
    # 星盘类回答硬上限（字）：绑定 star_chart 工具的智能体完整解读 ≤ 该值，
    # 超出按句子边界截断（提示词约束模型不可靠，服务层兜底保证字数上限）
    llm_answer_max_chars: int = 3000

    # ---- Redis（短期记忆） ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    memory_rounds: int = 10                   # 最近 N 轮对话
    memory_ttl_hours: int = 24                # TTL 24 小时

    # ---- RAG 切分 ----
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50

    # ---- 数据库文件解析（第一期：SQLite + CSV，设计 v0.2 §7/§10） ----
    db_chunk_rows: int = 50            # 结构化切片：每 chunk 合并的行数
    db_batch_rows: int = 1000          # 游标分批读取行数（大表防内存峰值）
    csv_fallback_encoding: str = "gb18030"  # CSV UTF-8 失败后的兜底编码（兼容中文 Excel 导出）
    db_max_rows: int = 100_000         # 单文件总行数上限，超出直接拒绝
    db_max_tables: int = 100           # 单文件表数上限，超出直接拒绝
    # ---- 手动切片参数上限（slicingConfig 校验，防恶意超参） ----
    manual_max_chunk_rows: int = 500   # 手动模式每 chunk 行数上限
    manual_max_chunk_tokens: int = 2000  # 手动模式 chunk token 上限

    # ---- 共享文件卷 ----
    upload_dir: str = "/data/uploads"

    # ---- 自定义工具（工具定义开发文档 v3.0 §6/§7） ----
    # HTTP 工具执行器
    http_tool_timeout_seconds: int = 15        # 单次请求超时（默认 15s）
    http_tool_max_response_bytes: int = 1_048_576  # 响应体大小上限（1MB）
    http_tool_ssrf_enabled: bool = True        # SSRF 防护开关（内网/保留地址段拒绝）
    http_tool_max_chars: int = 4000            # 回填 LLM 的结果文本截断长度
    # 代码工具 + sandbox 沙箱执行器
    sandbox_base_url: str = "http://sandbox:8700"  # 沙箱服务内部地址（compose network_mode: none）
    sandbox_internal_token: str = "dev-sandbox-token"
    script_tool_max_source_chars: int = 51_200  # 代码大小上限（50KB，与后端双重校验）
    script_tool_max_stdout_chars: int = 4000   # stdout 回填截断

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "extra": "ignore",
    }


settings = Settings()
