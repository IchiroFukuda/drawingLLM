#!/usr/bin/env python3

"""
CAD Explorer - 意味検索API
FastAPI + pgvector でベクトル検索を提供
"""

import os
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase is not installed. Please run: pip install supabase")
    exit(1)

# FastAPIアプリケーション
app = FastAPI(
    title="CAD Explorer API",
    description="DXF図面の意味検索API",
    version="1.0.0"
)

# CORS設定（開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 環境変数
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ozlbcjhfwzgwadumdwfz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

openai.api_key = OPENAI_API_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# レスポンスモデル
class SearchResult(BaseModel):
    drawing_id: str
    entity_id: Optional[str]
    kind: str
    payload: str
    score: float
    filename: Optional[str] = None
    entity_type: Optional[str] = None
    layer: Optional[str] = None
    text: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    count: int


class HealthResponse(BaseModel):
    status: str
    embeddings_count: int
    drawings_count: int
    entities_count: int


# ヘルパー関数
def embed_query(query: str) -> List[float]:
    """クエリをベクトルに変換"""
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-large",
            input=query
        )
        return response.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")


def vector_search(embedding: List[float], limit: int = 20) -> List[dict]:
    """ベクトル検索を実行（RPC使用）"""
    try:
        # Supabase RPCで検索
        result = supabase.rpc(
            'search_embeddings',
            {
                'query_embedding': embedding,
                'match_count': limit
            }
        ).execute()
        
        return result.data
    except Exception as e:
        # RPCが使えない場合は直接SQLで検索
        # 注意: この方法はpython-supabaseの制限により完全には動作しない可能性があります
        raise HTTPException(
            status_code=500, 
            detail=f"Vector search failed. Please create the RPC function: {str(e)}"
        )


def get_entity_details(entity_ids: List[str]) -> dict:
    """エンティティの詳細情報を取得"""
    if not entity_ids:
        return {}
    
    result = supabase.table("entities").select(
        "id, type, layer, text, drawing_id"
    ).in_("id", entity_ids).execute()
    
    return {item["id"]: item for item in result.data}


def get_drawing_details(drawing_ids: List[str]) -> dict:
    """図面の詳細情報を取得"""
    if not drawing_ids:
        return {}
    
    result = supabase.table("drawings").select(
        "id, filename"
    ).in_("id", drawing_ids).execute()
    
    return {item["id"]: item for item in result.data}


# エンドポイント
@app.get("/", response_model=dict)
async def root():
    """ルートエンドポイント"""
    return {
        "message": "CAD Explorer API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/search?q=検索クエリ",
            "health": "/health"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """ヘルスチェック"""
    try:
        # 統計情報を取得
        embeddings = supabase.table("embeddings").select("id", count="exact").execute()
        drawings = supabase.table("drawings").select("id", count="exact").execute()
        entities = supabase.table("entities").select("id", count="exact").execute()
        
        return HealthResponse(
            status="healthy",
            embeddings_count=embeddings.count or 0,
            drawings_count=drawings.count or 0,
            entities_count=entities.count or 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="検索クエリ（例: φ8 ステンレス スリーブ）"),
    limit: int = Query(20, ge=1, le=100, description="結果の最大件数")
):
    """
    意味検索エンドポイント
    
    自然言語のクエリでCAD図面を検索します。
    
    例:
    - /search?q=ステンレス
    - /search?q=Plan 1 レイヤー
    - /search?q=円形の図形
    """
    try:
        # 1. クエリをベクトル化
        query_embedding = embed_query(q)
        
        # 2. ベクトル検索を実行（手動でSQLクエリ）
        # Supabaseのpython clientではvector検索が制限されているため、
        # 一時的に全件取得してPython側で計算
        
        # より良い方法: PostgreSQL関数を使用
        # まず、embeddings から全データを取得（少量なので許容）
        all_embeddings = supabase.table("embeddings").select(
            "id, drawing_id, entity_id, kind, payload, embedding"
        ).execute()
        
        # コサイン類似度を計算
        import numpy as np
        
        results = []
        query_vec = np.array(query_embedding)
        
        for item in all_embeddings.data:
            emb_vec = np.array(item["embedding"])
            # コサイン類似度: 1 - コサイン距離
            similarity = np.dot(query_vec, emb_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(emb_vec)
            )
            
            results.append({
                "drawing_id": item["drawing_id"],
                "entity_id": item["entity_id"],
                "kind": item["kind"],
                "payload": item["payload"],
                "score": float(similarity)
            })
        
        # スコア順にソート
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]
        
        # 3. エンティティと図面の詳細を取得
        entity_ids = [r["entity_id"] for r in results if r["entity_id"]]
        drawing_ids = list(set([r["drawing_id"] for r in results]))
        
        entities_map = get_entity_details(entity_ids)
        drawings_map = get_drawing_details(drawing_ids)
        
        # 4. 結果を結合
        enriched_results = []
        for r in results:
            result = SearchResult(
                drawing_id=r["drawing_id"],
                entity_id=r["entity_id"],
                kind=r["kind"],
                payload=r["payload"],
                score=r["score"]
            )
            
            # 図面情報を追加
            if r["drawing_id"] in drawings_map:
                result.filename = drawings_map[r["drawing_id"]]["filename"]
            
            # エンティティ情報を追加
            if r["entity_id"] and r["entity_id"] in entities_map:
                entity = entities_map[r["entity_id"]]
                result.entity_type = entity.get("type")
                result.layer = entity.get("layer")
                result.text = entity.get("text")
            
            enriched_results.append(result)
        
        return SearchResponse(
            query=q,
            results=enriched_results,
            count=len(enriched_results)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting CAD Explorer API...")
    print(f"   Supabase: {SUPABASE_URL}")
    print(f"   OpenAI: {'✓ Configured' if OPENAI_API_KEY else '✗ Not configured'}")
    print("\n📍 API Documentation: http://localhost:8000/docs")
    print("🔍 Search example: http://localhost:8000/search?q=スリーブ\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
