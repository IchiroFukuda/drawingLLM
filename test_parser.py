#!/usr/bin/env python3
"""
簡単なパーサーテスト
"""
import sys
from pathlib import Path
from enhanced_dxf_parser import EnhancedDXFParser

if len(sys.argv) < 2:
    print("Usage: python3 test_parser.py <dxf_file>")
    sys.exit(1)

print(f"解析開始: {sys.argv[1]}")
print("="*60)

parser = EnhancedDXFParser(Path(sys.argv[1]))

# 個別に各メソッドを呼び出してテスト
print("\n1. メタデータ抽出...")
parser._extract_metadata()
print(f"   ✓ ファイル名: {parser.metadata['filename']}")
print(f"   ✓ レイヤー数: {parser.metadata['layer_count']}")

print("\n2. 寸法抽出...")
parser._extract_dimensions()
print(f"   ✓ 寸法数: {len(parser.dimensions)}")

print("\n3. テキスト抽出...")
parser._extract_texts()
print(f"   ✓ テキスト数: {len(parser.texts)}")
print(f"   ✓ 材質情報: {len(parser.material_info)}")
for text in parser.texts[:5]:  # 最初の5件だけ表示
    print(f"      - {text['content']}")

print("\n4. エンティティ抽出...")
parser._extract_entities()
print(f"   ✓ エンティティ数: {len(parser.entities)}")
summary = parser._summarize_entities()
for etype, count in summary.items():
    print(f"      - {etype}: {count}件")

print("\n" + "="*60)
print("完了！")
