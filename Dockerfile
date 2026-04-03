# AM-HK v3.0 - Dockerfile
# 多阶段构建，优化镜像大小

# ========== 构建阶段 ==========
FROM python:3.12-slim as builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ========== 运行阶段 ==========
FROM python:3.12-slim

# 设置元数据
LABEL maintainer="AM-HK Team"
LABEL version="3.0.0"
LABEL description="AlphaMind HK Trading System"

# 设置工作目录
WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建非root用户
RUN groupadd -r amhk && useradd -r -g amhk amhk

# 复制应用代码
COPY --chown=amhk:amhk . .

# 创建日志目录
RUN mkdir -p /app/logs && chown -R amhk:amhk /app/logs

# 切换到非root用户
USER amhk

# 暴露端口
EXPOSE 8020

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8020/health || exit 1

# 启动命令
CMD ["python", "main.py"]
