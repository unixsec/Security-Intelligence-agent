#!/usr/bin/env python3
# ================================================================
# 安全情报分析智能体 — 评分模型升级脚本
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================
"""
使用说明：
    python scripts/migrate-scoring-model.py \
        --db-host localhost \
        --db-user intel_admin \
        --db-password your_password \
        --new-model-file path/to/new_model.json \
        [--dry-run]

功能：
    1. 从数据库读取当前评分模型配置
    2. 加载新评分模型配置
    3. 对新旧模型的差异进行对比输出
    4. 可选：对最近 N 条情报重新计算评分（回测）
    5. 确认后更新数据库配置（热更新，无需重启服务）
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional

try:
    import pymysql
except ImportError:
    print("请先安装 pymysql：pip install pymysql")
    sys.exit(1)


def compute_total_score(scores: Dict, weights: Dict) -> float:
    """根据权重计算综合分。"""
    total = (
        scores.get("threat_likelihood", 0) * weights.get("threat_likelihood", 0.25)
        + scores.get("business_impact", 0) * weights.get("business_impact", 0.30)
        + scores.get("compliance_impact", 0) * weights.get("compliance_impact", 0.20)
        + scores.get("time_urgency", 0) * weights.get("time_urgency", 0.15)
        + scores.get("source_quality", 0) * weights.get("source_quality", 0.10)
    )
    return round(total, 2)


def determine_p_level(total_score: float, threat: int, urgency: int) -> str:
    """判定 P 级别。"""
    if total_score >= 85 and threat >= 80:
        return "P0"
    elif total_score >= 75 or urgency >= 90:
        return "P1"
    return "P2"


def backtest_scoring(cursor, old_weights: Dict, new_weights: Dict, sample_size: int = 50):
    """对最近 N 条情报进行新旧评分模型对比回测。"""
    print(f"\n[回测] 取最近 {sample_size} 条情报进行新旧模型对比...")

    cursor.execute(
        f"""
        SELECT id, title, score_threat, score_business, score_compliance,
               score_urgency, score_quality, total_score, p_level
        FROM scored_intel
        ORDER BY scored_at DESC
        LIMIT {sample_size}
        """
    )
    rows = cursor.fetchall()

    if not rows:
        print("  没有可用的评分情报，跳过回测。")
        return

    changes = {"P0_up": 0, "P0_down": 0, "P1_up": 0, "P1_down": 0, "score_delta": []}

    for row in rows:
        scores = {
            "threat_likelihood": row["score_threat"],
            "business_impact": row["score_business"],
            "compliance_impact": row["score_compliance"],
            "time_urgency": row["score_urgency"],
            "source_quality": row["score_quality"],
        }

        old_total = compute_total_score(scores, old_weights)
        new_total = compute_total_score(scores, new_weights)
        old_p = row["p_level"]
        new_p = determine_p_level(new_total, row["score_threat"], row["score_urgency"])

        delta = new_total - old_total
        changes["score_delta"].append(delta)

        if old_p != "P0" and new_p == "P0":
            changes["P0_up"] += 1
        elif old_p == "P0" and new_p != "P0":
            changes["P0_down"] += 1
        elif old_p != "P1" and new_p == "P1":
            changes["P1_up"] += 1
        elif old_p == "P1" and new_p != "P1":
            changes["P1_down"] += 1

    avg_delta = sum(changes["score_delta"]) / len(changes["score_delta"])
    print(f"  样本量：{len(rows)} 条")
    print(f"  平均分变化：{avg_delta:+.2f}")
    print(f"  P0 升级：{changes['P0_up']} 条 | P0 降级：{changes['P0_down']} 条")
    print(f"  P1 升级：{changes['P1_up']} 条 | P1 降级：{changes['P1_down']} 条")

    if abs(avg_delta) > 10 or changes["P0_up"] + changes["P0_down"] > sample_size * 0.1:
        print("  ⚠ 变化较大，请仔细审查后再确认升级。")
    else:
        print("  ✓ 变化在可接受范围内。")


def main():
    parser = argparse.ArgumentParser(description="评分模型升级工具")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-user", default="intel_admin")
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--db-name", default="intel_system")
    parser.add_argument("--new-model-file", required=False, help="新模型配置 JSON 文件路径")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backtest-size", type=int, default=50)
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  安全情报分析智能体 — 评分模型升级工具 v1.0")
    print("  作者：alex (unix_sec@163.com)")
    print("=" * 60)

    # 连接数据库
    conn = pymysql.connect(
        host=args.db_host, port=args.db_port,
        user=args.db_user, password=args.db_password,
        database=args.db_name, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    cursor = conn.cursor()

    # 读取当前模型
    cursor.execute("SELECT config_value FROM system_configs WHERE config_key = 'scoring_model'")
    row = cursor.fetchone()
    if not row:
        print("ERROR: 未找到 scoring_model 配置，请先运行 seed.sql。")
        sys.exit(1)

    current_model = row["config_value"] if isinstance(row["config_value"], dict) else json.loads(row["config_value"])
    print(f"\n当前模型版本：{current_model.get('version')} - {current_model.get('name')}")

    old_weights = {d["name"]: d["weight"] for d in current_model.get("dimensions", [])}
    print(f"当前权重：{json.dumps(old_weights, ensure_ascii=False)}")

    # 加载新模型
    if args.new_model_file:
        with open(args.new_model_file, "r", encoding="utf-8") as f:
            new_model = json.load(f)
    else:
        print("\n未指定新模型文件，仅查看当前配置。")
        print(json.dumps(current_model, ensure_ascii=False, indent=2))
        cursor.close()
        conn.close()
        return

    new_weights = {d["name"]: d["weight"] for d in new_model.get("dimensions", [])}
    print(f"\n新模型版本：{new_model.get('version')} - {new_model.get('name')}")
    print(f"新权重：{json.dumps(new_weights, ensure_ascii=False)}")

    # 权重差异对比
    print("\n权重变化对比：")
    for k in set(list(old_weights.keys()) + list(new_weights.keys())):
        old_w = old_weights.get(k, 0)
        new_w = new_weights.get(k, 0)
        delta = new_w - old_w
        marker = f"  ({delta:+.2f})" if delta != 0 else ""
        print(f"  {k}: {old_w:.2f} → {new_w:.2f}{marker}")

    # 回测
    backtest_scoring(cursor, old_weights, new_weights, args.backtest_size)

    # 确认并更新
    if args.dry_run:
        print("\n[DRY-RUN] 不执行实际更新。")
    else:
        confirm = input("\n确认将评分模型升级为新版本？[y/N] ")
        if confirm.lower() != "y":
            print("已取消。")
            return

        cursor.execute(
            "UPDATE system_configs SET config_value = %s, updated_by = %s "
            "WHERE config_key = 'scoring_model'",
            (json.dumps(new_model, ensure_ascii=False), f"migrate-script/{datetime.now().isoformat()}"),
        )
        conn.commit()
        print(f"\n✓ 评分模型已升级至版本 {new_model.get('version')}（热更新已生效）")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
