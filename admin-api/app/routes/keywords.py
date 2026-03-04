# ================================================================
# 安全情报分析智能体 — 搜索关键词管理 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.database import engine, get_db
from app.models.schemas import (
    KeywordCreate, KeywordResponse, KeywordUpdate, PagedResponse, SuccessResponse,
)

router = APIRouter(prefix="/keywords", tags=["关键词管理"])


@router.get("", response_model=PagedResponse)
def list_keywords(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    conditions = ["1=1"]
    params = {}
    if category:
        conditions.append("category = :category")
        params["category"] = category
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM search_keywords WHERE {where}"), params
        ).scalar()
        rows = conn.execute(
            text(
                f"SELECT * FROM search_keywords WHERE {where} "
                f"ORDER BY category, keyword LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

    return PagedResponse(
        total=total or 0, page=page, page_size=page_size,
        items=[dict(r._mapping) for r in rows],
    )


@router.post("", status_code=201)
def create_keyword(payload: KeywordCreate, db: Session = Depends(get_db)):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO search_keywords (keyword, category, language, daily_quota) "
                "VALUES (:keyword, :category, :language, :daily_quota)"
            ),
            payload.model_dump(),
        )
        new_id = result.lastrowid

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM search_keywords WHERE id = :id"), {"id": new_id}
        ).fetchone()
    return dict(row._mapping)


@router.put("/{keyword_id}")
def update_keyword(
    keyword_id: int, payload: KeywordUpdate, db: Session = Depends(get_db)
):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="无可更新字段")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    with engine.begin() as conn:
        result = conn.execute(
            text(f"UPDATE search_keywords SET {set_clause} WHERE id = :id"),
            {**updates, "id": keyword_id},
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="关键词不存在")

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM search_keywords WHERE id = :id"), {"id": keyword_id}
        ).fetchone()
    return dict(row._mapping)


@router.delete("/{keyword_id}", response_model=SuccessResponse)
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM search_keywords WHERE id = :id"), {"id": keyword_id}
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="关键词不存在")
    return SuccessResponse(message="删除成功")


@router.post("/import", response_model=SuccessResponse)
async def import_keywords(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    count = 0
    for row in reader:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT IGNORE INTO search_keywords "
                        "(keyword, category, language, daily_quota) "
                        "VALUES (:keyword, :category, :language, :daily_quota)"
                    ),
                    {
                        "keyword": row.get("keyword", ""),
                        "category": row.get("category", "general_security"),
                        "language": row.get("language", "zh"),
                        "daily_quota": int(row.get("daily_quota", 10)),
                    },
                )
            count += 1
        except Exception:
            continue
    return SuccessResponse(message=f"成功导入 {count} 条关键词")


@router.get("/export")
def export_keywords(db: Session = Depends(get_db)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT keyword, category, language, status, daily_quota FROM search_keywords ORDER BY id")
        ).fetchall()

    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=["keyword", "category", "language", "status", "daily_quota"]
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row._mapping))

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=keywords_{datetime.now().strftime('%Y%m%d')}.csv"
            )
        },
    )
