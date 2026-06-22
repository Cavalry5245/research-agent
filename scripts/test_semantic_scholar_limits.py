"""
Test Semantic Scholar API rate limiting.
"""

import os
import time
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

import httpx

API_BASE = "https://api.semanticscholar.org/graph/v1"

def test_with_rate_limit():
    """Test with 1 second delay between requests."""
    print("测试 Semantic Scholar API 速率限制")
    print("策略: 1秒延迟")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    for i in range(10):
        time.sleep(1.1)  # 确保1秒间隔

        try:
            response = httpx.get(
                f"{API_BASE}/paper/search",
                params={"query": "machine learning", "limit": 1},
                timeout=10.0
            )

            if response.status_code == 200:
                success_count += 1
                print(f"[OK] 请求 {i+1:2d} | 状态: 200")
            elif response.status_code == 429:
                fail_count += 1
                print(f"[FAIL] 请求 {i+1:2d} | 状态: 429 (限流)")
            else:
                print(f"[WARN] 请求 {i+1:2d} | 状态: {response.status_code}")

        except Exception as e:
            fail_count += 1
            print(f"[ERROR] 请求 {i+1:2d} | {e}")

    print("-" * 60)
    print(f"成功: {success_count}/10")
    print(f"失败: {fail_count}/10")

    if success_count >= 8:
        print("\n[OK] 速率限制有效，可以正常使用")
    else:
        print("\n[FAIL] 仍然遇到限流，需要申请API key")


if __name__ == "__main__":
    test_with_rate_limit()
