# ================================================================
# 安全情报分析智能体 — 数据库连接池模块
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import DBConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """MySQL 连接池管理器，基于 SQLAlchemy。"""

    def __init__(self, config: DBConfig):
        dsn = (
            f"mysql+pymysql://{config.user}:{config.password}"
            f"@{config.host}:{config.port}/{config.database}"
            f"?charset=utf8mb4"
        )
        self._engine = create_engine(
            dsn,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_pre_ping=True,
            echo=False,
        )
        self._Session = sessionmaker(bind=self._engine)
        logger.info("Database connection pool initialized: %s:%d/%s",
                    config.host, config.port, config.database)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """提供一个事务性 Session 上下文管理器。"""
        sess = self._Session()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def health_check(self) -> bool:
        """检查数据库连接是否正常。"""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return False

    def close(self):
        self._engine.dispose()
