# ================================================================
# 安全情报分析智能体 — 情报服务层
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.database import engine
from sqlalchemy import text


class IntelService:
    """情报数据查询服务。"""

    def __init__(self, db: Session):
        self.db = db

    def list_raw_intel(
        self,
        page: int,
        page_size: int,
        status: Optional[str] = None,
        source_name: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Tuple[int, List]:
        conditions = ["1=1"]
        params = {}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if source_name:
            conditions.append("source_name LIKE :source_name")
            params["source_name"] = f"%{source_name}%"
        if date_from:
            conditions.append("DATE(collected_at) >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("DATE(collected_at) <= :date_to")
            params["date_to"] = date_to

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size

        with engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM raw_intel WHERE {where}"), params
            ).scalar()
            rows = conn.execute(
                text(
                    f"SELECT id, source_name, source_url, title, summary, language, "
                    f"collected_at, published_at, status FROM raw_intel "
                    f"WHERE {where} ORDER BY collected_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": page_size, "offset": offset},
            ).fetchall()

        return total or 0, [dict(r._mapping) for r in rows]

    def list_scored_intel(
        self,
        page: int,
        page_size: int,
        p_level: Optional[str] = None,
        intel_type: Optional[str] = None,
        severity: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        min_score: Optional[float] = None,
    ) -> Tuple[int, List]:
        conditions = ["1=1"]
        params = {}

        if p_level:
            conditions.append("p_level = :p_level")
            params["p_level"] = p_level
        if intel_type:
            conditions.append("intel_type = :intel_type")
            params["intel_type"] = intel_type
        if severity:
            conditions.append("severity = :severity")
            params["severity"] = severity
        if date_from:
            conditions.append("DATE(scored_at) >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("DATE(scored_at) <= :date_to")
            params["date_to"] = date_to
        if min_score is not None:
            conditions.append("total_score >= :min_score")
            params["min_score"] = min_score

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size

        with engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM scored_intel WHERE {where}"), params
            ).scalar()
            rows = conn.execute(
                text(
                    f"SELECT * FROM scored_intel WHERE {where} "
                    f"ORDER BY total_score DESC LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": page_size, "offset": offset},
            ).fetchall()

        return total or 0, [dict(r._mapping) for r in rows]

    def get_scored_intel(self, intel_id: int) -> Optional[dict]:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM scored_intel WHERE id = :id"), {"id": intel_id}
            ).fetchone()
        return dict(row._mapping) if row else None

    def list_event_tracks(
        self,
        page: int,
        page_size: int,
        status: Optional[str] = None,
    ) -> Tuple[int, List]:
        conditions = ["1=1"]
        params = {}
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size

        with engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM event_tracks WHERE {where}"), params
            ).scalar()
            rows = conn.execute(
                text(
                    f"SELECT * FROM event_tracks WHERE {where} "
                    f"ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": page_size, "offset": offset},
            ).fetchall()

        return total or 0, [dict(r._mapping) for r in rows]
