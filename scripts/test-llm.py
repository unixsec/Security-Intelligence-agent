#!/usr/bin/env python3
# ================================================================
# 安全情报分析智能体 — LLM 连通性和能力验证脚本
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================
"""
使用说明：
    python scripts/test-llm.py \
        --api-url http://deepseek-server.llm-serving.svc:8000/v1 \
        --api-key your-api-key \
        --model deepseek-chat

测试内容：
    1. API 连通性检查
    2. 基础对话能力
    3. JSON 结构化输出能力（情报分析格式）
    4. 响应延迟测量
"""

import argparse
import json
import time
from typing import Optional

import requests


def test_connectivity(api_url: str, api_key: str) -> bool:
    """测试 API 基础连通性。"""
    print("\n[1] 测试 API 连通性...")
    try:
        resp = requests.get(
            f"{api_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            print(f"    ✓ API 连通正常，可用模型：{[m.get('id') for m in models]}")
            return True
        else:
            print(f"    ✗ API 返回错误：{resp.status_code} {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"    ✗ 连接失败：{e}")
        return False


def test_basic_chat(api_url: str, api_key: str, model: str) -> bool:
    """测试基础对话能力和响应时间。"""
    print("\n[2] 测试基础对话能力...")
    try:
        start = time.time()
        resp = requests.post(
            f"{api_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "请用一句话介绍勒索软件的威胁。"}
                ],
                "max_tokens": 100,
                "temperature": 0.3,
            },
            timeout=60,
        )
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"    ✓ 对话成功（{elapsed:.2f}s）")
            print(f"    响应：{content[:120]}")
            return True
        else:
            print(f"    ✗ 对话失败：{resp.status_code}")
            return False
    except Exception as e:
        print(f"    ✗ 异常：{e}")
        return False


def test_json_output(api_url: str, api_key: str, model: str) -> bool:
    """测试 JSON 结构化输出能力（情报分析格式）。"""
    print("\n[3] 测试 JSON 结构化输出...")

    system_prompt = """你是安全情报分析师，请分析安全情报并输出严格的 JSON 格式，不要添加任何说明文字。"""

    user_prompt = """
请分析以下情报：

标题：Microsoft Exchange Server 远程代码执行漏洞（CVE-2024-XXXX）
来源：CISA
内容：Microsoft Exchange Server 存在严重的远程代码执行漏洞，
攻击者无需身份验证即可在目标服务器上执行任意代码。CVSS 评分 9.8。
已有在野利用报告。

输出格式：
{
  "title": "30字以内标题",
  "intel_type": "vulnerability",
  "severity": "high",
  "summary_zh": "摘要",
  "scores": {
    "threat_likelihood": 整数0-100,
    "business_impact": 整数0-100,
    "compliance_impact": 整数0-100,
    "time_urgency": 整数0-100,
    "source_quality": 整数0-100
  }
}
"""

    try:
        start = time.time()
        resp = requests.post(
            f"{api_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.1,
            },
            timeout=90,
        )
        elapsed = time.time() - start

        if resp.status_code != 200:
            print(f"    ✗ API 错误：{resp.status_code}")
            return False

        content = resp.json()["choices"][0]["message"]["content"]

        # 尝试解析 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(content)
        scores = parsed.get("scores", {})

        print(f"    ✓ JSON 输出解析成功（{elapsed:.2f}s）")
        print(f"    标题：{parsed.get('title', 'N/A')}")
        print(f"    类型：{parsed.get('intel_type')} | 严重度：{parsed.get('severity')}")
        print(f"    评分：威胁={scores.get('threat_likelihood')} | "
              f"业务={scores.get('business_impact')} | "
              f"紧迫={scores.get('time_urgency')}")
        return True

    except json.JSONDecodeError as e:
        print(f"    ✗ JSON 解析失败：{e}")
        print(f"    原始输出：{content[:200]}")
        return False
    except Exception as e:
        print(f"    ✗ 异常：{e}")
        return False


def test_latency(api_url: str, api_key: str, model: str, iterations: int = 3) -> None:
    """多轮延迟测试。"""
    print(f"\n[4] 延迟测试（{iterations} 轮）...")
    times = []
    for i in range(iterations):
        try:
            start = time.time()
            resp = requests.post(
                f"{api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "回复 OK"}],
                    "max_tokens": 10,
                },
                timeout=30,
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                times.append(elapsed)
                print(f"    轮次 {i + 1}: {elapsed:.2f}s")
        except Exception as e:
            print(f"    轮次 {i + 1}: 失败 ({e})")

    if times:
        avg = sum(times) / len(times)
        print(f"    平均延迟：{avg:.2f}s | 最快：{min(times):.2f}s | 最慢：{max(times):.2f}s")
        if avg < 5:
            print("    ✓ 延迟良好（< 5s）")
        elif avg < 15:
            print("    ⚠ 延迟可接受（< 15s）")
        else:
            print("    ✗ 延迟过高（>= 15s），建议检查 GPU 资源")


def main():
    parser = argparse.ArgumentParser(description="LLM 连通性和能力验证")
    parser.add_argument("--api-url",
                        default="http://deepseek-server.llm-serving.svc.cluster.local:8000/v1",
                        help="LLM API 基础 URL")
    parser.add_argument("--api-key", default="", help="API Key")
    parser.add_argument("--model", default="deepseek-chat", help="模型名称")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  安全情报分析智能体 — LLM 能力验证")
    print("  作者：alex (unix_sec@163.com)")
    print("=" * 60)
    print(f"  API URL：{args.api_url}")
    print(f"  模型：   {args.model}")

    results = []
    results.append(("API 连通性", test_connectivity(args.api_url, args.api_key)))
    results.append(("基础对话", test_basic_chat(args.api_url, args.api_key, args.model)))
    results.append(("JSON 结构化输出", test_json_output(args.api_url, args.api_key, args.model)))
    test_latency(args.api_url, args.api_key, args.model)

    print("\n" + "=" * 60)
    print("  验证结果汇总：")
    all_pass = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}  {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n  ✓ 所有测试通过，LLM 已就绪！")
    else:
        print("\n  ✗ 部分测试失败，请检查 LLM 配置。")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
