#!/usr/bin/env python3

"""
JSON → Supabase インポートスクリプト
Supabase Python Clientを使用してデータを投入
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import os

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase is not installed. Please run: pip install supabase", file=sys.stderr)
    sys.exit(1)


def get_supabase_client() -> Client:
    """Supabaseクライアントを取得"""
    url = os.getenv("SUPABASE_URL") or "https://ozlbcjhfwzgwadumdwfz.supabase.co"
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY environment variable is not set.", file=sys.stderr)
        print("Example: export SUPABASE_SERVICE_ROLE_KEY='eyJ...'", file=sys.stderr)
        sys.exit(1)
    
    return create_client(url, key)


def insert_drawing(supabase: Client, json_data: Dict[str, Any]) -> str:
    """drawingsテーブルにレコードを挿入"""
    meta = json_data.get("meta", {})
    
    drawing_data = {
        "filename": meta.get("filename"),
        "file_path": meta.get("path"),
        "version": meta.get("version"),
        "layer_count": meta.get("layer_count", 0),
        "entity_count": meta.get("entity_sampled", 0),
        "layers": meta.get("layers", []),
        "entity_counts": meta.get("entity_counts", {})
    }
    
    result = supabase.table("drawings").insert(drawing_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to insert drawing")
    
    return result.data[0]["id"]


def prepare_entity_data(drawing_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
    """エンティティデータをSupabase用に整形"""
    return {
        "drawing_id": drawing_id,
        "type": entity.get("type"),
        "layer": entity.get("layer"),
        "color": entity.get("color"),
        "linetype": entity.get("linetype"),
        "lineweight": entity.get("lineweight"),
        "bbox": entity.get("bbox"),
        "start": entity.get("start"),
        "end": entity.get("end"),
        "center": entity.get("center"),
        "radius": entity.get("radius"),
        "start_angle": entity.get("start_angle"),
        "end_angle": entity.get("end_angle"),
        "points": entity.get("points"),
        "is_closed": entity.get("is_closed"),
        "fit_points": entity.get("fit_points"),
        "major_axis": entity.get("major_axis"),
        "ratio": entity.get("ratio"),
        "text": entity.get("text"),
        "position": entity.get("position"),
        "name": entity.get("name"),
        "insert": entity.get("insert"),
        "xscale": entity.get("xscale"),
        "yscale": entity.get("yscale"),
        "rotation": entity.get("rotation"),
        "measurement": entity.get("measurement"),
        "solid_fill": entity.get("solid_fill"),
        "pattern_name": entity.get("pattern_name"),
    }


def insert_entities_batch(supabase: Client, drawing_id: str, entities: List[Dict[str, Any]]):
    """entitiesテーブルに複数レコードをバッチ挿入"""
    if not entities:
        return
    
    # Supabaseは一度に大量のデータを送ると失敗する可能性があるので、
    # バッチサイズを制限
    batch_size = 100
    
    for i in range(0, len(entities), batch_size):
        batch = entities[i:i + batch_size]
        data = [prepare_entity_data(drawing_id, e) for e in batch]
        
        result = supabase.table("entities").insert(data).execute()
        
        if not result.data:
            raise Exception(f"Failed to insert entities batch {i//batch_size + 1}")
        
        print(f"  ✓ Inserted {len(data)} entities (batch {i//batch_size + 1})")


def import_json_file(supabase: Client, json_path: Path) -> Dict[str, Any]:
    """1つのJSONファイルをSupabaseにインポート"""
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"\n📄 Processing: {json_path.name}")
        
        # drawingsテーブルに挿入
        print("  → Inserting drawing metadata...")
        drawing_id = insert_drawing(supabase, data)
        print(f"  ✓ Drawing ID: {drawing_id}")
        
        # entitiesテーブルに一括挿入
        entities = data.get("entities", [])
        print(f"  → Inserting {len(entities)} entities...")
        insert_entities_batch(supabase, drawing_id, entities)
        
        return {
            "file": str(json_path),
            "ok": True,
            "drawing_id": drawing_id,
            "entity_count": len(entities)
        }
    except Exception as e:
        return {
            "file": str(json_path),
            "ok": False,
            "error": str(e)
        }


def iter_json_files(target: Path):
    """JSONファイルを列挙"""
    if target.is_file() and target.suffix.lower() == ".json":
        # index.jsonlは除外
        if target.name != "index.jsonl":
            yield target
    elif target.is_dir():
        for p in target.glob("*.json"):
            if p.name != "index.jsonl":
                yield p


def main():
    ap = argparse.ArgumentParser(description="JSON → Supabase インポーター")
    ap.add_argument("input", help="JSONファイルまたはディレクトリ")
    ap.add_argument("--url", help="Supabase URL (省略時は環境変数 SUPABASE_URL を使用)")
    ap.add_argument("--key", help="Supabase Service Role Key (省略時は環境変数 SUPABASE_SERVICE_ROLE_KEY を使用)")
    ap.add_argument("--dry-run", action="store_true", help="実際には挿入せず、処理内容のみ表示")
    args = ap.parse_args()
    
    src = Path(args.input)
    
    # 環境変数を上書き（オプション）
    if args.url:
        os.environ["SUPABASE_URL"] = args.url
    if args.key:
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = args.key
    
    # Supabaseクライアント
    if args.dry_run:
        print("[DRY RUN MODE] Supabaseには接続しません")
        supabase = None
    else:
        supabase = get_supabase_client()
        print("✓ Supabaseに接続しました")
    
    # JSONファイルを処理
    found = False
    results = []
    
    for json_path in iter_json_files(src):
        found = True
        
        if args.dry_run:
            print(f"\n[DRY RUN] {json_path}")
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  - Entities: {len(data.get('entities', []))}")
            results.append({"file": str(json_path), "ok": True, "dry_run": True})
        else:
            result = import_json_file(supabase, json_path)
            results.append(result)
            status = "✓" if result.get("ok") else "✗"
            print(f"\n[{status}] {json_path.name}")
            if not result.get("ok"):
                print(f"    Error: {result.get('error')}")
    
    if not found:
        print("No JSON files found.", file=sys.stderr)
        sys.exit(1)
    
    # サマリー
    success_count = sum(1 for r in results if r.get("ok"))
    fail_count = len(results) - success_count
    
    print(f"\n{'='*50}")
    print(f"✨ 完了: {success_count}件成功, {fail_count}件失敗")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
