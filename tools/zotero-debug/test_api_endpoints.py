"""
测试 Zotero 9.x 可能的 API 端点
"""
import urllib.request
import json

endpoints = [
    'http://127.0.0.1:23119/api/users/0/collections',
    'http://127.0.0.1:23119/users/0/collections',
    'http://localhost:23119/api/users/0/collections',
    'http://127.0.0.1:23119/connector/collections',
]

print("测试 Zotero API 端点...")
print("=" * 60)

proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler)

for endpoint in endpoints:
    print(f"\n尝试: {endpoint}")
    try:
        req = urllib.request.Request(endpoint)
        response = opener.open(req, timeout=3)

        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            print(f"✓ 成功！返回 {len(data)} 个集合")

            if data:
                print("\n集合列表：")
                for i, coll in enumerate(data[:3], 1):
                    name = coll.get('data', {}).get('name', coll.get('name', 'Unknown'))
                    key = coll.get('key', 'N/A')
                    print(f"  {i}. {name} (ID: {key})")
            break
    except Exception as e:
        print(f"✗ 失败: {type(e).__name__}")

print("\n" + "=" * 60)
input("按回车退出...")
