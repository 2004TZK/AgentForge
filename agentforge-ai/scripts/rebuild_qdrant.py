"""Qdrant 集合重建脚本：删除全部（或指定）agent_* 集合。

用途：EMBEDDING_DIM 变更（如 bge-m3 1024 维 vs nomic-embed-text 768 维）后，
旧集合维度与配置不符会导致入库报错，需删除后由下一次入库自动重建。

用法（在 agentforge-ai 目录下）：
    python scripts/rebuild_qdrant.py                # 删除全部 agent_* 集合
    python scripts/rebuild_qdrant.py --agent 1      # 仅删除 agent_1
    python scripts/rebuild_qdrant.py --host qdrant  # 容器内联调指定主机

注意：删除后集合内全部向量丢失，需重新上传文档入库。
"""
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="重建 Qdrant 集合（维度变更后运行）")
    parser.add_argument("--agent", type=int, default=None, help="仅重建指定 agent 的集合")
    parser.add_argument("--host", default=None, help="Qdrant 主机（缺省读配置）")
    parser.add_argument("--port", type=int, default=None, help="Qdrant 端口（缺省读配置）")
    args = parser.parse_args()

    from app.core.config import settings  # 与 AI 服务共用配置（agentforge-ai 目录下运行）
    from qdrant_client import QdrantClient

    host = args.host or settings.qdrant_host
    port = args.port or settings.qdrant_port
    client = QdrantClient(host=host, port=port)
    collections = [c.name for c in client.get_collections().collections
                   if c.name.startswith("agent_")]
    if args.agent is not None:
        collections = [c for c in collections if c == f"agent_{args.agent}"]
    if not collections:
        logger.info("没有需要重建的集合")
        return 0
    for name in collections:
        client.delete_collection(name)
        logger.info("已删除集合: %s", name)
    logger.info("重建完成：下次文档入库将按 EMBEDDING_DIM=%s 自动创建集合",
                settings.embedding_dim)
    return 0


if __name__ == "__main__":
    sys.exit(main())
