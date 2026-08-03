#!/bin/sh
# ============================================================
# AgentForge 备份脚本（M4）：MySQL 全量 + Qdrant 快照
# 用法：./scripts/backup.sh [备份目录]（默认 ./backups）
# 产物：backups/YYYYMMDD-HHMMSS/ 下 mysql-*.sql.gz 与 qdrant-*.snapshot
# 恢复：见 scripts/restore.md
# ============================================================
set -e

BACKUP_DIR=${1:-./backups}
STAMP=$(date +%Y%m%d-%H%M%S)
TARGET="${BACKUP_DIR}/${STAMP}"
mkdir -p "${TARGET}"

# 读取 .env 中的 MySQL 密码（未配置时用默认值）
ENV_FILE=${ENV_FILE:-.env}
MYSQL_PASSWORD=$(grep -E '^MYSQL_ROOT_PASSWORD=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
MYSQL_PASSWORD=${MYSQL_PASSWORD:-change-me-root}
MYSQL_DATABASE=$(grep -E '^MYSQL_DATABASE=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
MYSQL_DATABASE=${MYSQL_DATABASE:-agentforge}

echo "== [1/2] MySQL dump =="
docker exec agentforge-mysql sh -c "mysqldump -uroot -p\"\${MYSQL_ROOT_PASSWORD}\" --single-transaction ${MYSQL_DATABASE} | gzip" \
  > "${TARGET}/mysql-${MYSQL_DATABASE}.sql.gz"
echo "  → ${TARGET}/mysql-${MYSQL_DATABASE}.sql.gz"

echo "== [2/2] Qdrant snapshot =="
# Qdrant 官方快照 API（一致性保证，非直接卷拷贝）
SNAPSHOT_RESP=$(curl -s -X POST "http://localhost:${QDRANT_PORT:-6333}/snapshots")
SNAPSHOT_NAME=$(echo "${SNAPSHOT_RESP}" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')
if [ -n "${SNAPSHOT_NAME}" ]; then
  docker cp "agentforge-qdrant:/qdrant/snapshots/${SNAPSHOT_NAME}" "${TARGET}/"
  echo "  → ${TARGET}/${SNAPSHOT_NAME}"
else
  echo "  WARN: Qdrant snapshot 创建失败，响应: ${SNAPSHOT_RESP}"
fi

echo "== done: ${TARGET} =="
du -sh "${TARGET}"

# 保留最近 7 天，清理更早的备份
find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
