# ================================================================
# 安全情报分析智能体 — 管理前端 Dockerfile（多阶段构建）
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# ================================================================

# 构建阶段
FROM node:20-alpine AS builder

LABEL maintainer="alex <unix_sec@163.com>"

WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

# 生产阶段
FROM nginx:1.25-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
