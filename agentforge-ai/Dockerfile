# AgentForge AI Service 镜像
FROM python:3.12-slim

# 安装构建依赖（pyswisseph 需编译 C 扩展）和系统时区数据
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libc6-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 时区与基础工具
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 历书数据文件随仓库打包（app/tools/data/ephe/*.se1，约 1.8MB）
# 如需更新历书数据，运行：python scripts/download_ephemeris.py

EXPOSE 8000

# 生产建议 4 worker（容器内可调），--reload 仅本地开发使用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
