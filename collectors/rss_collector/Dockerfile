# ================================================================
# 安全情报分析智能体 — RSS 采集器 Dockerfile
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# ================================================================

FROM python:3.11-slim

LABEL maintainer="alex <unix_sec@163.com>"
LABEL version="1.0"
LABEL description="Security Intelligence Agent - RSS Collector"

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制公共模块和采集器代码
COPY common/ ./common/
COPY rss_collector/ ./rss_collector/

WORKDIR /app/rss_collector

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
