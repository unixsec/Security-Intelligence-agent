# ================================================================
# 安全情报分析智能体 — 情报源服务层
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import csv
import io
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.database import engine
from app.models.schemas import IntelSourceCreate, IntelSourceUpdate


class SourceService:
    """情报源 CRUD 服务。"""

    def __init__(self, db: Session):
        self.db = db

    def list_sources(
        self,
        page: int,
        page_size: int,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Tuple[int, List]:
        conditions = ["1=1"]
        params = {}

        if source_type:
            conditions.append("source_type = :source_type")
            params["source_type"] = source_type
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if category:
            conditions.append("category = :category")
            params["category"] = category

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size

        with engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM intel_sources WHERE {where}"), params
            ).scalar()
            rows = conn.execute(
                text(
                    f"SELECT * FROM intel_sources WHERE {where} "
                    f"ORDER BY priority ASC, created_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": page_size, "offset": offset},
            ).fetchall()

        return total or 0, [dict(r._mapping) for r in rows]

    def create_source(self, payload: IntelSourceCreate) -> dict:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "INSERT INTO intel_sources "
                    "(source_type, name, url, category, language, priority, notes, created_by) "
                    "VALUES (:source_type, :name, :url, :category, :language, :priority, :notes, 'admin-api')"
                ),
                {
                    "source_type": payload.source_type,
                    "name": payload.name,
                    "url": payload.url,
                    "category": payload.category,
                    "language": payload.language,
                    "priority": payload.priority,
                    "notes": payload.notes,
                },
            )
            new_id = result.lastrowid

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM intel_sources WHERE id = :id"), {"id": new_id}
            ).fetchone()
        return dict(row._mapping)

    def update_source(self, source_id: int, payload: IntelSourceUpdate) -> Optional[dict]:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM intel_sources WHERE id = :id"), {"id": source_id}
            ).fetchone()
        if not row:
            return None

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM intel_sources WHERE id = :id"), {"id": source_id}
                ).fetchone()
            return dict(row._mapping)

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE intel_sources SET {set_clause} WHERE id = :id"),
                {**updates, "id": source_id},
            )

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM intel_sources WHERE id = :id"), {"id": source_id}
            ).fetchone()
        return dict(row._mapping)

    def delete_source(self, source_id: int) -> bool:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM intel_sources WHERE id = :id"), {"id": source_id}
            )
        return result.rowcount > 0

    def get_source_health(self, source_id: int) -> Optional[dict]:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM intel_sources WHERE id = :id"), {"id": source_id}
            ).fetchone()
        if not row:
            return None

        data = dict(row._mapping)
        # 最近 24h 采集量
        with engine.connect() as conn:
            cnt = conn.execute(
                text(
                    "SELECT COUNT(*) FROM raw_intel "
                    "WHERE source_id = :id AND collected_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
                ),
                {"id": source_id},
            ).scalar()

        data["recent_24h_intel_count"] = cnt or 0
        return data

    def import_from_csv(self, csv_content: str) -> int:
        reader = csv.DictReader(io.StringIO(csv_content))
        count = 0
        for row in reader:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "INSERT IGNORE INTO intel_sources "
                            "(source_type, name, url, category, language, priority, notes, created_by) "
                            "VALUES (:source_type, :name, :url, :category, :language, :priority, :notes, 'csv-import')"
                        ),
                        {
                            "source_type": row.get("source_type", "rss"),
                            "name": row.get("name", ""),
                            "url": row.get("url", ""),
                            "category": row.get("category", "general_security"),
                            "language": row.get("language", "zh"),
                            "priority": row.get("priority", "medium"),
                            "notes": row.get("notes", ""),
                        },
                    )
                count += 1
            except Exception:
                continue
        return count

    def export_to_csv(self) -> str:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT source_type, name, url, category, language, priority, status, notes "
                     "FROM intel_sources ORDER BY id")
            ).fetchall()

        output = io.StringIO()
        fieldnames = ["source_type", "name", "url", "category", "language", "priority", "status", "notes"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row._mapping))
        return output.getvalue()
