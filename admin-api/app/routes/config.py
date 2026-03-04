# ================================================================
# 安全情报分析智能体 — 系统配置 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.database import engine, get_db
from app.models.schemas import ConfigResponse, ConfigUpdate, SuccessResponse

router = APIRouter(prefix="/config", tags=["系统配置"])


@router.get("/{config_key}")
def get_config(config_key: str, db: Session = Depends(get_db)):
    """读取系统配置项。"""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM system_configs WHERE config_key = :key"),
            {"key": config_key},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"配置项 {config_key} 不存在")
    return dict(row._mapping)


@router.put("/{config_key}", response_model=SuccessResponse)
def update_config(
    config_key: str,
    payload: ConfigUpdate,
    db: Session = Depends(get_db),
):
    """更新系统配置项（含评分模型、LLM 配置等，热更新生效）。"""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM system_configs WHERE config_key = :key"),
            {"key": config_key},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"配置项 {config_key} 不存在")

        import json
        conn.execute(
            text(
                "UPDATE system_configs SET config_value = :val, updated_by = 'admin-api' "
                "WHERE config_key = :key"
            ),
            {"val": json.dumps(payload.config_value, ensure_ascii=False), "key": config_key},
        )
        conn.commit()

    return SuccessResponse(message=f"配置项 {config_key} 更新成功")
