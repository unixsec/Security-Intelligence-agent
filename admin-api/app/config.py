# ================================================================
# 安全情报分析智能体 — 管理 API 配置
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用基础
    app_name: str = "Security Intelligence Agent Admin API"
    app_version: str = "1.0"
    debug: bool = False

    # 数据库
    mysql_host: str = "mysql-primary.intel-system.svc"
    mysql_port: int = 3306
    mysql_user: str = "intel_admin"
    mysql_password: str = ""
    mysql_database: str = "intel_system"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Dify
    dify_api_base: str = "http://dify-api.intel-system.svc:5001/v1"
    dify_api_key: str = ""

    # 安全
    api_secret_key: str = "change-me-in-production"
    cors_origins: list = ["http://localhost:5173", "http://intel-admin.internal.company.com"]

    # 分页默认值
    default_page_size: int = 20
    max_page_size: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
