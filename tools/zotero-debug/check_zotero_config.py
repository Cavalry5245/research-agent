"""
读取 Zotero 配置文件，检查 HTTP 服务器设置
"""
prefs_path = r"C:\Users\HC\AppData\Roaming\Zotero\Zotero\Profiles\chg1pqcd.default\prefs.js"

print("检查 Zotero HTTP 服务器配置...")
print("=" * 60)

try:
    with open(prefs_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # 检查关键配置
    configs = {
        'httpServer.enabled': False,
        'httpServer.port': False,
        'httpServer.localAPI.enabled': False,
    }

    for line in content.split('\n'):
        if 'httpServer' in line and 'user_pref' in line:
            print(line.strip())
            for key in configs:
                if key in line:
                    configs[key] = True

    print("\n" + "=" * 60)
    print("配置检查结果：")
    print("=" * 60)

    for key, found in configs.items():
        status = "✓ 找到" if found else "✗ 缺失"
        print(f"{status}: extensions.zotero.{key}")

    print("\n" + "=" * 60)
    if not configs['httpServer.enabled']:
        print("问题：缺少 httpServer.enabled 配置！")
        print("\n修复方法：")
        print("1. 关闭 Zotero")
        print("2. 在 prefs.js 末尾添加：")
        print('   user_pref("extensions.zotero.httpServer.enabled", true);')
        print("3. 保存并重启 Zotero")
    elif not configs['httpServer.port']:
        print("问题：缺少端口配置！")
        print("但端口已监听，可能使用默认值 23119")
    else:
        print("配置看起来正确...")
        print("可能是其他问题（防火墙/Zotero 版本等）")

except Exception as e:
    print(f"错误: {e}")

input("\n按回车退出...")
