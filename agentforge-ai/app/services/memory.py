"""Redis 短期记忆：memory:agent:{agentId}:user:{userId}，保存最近 N 轮对话，TTL 24 小时。

M3 起按用户隔离（后端 chat 请求透传 userId），避免多用户共用同一 Agent 时串上下文；
userId 为空（旧调用方）时退化为按 Agent 隔离的兼容 key。
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


def _key(agent_id: int, user_id: int | None = None) -> str:
    if user_id is not None:
        return f"memory:agent:{agent_id}:user:{user_id}"
    return f"memory:agent:{agent_id}"


def get_history(agent_id: int, user_id: int | None = None) -> list[dict]:
    """读取最近 N 轮对话，格式 [{role, content}]（Redis 值为 JSON 列表）。"""
    client = _get_redis()
    if client is None:
        return []
    try:
        raw = client.lrange(_key(agent_id, user_id), 0, -1)
        return [json.loads(item) for item in raw]
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取记忆失败: %s", exc)
        return []


def append_round(agent_id: int, user_id: int | None, user_message: str,
                 assistant_message: str) -> None:
    """追加一轮对话并裁剪至最近 N 轮，刷新 TTL。"""
    client = _get_redis()
    if client is None:
        return
    try:
        key = _key(agent_id, user_id)
        client.rpush(key, json.dumps({"role": "user", "content": user_message}),
                     json.dumps({"role": "assistant", "content": assistant_message}))
        client.ltrim(key, -settings.memory_rounds * 2, -1)
        client.expire(key, settings.memory_ttl_hours * 3600)
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入记忆失败: %s", exc)


def clear_history(agent_id: int, user_id: int | None = None) -> None:
    """清空指定（Agent, 用户）的记忆（测试/管理用）。"""
    client = _get_redis()
    if client is None:
        return
    try:
        client.delete(_key(agent_id, user_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("清空记忆失败: %s", exc)


def health() -> bool:
    return _get_redis() is not None
