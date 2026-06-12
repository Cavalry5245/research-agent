"""
直接从 Zotero 数据库读取 Collection ID
"""
import sqlite3

zotero_db = r"D:\HC\Zotero\zotero.sqlite"

try:
    conn = sqlite3.connect(zotero_db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.key,
            c.collectionName,
            (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as count
        FROM collections c
        ORDER BY c.collectionName
    """)

    collections = cursor.fetchall()

    print("=" * 60)
    print(f"从数据库读取到 {len(collections)} 个集合")
    print("=" * 60)

    for key, name, count in collections:
        print(f"\n{name}")
        print(f"  Collection ID: {key}")
        print(f"  论文数量: {count}")

    print("\n" + "=" * 60)
    print("使用说明：")
    print("复制上面的 Collection ID 在 ResearchAgent 中使用")
    print("\n.env 配置：")
    print("ENABLE_ZOTERO=true")
    print("ZOTERO_DATA_DIR=D:/HC/Zotero")

    conn.close()

except Exception as e:
    print(f"错误: {e}")
    print("\n请确认 Zotero 数据目录路径是否正确")

input("\n按回车退出...")
