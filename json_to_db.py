#!/usr/bin/env python3

"""
JSON → PostgreSQL/Supabase インポートスクリプト
DXFから変換したJSONファイルをデータベースに格納する
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import os

# pip install psycopg2-binary or psycopg[binary]
try:
    import psycopg2
    from psycopg2.extras import Json, execute_batch
except ImportError:
    print("ERROR: psycopg2 is not installed. Please run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def get_db_connection(connection_string: Optional[str] = None):
    """データベース接続を取得"""
    if connection_string is None:
        # 環境変数から接続情報を取得
        connection_string = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    
    if not connection_string:
        print("ERROR: DATABASE_URL or SUPABASE_DB_URL environment variable is not set.", file=sys.stderr)
        print("Example: export DATABASE_URL='postgresql://user:password@host:port/dbname'", file=sys.stderr)
        sys.exit(1)
    
    return psycopg2.connect(connection_string)


def insert_drawing(conn, json_data: Dict[str, Any]) -> str:
    """drawingsテーブルにレコードを挿入"""
    meta = json_data.get("meta", {})
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO drawings (
                filename, file_path, version, layer_count, entity_count,
                layers, entity_counts
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            meta.get("filename"),
            meta.get("path"),
            meta.get("version"),
            meta.get("layer_count", 0),
            meta.get("entity_sampled", 0),
            Json(meta.get("layers", [])),
            Json(meta.get("entity_counts", {}))
        ))
        drawing_id = cur.fetchone()[0]
        conn.commit()
    
    return drawing_id


def prepare_entity_data(drawing_id: str, entity: Dict[str, Any]) -> tuple:
    """エンティティデータをDB挿入用に整形"""
    return (
        drawing_id,
        entity.get("type"),
        entity.get("layer"),
        entity.get("color"),
        entity.get("linetype"),
        entity.get("lineweight"),
        entity.get("bbox"),  # REAL[] として格納
        entity.get("start"),
        entity.get("end"),
        entity.get("center"),
        entity.get("radius"),
        entity.get("start_angle"),
        entity.get("end_angle"),
        Json(entity.get("points")) if entity.get("points") else None,
        entity.get("is_closed"),
        Json(entity.get("fit_points")) if entity.get("fit_points") else None,
        entity.get("major_axis"),
        entity.get("ratio"),
        entity.get("text"),
        entity.get("position"),
        entity.get("name"),
        entity.get("insert"),
        entity.get("xscale"),
        entity.get("yscale"),
        entity.get("rotation"),
        entity.get("measurement"),
        entity.get("solid_fill"),
        entity.get("pattern_name"),
    )


def insert_entities_batch(conn, drawing_id: str, entities: List[Dict[str, Any]]):
    """entitiesテーブルに複数レコードをバッチ挿入"""
    if not entities:
        return
    
    data = [prepare_entity_data(drawing_id, e) for e in entities]
    
    with conn.cursor() as cur:
        execute_batch(cur, """
            INSERT INTO entities (
                drawing_id, type, layer, color, linetype, lineweight, bbox,
                start, "end", center, radius, start_angle, end_angle,
                points, is_closed, fit_points, major_axis, ratio,
                text, position, name, insert, xscale, yscale, rotation,
                measurement, solid_fill, pattern_name
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """, data)
        conn.commit()


def import_json_file(conn, json_path: Path) -> Dict[str, Any]:
    """1つのJSONファイルをDBにインポート"""
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # drawingsテーブルに挿入
        drawing_id = insert_drawing(conn, data)
        
        # entitiesテーブルに一括挿入
        entities = data.get("entities", [])
        insert_entities_batch(conn, drawing_id, entities)
        
        return {
            "file": str(json_path),
            "ok": True,
            "drawing_id": drawing_id,
            "entity_count": len(entities)
        }
    except Exception as e:
        conn.rollback()
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
    ap = argparse.ArgumentParser(description="JSON → PostgreSQL/Supabase インポーター")
    ap.add_argument("input", help="JSONファイルまたはディレクトリ")
    ap.add_argument("--db", help="データベース接続文字列 (省略時は環境変数 DATABASE_URL を使用)")
    ap.add_argument("--dry-run", action="store_true", help="実際には挿入せず、処理内容のみ表示")
    args = ap.parse_args()
    
    src = Path(args.input)
    
    # データベース接続
    if args.dry_run:
        print("[DRY RUN MODE] データベースには接続しません")
        conn = None
    else:
        conn = get_db_connection(args.db)
        print(f"✓ データベースに接続しました")
    
    # JSONファイルを処理
    found = False
    results = []
    
    for json_path in iter_json_files(src):
        found = True
        
        if args.dry_run:
            print(f"[DRY RUN] {json_path}")
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  - Entities: {len(data.get('entities', []))}")
            results.append({"file": str(json_path), "ok": True, "dry_run": True})
        else:
            result = import_json_file(conn, json_path)
            results.append(result)
            status = "✓" if result.get("ok") else "✗"
            print(f"[{status}] {json_path}")
            if result.get("ok"):
                print(f"    Drawing ID: {result['drawing_id']}, Entities: {result['entity_count']}")
            else:
                print(f"    Error: {result.get('error')}")
    
    if not found:
        print("No JSON files found.", file=sys.stderr)
        sys.exit(1)
    
    # サマリー
    success_count = sum(1 for r in results if r.get("ok"))
    fail_count = len(results) - success_count
    
    print(f"\n{'='*50}")
    print(f"完了: {success_count}件成功, {fail_count}件失敗")
    print(f"{'='*50}")
    
    if conn:
        conn.close()


if __name__ == "__main__":
    main()
