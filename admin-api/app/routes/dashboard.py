# ================================================================
# 安全情报分析智能体 — 仪表盘 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from datetime import datetime, date

from fastapi import APIRouter, Depends
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import DashboardStats, HealthStatus

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """获取系统概览统计数据。"""
    from app.models.database import engine
    from sqlalchemy import text

    today_start = datetime.combine(date.today(), datetime.min.time())

    with engine.connect() as conn:
        total_sources = conn.execute(
            text("SELECT COUNT(*) FROM intel_sources")
        ).scalar()
        active_sources = conn.execute(
            text("SELECT COUNT(*) FROM intel_sources WHERE status='active'")
        ).scalar()
        error_sources = conn.execute(
            text("SELECT COUNT(*) FROM intel_sources WHERE status='error'")
        ).scalar()
        today_raw = conn.execute(
            text("SELECT COUNT(*) FROM raw_intel WHERE collected_at >= :ts"),
            {"ts": today_start},
        ).scalar()
        today_scored = conn.execute(
            text("SELECT COUNT(*) FROM scored_intel WHERE scored_at >= :ts"),
            {"ts": today_start},
        ).scalar()
        today_p0 = conn.execute(
            text("SELECT COUNT(*) FROM scored_intel WHERE p_level='P0' AND scored_at >= :ts"),
            {"ts": today_start},
        ).scalar()
        today_p1 = conn.execute(
            text("SELECT COUNT(*) FROM scored_intel WHERE p_level='P1' AND scored_at >= :ts"),
            {"ts": today_start},
        ).scalar()
        today_reports = conn.execute(
            text("SELECT COUNT(*) FROM reports WHERE created_at >= :ts"),
            {"ts": today_start},
        ).scalar()

    return DashboardStats(
        total_sources=total_sources or 0,
        active_sources=active_sources or 0,
        error_sources=error_sources or 0,
        today_raw_intel=today_raw or 0,
        today_scored_intel=today_scored or 0,
        today_p0_alerts=today_p0 or 0,
        today_p1_alerts=today_p1 or 0,
        today_reports=today_reports or 0,
        last_updated=datetime.utcnow(),
    )


@router.get("/health", response_model=HealthStatus)
def get_health_status(db: Session = Depends(get_db)):
    """获取系统健康状态。"""
    from app.models.database import engine
    from sqlalchemy import text

    # 检查数据库
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # 检查 Dify API
    dify_ok = False
    try:
        import requests
        from app.config import get_settings
        settings = get_settings()
        resp = requests.get(f"{settings.dify_api_base}/info", timeout=5)
        dify_ok = resp.status_code == 200
    except Exception:
        pass

    # 计算活跃情报源比例
    active_ratio = 0.0
    try:
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM intel_sources")).scalar() or 0
            active = conn.execute(
                text("SELECT COUNT(*) FROM intel_sources WHERE status='active'")
            ).scalar() or 0
            active_ratio = active / total if total > 0 else 1.0
    except Exception:
        pass

    if not db_ok:
        overall = "critical"
    elif not dify_ok or active_ratio < 0.5:
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthStatus(
        status=overall,
        database=db_ok,
        dify_api=dify_ok,
        active_sources_ratio=active_ratio,
        details={
            "database": "OK" if db_ok else "UNREACHABLE",
            "dify_api": "OK" if dify_ok else "UNREACHABLE",
            "active_sources_ratio": f"{active_ratio:.1%}",
        },
    )


@router.get("/feedbacks")
def get_feedback_summary(db: Session = Depends(get_db)):
    """获取最近 30 天的读者反馈汇总。"""
    from app.models.database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT rating, COUNT(*) as cnt
                FROM feedbacks
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY rating
            """)
        ).fetchall()

    summary = {row[0]: row[1] for row in rows}
    total = sum(summary.values())
    valuable = summary.get("valuable", 0)
    not_valuable = summary.get("not_valuable", 0)

    return {
        "period": "last_30_days",
        "total_feedbacks": total,
        "valuable": valuable,
        "not_valuable": not_valuable,
        "satisfaction_rate": f"{valuable / total * 100:.1f}%" if total > 0 else "N/A",
    }
