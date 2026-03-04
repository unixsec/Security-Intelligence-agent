# ================================================================
# 安全情报分析智能体 — 管理 API Dockerfile
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# ================================================================

FROM python:3.11-slim

LABEL maintainer="alex <unix_sec@163.com>"
LABEL version="1.0"
LABEL description="Security Intelligence Agent - Admin API"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
