#!/bin/sh
# ============================================================
# AgentForge 数据库迁移入口（docker compose 的 migrate 一次性服务）
#   按文件名顺序应用 docker/mysql/upgrade/*.sql，已应用的记录在
#   schema_migrations 表（幂等：重复启动自动跳过）。
# 首次部署：docker/mysql/init 由 MySQL 容器自动执行（建库建表）；
# 升级部署：本脚本自动补齐 upgrade/ 下所有未应用的迁移。
# ============================================================
set -e

MYSQL_HOST=${MYSQL_HOST:-mysql}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_USER=${MYSQL_USER:-agentforge}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-change-me-app}
MYSQL_DATABASE=${MYSQL_DATABASE:-agentforge}
# 必须显式 utf8mb4：缺省时 mysql CLI 走 latin1 连接，
# UTF-8 迁移 SQL 中的中文会被双重编码入库（2026-08-05 实测踩坑）
MYSQL_CHARSET=${MYSQL_CHARSET:-utf8mb4}

# 等待 MySQL 就绪（最多 60 次 × 2s）
i=0
until mysql --default-character-set="${MYSQL_CHARSET}" \
      -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" \
      -e "SELECT 1" "${MYSQL_DATABASE}" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "${i}" -ge 60 ]; then
    echo "ERROR: MySQL 未在 120s 内就绪，迁移中止" >&2
    exit 1
  fi
  echo "waiting for mysql... (${i})"
  sleep 2
done

# 迁移记录表（幂等）
mysql --default-character-set="${MYSQL_CHARSET}" \
  -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" "${MYSQL_DATABASE}" <<'SQL'
CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `version`    VARCHAR(100) NOT NULL COMMENT '迁移文件名（upgrade/*.sql）',
  `applied_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '应用时间',
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库迁移记录';
SQL

for f in /upgrade/*.sql; do
  [ -e "$f" ] || continue
  version=$(basename "$f")
  applied=$(mysql --default-character-set="${MYSQL_CHARSET}" \
    -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" \
    -N -e "SELECT COUNT(*) FROM schema_migrations WHERE version='${version}'" "${MYSQL_DATABASE}")
  if [ "${applied}" -eq 0 ]; then
    echo "== applying ${version} =="
    mysql --default-character-set="${MYSQL_CHARSET}" \
      -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" "${MYSQL_DATABASE}" < "$f"
    mysql --default-character-set="${MYSQL_CHARSET}" \
      -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" \
      -e "INSERT INTO schema_migrations (version) VALUES ('${version}')" "${MYSQL_DATABASE}"
    echo "== ${version} applied =="
  else
    echo "== ${version} already applied, skip =="
  fi
done

echo "migrations done"
