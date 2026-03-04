# ================================================================
# 安全情报分析智能体 — 网页采集器 Dockerfile
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# ================================================================

FROM python:3.11-slim

LABEL maintainer="alex <unix_sec@163.com>"
LABEL version="1.0"
LABEL description="Security Intelligence Agent - Web Collector"

# 安装 Playwright 系统依赖
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates libglib2.0-0 libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 \
    libexpat1 libxcb1 libxkbcommon0 libx11-6 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY common/ ./common/
COPY web_collector/ ./web_collector/

WORKDIR /app/web_collector

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
