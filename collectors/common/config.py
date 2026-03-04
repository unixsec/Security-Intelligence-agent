# ================================================================
# 安全情报分析智能体 — 公共配置模块
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import os
from dataclasses import dataclass


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30


@dataclass
class MilvusConfig:
    host: str
    port: int
    collection_name: str = "intel_vectors"
    dim: int = 1536
    dedup_threshold: float = 0.92
    dedup_lookback_days: int = 7


@dataclass
class DifyConfig:
    api_base: str
    api_key: str
    wf_dedup_id: str
    wf_analysis_id: str
    timeout: int = 120


@dataclass
class AppConfig:
    db: DBConfig
    milvus: MilvusConfig
    dify: DifyConfig
    log_level: str = "INFO"
    collector_batch_size: int = 50


def load_config() -> AppConfig:
    """从环境变量（K8s Secrets 注入）加载配置。"""
    db = DBConfig(
        host=os.environ.get("MYSQL_HOST", "mysql-primary.intel-system.svc"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "intel_admin"),
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ.get("MYSQL_DATABASE", "intel_system"),
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
    )

    milvus = MilvusConfig(
        host=os.environ.get("MILVUS_HOST", "milvus-standalone.intel-system.svc"),
        port=int(os.environ.get("MILVUS_PORT", "19530")),
        dedup_threshold=float(os.environ.get("DEDUP_THRESHOLD", "0.92")),
        dedup_lookback_days=int(os.environ.get("DEDUP_LOOKBACK_DAYS", "7")),
    )

    dify = DifyConfig(
        api_base=os.environ.get(
            "DIFY_API_BASE", "http://dify-api.intel-system.svc:5001/v1"
        ),
        api_key=os.environ["DIFY_API_KEY"],
        wf_dedup_id=os.environ.get("DIFY_WF_DEDUP_ID", "wf-3-dedup"),
        wf_analysis_id=os.environ.get("DIFY_WF_ANALYSIS_ID", "wf-2-analysis"),
    )

    return AppConfig(
        db=db,
        milvus=milvus,
        dify=dify,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
