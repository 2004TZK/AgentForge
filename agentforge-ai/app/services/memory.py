"""Redis 短期记忆：memory:agent:{agentId}，保存最近 N 轮对话，TTL 24 小时。

Redis 不可用时降级为空记忆（不阻断对话主链路）。
"""
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_redis():
    try:
        import redis as redis_lib
    except ImportError:
        return None
    try:
        client = redis_lib.Redis(host=settings.redis_host, port=settings.redis_port,
                                 socket_connect_timeout=1, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 不可用，记忆功能降级: %s", exc)
        return None


def _key(agent_id: int) -> str:
    return f"memory:agent:{agent_id}"


def get_history(agent_id: int) -> list[dict]:
    """读取最近 N 轮对话，格式 [{role, content}]（Redis 值为 JSON 列表）。"""
    client = _get_redis()
    if client is None:
        return []
    try:
        raw = client.lrange(_key(agent_id), 0, -1)
        return [json.loads(item) for item in raw]
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取记忆失败: %s", exc)
        return []


def append_round(agent_id: int, user_message: str, assistant_message: str) -> None:
    """追加一轮对话并裁剪至最近 N 轮，刷新 TTL。"""
    client = _get_redis()
    if client is None:
        return
    try:
        key = _key(agent_id)
        client.rpush(key, json.dumps({"role": "user", "content": user_message}),
                     json.dumps({"role": "assistant", "content": assistant_message}))
        client.ltrim(key, -settings.memory_rounds * 2, -1)
        client.expire(key, settings.memory_ttl_hours * 3600)
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入记忆失败: %s", exc)


def health() -> bool:
    return _get_redis() is not None
