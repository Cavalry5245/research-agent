import os
import sys
import json
import time
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


def build_candidate_base_urls(base_url: str) -> List[str]:
    """
    兼容两种写法：
    1. LLM_BASE_URL=http://localhost:18080/v1
    2. LLM_BASE_URL=http://localhost:18080
    """
    base_url = base_url.rstrip("/")
    candidates = [base_url]

    if not base_url.endswith("/v1"):
        candidates.append(base_url + "/v1")

    return candidates


def call_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "请只回复 OK，用来测试 LLM 配置是否可用。",
            },
        ],
        "temperature": 0,
        "max_tokens": 20,
    }

    start = time.time()

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout,
    )

    elapsed = time.time() - start

    result = {
        "url": url,
        "status_code": response.status_code,
        "elapsed_seconds": round(elapsed, 3),
        "ok": response.ok,
        "raw_text": response.text,
    }

    try:
        result["json"] = response.json()
    except Exception:
        result["json"] = None

    return result


def extract_answer(response_json: Optional[Dict[str, Any]]) -> str:
    if not response_json:
        return ""

    try:
        return response_json["choices"][0]["message"]["content"]
    except Exception:
        return ""


def main() -> int:
    load_dotenv()

    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    print("=" * 60)
    print("LLM 配置测试")
    print("=" * 60)

    print(f"LLM_BASE_URL: {base_url}")
    print(f"LLM_API_KEY : {mask_key(api_key)}")
    print(f"LLM_MODEL   : {model}")
    print("-" * 60)

    missing = []
    if not base_url:
        missing.append("LLM_BASE_URL")
    if not api_key:
        missing.append("LLM_API_KEY")
    if not model:
        missing.append("LLM_MODEL")

    if missing:
        print("❌ 缺少必要环境变量：")
        for item in missing:
            print(f"  - {item}")
        print("\n请检查项目根目录下的 .env 文件。")
        return 1

    candidate_base_urls = build_candidate_base_urls(base_url)

    last_result = None

    for candidate_base_url in candidate_base_urls:
        print(f"正在测试接口：{candidate_base_url}/chat/completions")

        try:
            result = call_chat_completion(
                base_url=candidate_base_url,
                api_key=api_key,
                model=model,
            )
            last_result = result

            if result["ok"]:
                answer = extract_answer(result["json"])

                print("\n✅ LLM 配置可用")
                print(f"请求地址: {result['url']}")
                print(f"状态码  : {result['status_code']}")
                print(f"耗时    : {result['elapsed_seconds']} 秒")
                print(f"模型回复: {answer}")
                return 0

            print(f"当前地址测试失败，状态码：{result['status_code']}")

        except requests.exceptions.Timeout:
            print("当前地址请求超时。")
        except requests.exceptions.ConnectionError:
            print("当前地址连接失败。")
        except Exception as e:
            print(f"当前地址出现异常：{type(e).__name__}: {e}")

        print("-" * 60)

    print("\n❌ LLM 配置不可用")

    if last_result:
        print(f"最后请求地址: {last_result['url']}")
        print(f"最后状态码  : {last_result['status_code']}")
        print("\n服务端返回内容：")

        try:
            parsed = last_result.get("json")
            if parsed is not None:
                print(json.dumps(parsed, ensure_ascii=False, indent=2))
            else:
                print(last_result.get("raw_text", ""))
        except Exception:
            print(last_result.get("raw_text", ""))

    print("\n常见原因：")
    print("1. LLM_BASE_URL 没有写对，例如应该是 http://localhost:18080/v1")
    print("2. LLM_API_KEY 无效或没有按 Bearer 方式认证")
    print("3. LLM_MODEL 名称不存在或中转站不支持")
    print("4. 本地服务没有启动，或者端口无法访问")
    print("5. 中转站接口不是 OpenAI 兼容格式")

    return 1


if __name__ == "__main__":
    sys.exit(main())