# ================================================================
# 安全情报分析智能体 — Dify Workflow API 客户端
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
import time
from typing import Any, Dict, Optional

import requests

from .config import DifyConfig

logger = logging.getLogger(__name__)


class DifyClient:
    """Dify Workflow API 客户端，负责触发工作流。"""

    def __init__(self, config: DifyConfig):
        self._base = config.api_base.rstrip("/")
        self._key = config.api_key
        self._wf_dedup_id = config.wf_dedup_id
        self._wf_analysis_id = config.wf_analysis_id
        self._timeout = config.timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        })

    def trigger_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        user: str = "collector",
        max_retries: int = 3,
        backoff: float = 2.0,
    ) -> Optional[Dict]:
        """
        触发指定 Dify Workflow，支持指数退避重试。

        Args:
            workflow_id: Dify Workflow 的 API ID
            inputs: 工作流输入参数
            user: 请求发起用户标识
            max_retries: 最大重试次数
            backoff: 初始退避秒数（指数增长）

        Returns:
            Workflow 运行响应 JSON，失败时返回 None
        """
        url = f"{self._base}/workflows/run"
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user,
        }
        # 如果 Dify 支持按 workflow_id 路由，加入 header
        headers = {"X-Workflow-ID": workflow_id}

        for attempt in range(1, max_retries + 1):
            try:
                resp = self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    "Workflow %s triggered successfully (attempt %d), "
                    "run_id=%s",
                    workflow_id, attempt, data.get("workflow_run_id"),
                )
                return data
            except requests.exceptions.RequestException as e:
                wait = backoff ** attempt
                logger.warning(
                    "Workflow %s trigger failed (attempt %d/%d): %s. "
                    "Retrying in %.1fs...",
                    workflow_id, attempt, max_retries, e, wait,
                )
                if attempt < max_retries:
                    time.sleep(wait)
                else:
                    logger.error(
                        "Workflow %s trigger failed after %d attempts.",
                        workflow_id, max_retries,
                    )
                    return None

    def trigger_dedup(self, raw_intel_id: int) -> Optional[Dict]:
        """触发 WF-3 语义去重 Workflow。"""
        return self.trigger_workflow(
            self._wf_dedup_id,
            {"raw_intel_id": raw_intel_id},
        )

    def trigger_analysis(self, raw_intel_id: int) -> Optional[Dict]:
        """触发 WF-2 情报分析评分 Workflow（去重后新情报）。"""
        return self.trigger_workflow(
            self._wf_analysis_id,
            {"raw_intel_id": raw_intel_id},
        )

    def health_check(self) -> bool:
        """检查 Dify API 连通性。"""
        try:
            resp = self._session.get(
                f"{self._base}/info",
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error("Dify health check failed: %s", e)
            return False
