# AgentForge 恢复指南（M4 备份配套）

> 备份产物结构：`backups/YYYYMMDD-HHMMSS/` 下 `mysql-*.sql.gz` 与 `qdrant-*.snapshot`。

## 恢复 MySQL

```bash
# 1. 解压
gunzip -k backups/<日期>/mysql-agentforge.sql.gz

# 2. 导入（需先停后端避免写冲突；MySQL 容器须运行）
docker exec -i agentforge-mysql mysql -uroot -p"<root密码>" agentforge < mysql-agentforge.sql
```

## 恢复 Qdrant

```bash
# 1. 复制快照进容器
docker cp backups/<日期>/<快照名>.snapshot agentforge-qdrant:/qdrant/snapshots/

# 2. 恢复（快照名指向集合；删除现有集合会丢失当前数据）
curl -X POST http://localhost:6333/collections/<集合名>/snapshots/recover \
  -H 'Content-Type: application/json' \
  -d '{"location": "file:///qdrant/snapshots/<快照名>.snapshot"}'
```

> 集合名格式：`agent_<agentId>`。Qdrant 快照 API 文档见官方
> [snapshots](https://qdrant.tech/documentation/concepts/snapshots/)。

## 备注

- Ollama 模型目录挂载在宿主机 `D:/ollama`（或 `.env` 的 `OLLAMA_DATA_DIR`），
  备份/迁移只需拷贝该目录。
- Redis 短期记忆（TTL 24h）无需备份。
