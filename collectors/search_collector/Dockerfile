# ================================================================
# 安全情报分析智能体 — 搜索采集器 Dockerfile
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# ================================================================

FROM python:3.11-slim

LABEL maintainer="alex <unix_sec@163.com>"
LABEL version="1.0"
LABEL description="Security Intelligence Agent - Search Collector"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY search_collector/ ./search_collector/

WORKDIR /app/search_collector

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
