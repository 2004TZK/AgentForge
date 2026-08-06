#!/bin/sh
# ============================================================
# sandbox 入口：限制容器出站网络（"无外网"语义）
#   仅放行已建立连接的回复流量（AI 服务请求的响应），
#   拒绝所有主动新连接（用户代码无法访问外网/内网其他服务）。
# 需要 NET_ADMIN 能力（compose 已配置 cap_add）。
# ============================================================
set -e

# 放行已建立连接（响应 AI 服务请求）
iptables -A OUTPUT -o eth0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
# 拒绝其余 eth0 出站（新连接：外网 / 容器网络内其他服务）
iptables -A OUTPUT -o eth0 -j REJECT

exec uvicorn server:app --host 0.0.0.0 --port 8700
