#!/usr/bin/env python3
"""
デバッグ用：DXFファイルの全エンティティを表示
"""
import sys
import ezdxf

if len(sys.argv) < 2:
    print("Usage: python3 debug_dxf.py <dxf_file>")
    sys.exit(1)

doc = ezdxf.readfile(sys.argv[1])
msp = doc.modelspace()

print(f"📄 ファイル: {sys.argv[1]}")
print(f"バージョン: {doc.dxfversion}")
print(f"\n全エンティティ一覧:")
print("="*60)

entity_counts = {}
for entity in msp:
    etype = entity.dxftype()
    entity_counts[etype] = entity_counts.get(etype, 0) + 1
    
    print(f"\n{etype} (レイヤー: {entity.dxf.layer if hasattr(entity.dxf, 'layer') else 'N/A'})")
    
    # TEXTの詳細
    if etype == 'TEXT':
        print(f"  → テキスト: '{entity.dxf.text}'")
        print(f"  → 位置: {entity.dxf.insert}")
    
    # MTEXTの詳細
    if etype == 'MTEXT':
        text = getattr(entity, "plain_text", lambda: "")()
        print(f"  → テキスト: '{text}'")

print(f"\n{'='*60}")
print("エンティティ統計:")
for etype, count in sorted(entity_counts.items()):
    print(f"  {etype}: {count}件")

print(f"\n📝 TEXT/MTEXTエンティティを検索...")
text_found = False
for entity in msp.query('TEXT MTEXT'):
    text_found = True
    if entity.dxftype() == 'TEXT':
        print(f"  TEXT: '{entity.dxf.text}'")
    else:
        text = getattr(entity, "plain_text", lambda: "")()
        print(f"  MTEXT: '{text}'")

if not text_found:
    print("  ⚠️ TEXT/MTEXTエンティティが見つかりませんでした")
