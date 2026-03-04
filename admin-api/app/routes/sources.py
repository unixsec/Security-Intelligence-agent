# ================================================================
# 安全情报分析智能体 — 情报源管理 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    IntelSourceCreate, IntelSourceResponse, IntelSourceUpdate,
    PagedResponse, SuccessResponse,
)
from app.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["情报源管理"])


@router.get("", response_model=PagedResponse)
def list_sources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取情报源列表（支持分页和筛选）。"""
    svc = SourceService(db)
    total, items = svc.list_sources(
        page=page, page_size=page_size,
        source_type=source_type, status=status, category=category,
    )
    return PagedResponse(
        total=total, page=page, page_size=page_size,
        items=[IntelSourceResponse.model_validate(s) for s in items],
    )


@router.post("", response_model=IntelSourceResponse, status_code=201)
def create_source(
    payload: IntelSourceCreate,
    db: Session = Depends(get_db),
):
    """新增情报源。"""
    svc = SourceService(db)
    source = svc.create_source(payload)
    return IntelSourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=IntelSourceResponse)
def update_source(
    source_id: int,
    payload: IntelSourceUpdate,
    db: Session = Depends(get_db),
):
    """更新情报源信息。"""
    svc = SourceService(db)
    source = svc.update_source(source_id, payload)
    if not source:
        raise HTTPException(status_code=404, detail="情报源不存在")
    return IntelSourceResponse.model_validate(source)


@router.delete("/{source_id}", response_model=SuccessResponse)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """删除情报源。"""
    svc = SourceService(db)
    ok = svc.delete_source(source_id)
    if not ok:
        raise HTTPException(status_code=404, detail="情报源不存在")
    return SuccessResponse(message="删除成功")


@router.get("/{source_id}/health")
def get_source_health(
    source_id: int,
    db: Session = Depends(get_db),
):
    """查询情报源健康状态详情。"""
    svc = SourceService(db)
    health = svc.get_source_health(source_id)
    if not health:
        raise HTTPException(status_code=404, detail="情报源不存在")
    return health


@router.post("/import", response_model=SuccessResponse)
async def import_sources(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """CSV 批量导入情报源。"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    content = await file.read()
    svc = SourceService(db)
    count = svc.import_from_csv(content.decode("utf-8-sig"))
    return SuccessResponse(message=f"成功导入 {count} 条情报源")


@router.get("/export")
def export_sources(db: Session = Depends(get_db)):
    """CSV 导出所有情报源。"""
    svc = SourceService(db)
    csv_content = svc.export_to_csv()
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=intel_sources_"
                f"{datetime.now().strftime('%Y%m%d')}.csv"
            )
        },
    )
