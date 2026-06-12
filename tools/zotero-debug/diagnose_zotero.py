"""
Zotero API 诊断工具 - 绕过代理测试
"""
import socket
import urllib.request
import json
import subprocess

print("=" * 60)
print("Zotero API 诊断")
print("=" * 60)

# 1. 检查 Zotero 进程
print("\n[1] 检查 Zotero 是否运行...")
try:
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq zotero.exe'],
                          capture_output=True, text=True, timeout=5)
    if 'zotero.exe' in result.stdout:
        print("✓ Zotero 正在运行")
    else:
        print("✗ Zotero 未运行")
        input("\n按回车退出...")
        exit(1)
except:
    print("? 无法检查")

# 2. 检查端口
print("\n[2] 检查端口 23119...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
result = sock.connect_ex(('127.0.0.1', 23119))
sock.close()

if result == 0:
    print("✓ 端口 23119 正在监听")
else:
    print("✗ 端口 23119 未监听")
    print("  → Zotero HTTP 服务器未启动")
    input("\n按回车退出...")
    exit(1)

# 3. 测试 API（无代理）
print("\n[3] 测试 API 连接（绕过代理）...")
try:
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)

    req = urllib.request.Request('http://127.0.0.1:23119/api/users/0/collections')
    response = opener.open(req, timeout=5)

    if response.status == 200:
        data = response.read().decode('utf-8')
        collections = json.loads(data)
        print(f"✓ 成功！找到 {len(collections)} 个集合\n")

        print("=" * 60)
        print("你的 Collection 列表：")
        print("=" * 60)
        for i, coll in enumerate(collections, 1):
            key = coll.get('key', 'N/A')
            name = coll.get('data', {}).get('name', 'Unnamed')
            print(f"\n{i}. {name}")
            print(f"   Collection ID: {key}")

        print("\n" + "=" * 60)
        print("复制上面的 Collection ID 在 ResearchAgent 中使用")
    else:
        print(f"✗ HTTP 错误: {response.status}")

except urllib.error.URLError as e:
    print(f"✗ 连接失败: {e.reason}")
    print("\n可能原因：")
    print("  1. 防火墙或安全软件阻止")
    print("  2. Zotero 配置问题")
    print("  3. 本地回环被禁用（罕见）")

except Exception as e:
    print(f"✗ 错误: {e}")

print("\n" + "=" * 60)
input("按回车退出...")
