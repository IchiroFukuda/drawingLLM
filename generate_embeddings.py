#!/usr/bin/env python3

"""
埋め込みベクトル生成スクリプト
既存のentitiesとdrawingsからpayloadを作成し、OpenAI APIで埋め込みを生成
"""

import argparse
import os
import sys
from typing import List, Dict, Any, Optional
import time

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase is not installed. Please run: pip install supabase", file=sys.stderr)
    sys.exit(1)

try:
    import openai
except ImportError:
    print("ERROR: openai is not installed. Please run: pip install openai", file=sys.stderr)
    sys.exit(1)


def get_supabase_client() -> Client:
    """Supabaseクライアントを取得"""
    url = os.getenv("SUPABASE_URL") or "https://ozlbcjhfwzgwadumdwfz.supabase.co"
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    
    return create_client(url, key)


def setup_openai():
    """OpenAI APIキーを設定"""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        print("Example: export OPENAI_API_KEY='sk-...'", file=sys.stderr)
        sys.exit(1)
    
    openai.api_key = api_key


def create_entity_payload(entity: Dict[str, Any], filename: str) -> str:
    """エンティティからpayloadテキストを生成"""
    parts = []
    
    # エンティティタイプ
    if entity.get("type"):
        parts.append(f"type:{entity['type']}")
    
    # レイヤー
    if entity.get("layer"):
        parts.append(f"layer:{entity['layer']}")
    
    # 色
    if entity.get("color"):
        parts.append(f"color:{entity['color']}")
    
    # ファイル名
    parts.append(f"file:{filename}")
    
    # テキスト（最重要）
    if entity.get("text"):
        parts.append(f"text:{entity['text']}")
    
    # 線種
    if entity.get("linetype"):
        parts.append(f"linetype:{entity['linetype']}")
    
    # 名前（INSERTブロックなど）
    if entity.get("name"):
        parts.append(f"name:{entity['name']}")
    
    # 寸法値
    if entity.get("measurement"):
        parts.append(f"measurement:{entity['measurement']}")
    
    return " ".join(parts)


def create_drawing_payload(drawing: Dict[str, Any]) -> str:
    """図面からpayloadテキストを生成"""
    parts = []
    
    parts.append(f"filename:{drawing['filename']}")
    
    if drawing.get("version"):
        parts.append(f"version:{drawing['version']}")
    
    # レイヤー一覧
    if drawing.get("layers"):
        layers_str = ",".join(drawing['layers'])
        parts.append(f"layers:{layers_str}")
    
    # エンティティタイプの統計
    if drawing.get("entity_counts"):
        counts = []
        for etype, count in drawing['entity_counts'].items():
            counts.append(f"{etype}:{count}")
        parts.append(f"entities:{','.join(counts)}")
    
    return " ".join(parts)


def generate_embeddings_batch(texts: List[str], model: str = "text-embedding-3-large") -> List[List[float]]:
    """OpenAI APIで埋め込みをバッチ生成"""
    try:
        response = openai.embeddings.create(
            model=model,
            input=texts
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"  ⚠️  OpenAI API error: {e}", file=sys.stderr)
        raise


def process_entities(supabase: Client, batch_size: int = 50, limit: Optional[int] = None, skip_existing: bool = True):
    """エンティティの埋め込みを生成"""
    print("\n" + "="*60)
    print("📝 エンティティの埋め込みを生成")
    print("="*60)
    
    # 既存の埋め込みをチェック
    existing_entity_ids = set()
    if skip_existing:
        result = supabase.table("embeddings").select("entity_id").eq("kind", "entity").execute()
        existing_entity_ids = {row["entity_id"] for row in result.data if row.get("entity_id")}
        print(f"既存の埋め込み: {len(existing_entity_ids)}件（スキップします）")
    
    # エンティティを取得（drawingと結合）
    query = supabase.table("entities").select("*, drawings!inner(filename)").order("created_at")
    
    if limit:
        query = query.limit(limit)
    
    result = query.execute()
    entities = result.data
    
    print(f"対象エンティティ: {len(entities)}件")
    
    if not entities:
        print("処理対象がありません")
        return 0
    
    # バッチ処理
    total_processed = 0
    total_inserted = 0
    
    for i in range(0, len(entities), batch_size):
        batch = entities[i:i + batch_size]
        
        # 既存をスキップ
        if skip_existing:
            batch = [e for e in batch if e["id"] not in existing_entity_ids]
        
        if not batch:
            continue
        
        print(f"\n📦 バッチ {i//batch_size + 1}: {len(batch)}件を処理中...")
        
        # payloadを作成
        payloads = []
        metadata = []
        
        for entity in batch:
            filename = entity["drawings"]["filename"]
            payload = create_entity_payload(entity, filename)
            payloads.append(payload)
            metadata.append({
                "drawing_id": entity["drawing_id"],
                "entity_id": entity["id"],
                "payload": payload
            })
        
        # 埋め込み生成
        try:
            print("  → OpenAI APIで埋め込み生成中...")
            embeddings = generate_embeddings_batch(payloads)
            
            # DBに挿入
            print("  → Supabaseに保存中...")
            records = []
            for meta, embedding in zip(metadata, embeddings):
                records.append({
                    "drawing_id": meta["drawing_id"],
                    "entity_id": meta["entity_id"],
                    "kind": "entity",
                    "payload": meta["payload"],
                    "embedding": embedding
                })
            
            supabase.table("embeddings").insert(records).execute()
            
            total_processed += len(batch)
            total_inserted += len(records)
            
            print(f"  ✓ {len(records)}件の埋め込みを保存しました")
            print(f"  進捗: {total_processed}/{len(entities)}")
            
            # レート制限対策
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ✗ エラー: {e}", file=sys.stderr)
            continue
    
    print(f"\n✨ 完了: {total_inserted}件の埋め込みを生成しました")
    return total_inserted


def process_drawings(supabase: Client, skip_existing: bool = True):
    """図面の埋め込みを生成"""
    print("\n" + "="*60)
    print("📄 図面の埋め込みを生成")
    print("="*60)
    
    # 既存の埋め込みをチェック
    existing_drawing_ids = set()
    if skip_existing:
        result = supabase.table("embeddings").select("drawing_id").eq("kind", "drawing").execute()
        existing_drawing_ids = {row["drawing_id"] for row in result.data if row.get("drawing_id")}
        print(f"既存の埋め込み: {len(existing_drawing_ids)}件（スキップします）")
    
    # 図面を取得
    result = supabase.table("drawings").select("*").execute()
    drawings = result.data
    
    if skip_existing:
        drawings = [d for d in drawings if d["id"] not in existing_drawing_ids]
    
    print(f"対象図面: {len(drawings)}件")
    
    if not drawings:
        print("処理対象がありません")
        return 0
    
    # payloadを作成
    payloads = []
    metadata = []
    
    for drawing in drawings:
        payload = create_drawing_payload(drawing)
        payloads.append(payload)
        metadata.append({
            "drawing_id": drawing["id"],
            "payload": payload
        })
    
    # 埋め込み生成
    try:
        print("\n→ OpenAI APIで埋め込み生成中...")
        embeddings = generate_embeddings_batch(payloads)
        
        # DBに挿入
        print("→ Supabaseに保存中...")
        records = []
        for meta, embedding in zip(metadata, embeddings):
            records.append({
                "drawing_id": meta["drawing_id"],
                "entity_id": None,
                "kind": "drawing",
                "payload": meta["payload"],
                "embedding": embedding
            })
        
        supabase.table("embeddings").insert(records).execute()
        
        print(f"✓ {len(records)}件の埋め込みを保存しました")
        return len(records)
        
    except Exception as e:
        print(f"✗ エラー: {e}", file=sys.stderr)
        return 0


def main():
    ap = argparse.ArgumentParser(description="埋め込みベクトル生成スクリプト")
    ap.add_argument("--entities", action="store_true", help="エンティティの埋め込みを生成")
    ap.add_argument("--drawings", action="store_true", help="図面の埋め込みを生成")
    ap.add_argument("--all", action="store_true", help="すべての埋め込みを生成")
    ap.add_argument("--batch-size", type=int, default=50, help="バッチサイズ（デフォルト: 50）")
    ap.add_argument("--limit", type=int, help="処理する最大件数（テスト用）")
    ap.add_argument("--force", action="store_true", help="既存の埋め込みをスキップしない")
    args = ap.parse_args()
    
    # 環境変数チェック
    setup_openai()
    supabase = get_supabase_client()
    
    print("✓ Supabaseに接続しました")
    print("✓ OpenAI API キーを確認しました")
    
    skip_existing = not args.force
    
    total = 0
    
    if args.all or args.entities:
        total += process_entities(supabase, args.batch_size, args.limit, skip_existing)
    
    if args.all or args.drawings:
        total += process_drawings(supabase, skip_existing)
    
    if not (args.entities or args.drawings or args.all):
        print("\nUsage:")
        print("  --entities    エンティティの埋め込みを生成")
        print("  --drawings    図面の埋め込みを生成")
        print("  --all         すべての埋め込みを生成")
        print("\nExample:")
        print("  python generate_embeddings.py --all")
        sys.exit(1)
    
    print("\n" + "="*60)
    print(f"✨ 合計 {total}件の埋め込みを生成しました")
    print("="*60)


if __name__ == "__main__":
    main()
