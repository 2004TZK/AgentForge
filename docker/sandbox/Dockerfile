# ============================================================
# AgentForge sandbox 沙箱执行服务（工具定义开发文档 v3.0 §6）
#   运行：docker compose 服务 sandbox（network_mode: none，无外网）
#   能力：受限执行用户 Python / JavaScript 代码
#     - 子进程降权 nobody（非 root）、RLIMIT 内存/CPU、超时强杀
#     - 输出截断、错误分类、Token 鉴权、限流
#   注意：运行时无外网（network_mode: none），构建期可正常拉依赖
# ============================================================
FROM python:3.12-slim

# nodejs：JavaScript 代码执行运行时；iptables：容器内出站拦截（无外网）
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs iptables \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# FastAPI + uvicorn（构建期安装，运行时无外网）
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY server.py /srv/server.py
COPY entrypoint.sh /srv/entrypoint.sh
RUN chmod +x /srv/entrypoint.sh

# /tmp 供子进程写临时代码文件（nobody 用户可写）
RUN chmod 1777 /tmp

EXPOSE 8700

ENTRYPOINT ["/srv/entrypoint.sh"]
