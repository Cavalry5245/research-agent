"""
Test LLM API rate limits by sending requests until hitting the limit.
"""

import os
import sys
import time
from pathlib import Path

# Set SSL certificate
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.llm_client import LLMClient


def test_rate_limit():
    """Test LLM rate limits by sending simple requests."""

    print("初始化LLM客户端...")
    try:
        client = LLMClient()
        print(f"[OK] 客户端初始化成功")
        print(f"   Provider: {client.base_url}")
        print(f"   Model: {client.model}")
        print()
    except Exception as e:
        print(f"[FAIL] 初始化失败: {e}")
        return

    request_count = 0
    start_time = time.time()

    print("开始发送测试请求...")
    print("-" * 60)

    while request_count < 100:  # 最多测试100次
        try:
            response = client.generate_text("测试")
            request_count += 1
            elapsed = time.time() - start_time
            print(f"[OK] 请求 {request_count:3d} 成功 | 耗时: {elapsed:6.1f}s | 响应长度: {len(response)} 字符")

            # 避免请求太快
            time.sleep(0.5)

        except Exception as e:
            elapsed = time.time() - start_time
            error_str = str(e)

            print()
            print("=" * 60)
            print(f"[FAIL] 在第 {request_count + 1} 次请求时遇到错误")
            print(f"[+] 成功请求数: {request_count}")
            print(f"[+] 总耗时: {elapsed:.1f}秒")
            print(f"[+] 平均每次请求: {elapsed/request_count:.2f}秒" if request_count > 0 else "")
            print()

            # 判断错误类型
            if "429" in error_str or "rate limit" in error_str.lower():
                print("[!] 错误类型: API 速率限制 (Rate Limit)")
                print(f"[*] 建议: 免费tier限额约为 {request_count} 次请求")

                # 检查是否提到时间窗口
                if "minute" in error_str.lower():
                    print("[*] 限制周期: 每分钟")
                elif "hour" in error_str.lower():
                    print("[*] 限制周期: 每小时")
                elif "day" in error_str.lower():
                    print("[*] 限制周期: 每天")

            elif "timeout" in error_str.lower():
                print("[!] 错误类型: 请求超时 (Timeout)")
            elif "connection" in error_str.lower():
                print("[!] 错误类型: 连接错误 (Connection Error)")
            else:
                print("[!] 错误类型: 未知错误")

            print()
            print(f"错误详情:\n{error_str}")
            print("=" * 60)
            break

    if request_count >= 100:
        print()
        print("=" * 60)
        print("[OK] 测试完成: 发送了100次请求未遇到限流")
        print("[*] 当前API配额充足")
        print("=" * 60)


if __name__ == "__main__":
    test_rate_limit()
