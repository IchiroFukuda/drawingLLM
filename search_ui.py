#!/usr/bin/env python3
"""
Drawing Search UI - Streamlit アプリ
自然言語でDXF図面を検索
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import openai
from supabase import create_client
import numpy as np
import json
from typing import List, Dict, Any

# ページ設定
st.set_page_config(
    page_title="Drawing Search - 図面検索",
    page_icon="🔍",
    layout="wide"
)

# 環境変数
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ozlbcjhfwzgwadumdwfz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 初期化
if not SUPABASE_KEY or not OPENAI_API_KEY:
    st.error("環境変数が設定されていません。SUPABASE_SERVICE_ROLE_KEY と OPENAI_API_KEY を設定してください。")
    st.stop()

openai.api_key = OPENAI_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# スタイル
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .search-box {
        font-size: 1.2rem;
        padding: 1rem;
    }
    .result-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .material-badge {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.3rem 0.8rem;
        border-radius: 12px;
        font-size: 0.9rem;
        margin-right: 0.5rem;
        display: inline-block;
    }
    .thread-badge {
        background: #f3e5f5;
        color: #7b1fa2;
        padding: 0.3rem 0.8rem;
        border-radius: 12px;
        font-size: 0.9rem;
        margin-right: 0.5rem;
        display: inline-block;
    }
    .tolerance-badge {
        background: #fff3e0;
        color: #e65100;
        padding: 0.3rem 0.8rem;
        border-radius: 12px;
        font-size: 0.9rem;
        margin-right: 0.5rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

def embed_query(query: str) -> List[float]:
    """クエリをベクトル化"""
    response = openai.embeddings.create(
        model="text-embedding-3-large",
        input=query
    )
    return response.data[0].embedding

def search_drawings(query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """ベクトル検索を実行"""
    # 全埋め込みを取得して類似度計算（シンプル版）
    all_embeddings = supabase.table("embeddings").select(
        "id, drawing_id, entity_id, kind, payload, embedding"
    ).execute()
    
    results = []
    query_vec = np.array(query_embedding, dtype=np.float64)
    
    for item in all_embeddings.data:
        # embeddingがリストか文字列かをチェック
        emb = item["embedding"]
        if isinstance(emb, str):
            import json
            emb = json.loads(emb)
        
        emb_vec = np.array(emb, dtype=np.float64)
        
        # ベクトルの長さが一致するか確認
        if len(query_vec) != len(emb_vec):
            continue
        
        # コサイン類似度
        similarity = np.dot(query_vec, emb_vec) / (
            np.linalg.norm(query_vec) * np.linalg.norm(emb_vec)
        )
        
        results.append({
            "drawing_id": item["drawing_id"],
            "entity_id": item["entity_id"],
            "kind": item["kind"],
            "payload": item["payload"],
            "score": float(similarity),
            "embedding_id": item["id"]
        })
    
    # スコア順にソート
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # 重複を除去（同じdrawing_idは最高スコアのものだけ残す）
    seen_drawings = set()
    unique_results = []
    
    for r in results:
        drawing_id = r["drawing_id"]
        if drawing_id not in seen_drawings:
            seen_drawings.add(drawing_id)
            unique_results.append(r)
            if len(unique_results) >= limit:
                break
    
    return unique_results

def get_drawing_details(drawing_ids: List[str]) -> Dict[str, Any]:
    """図面の詳細を取得"""
    if not drawing_ids:
        return {}
    
    result = supabase.table("drawings").select("*").in_("id", drawing_ids).execute()
    return {item["id"]: item for item in result.data}

def get_entity_details(entity_ids: List[str]) -> Dict[str, Any]:
    """エンティティの詳細を取得"""
    if not entity_ids:
        return {}
    
    result = supabase.table("entities").select("*").in_("id", entity_ids).execute()
    return {item["id"]: item for item in result.data}

def render_dxf_viewer(entities: List[Dict], height: int = 400):
    """DXFビューアーをレンダリング"""
    # エンティティデータをJSON文字列化
    entities_json = json.dumps(entities)
    
    html_code = f"""
    <div style="width:100%; height:{height}px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
        <div id="canvas-container" style="width:100%; height:100%;"></div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        let scene, camera, renderer, dxfGroup;
        
        function init() {{
            const container = document.getElementById('canvas-container');
            
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf8f9fa);
            
            camera = new THREE.OrthographicCamera(
                -100, 100, 100, -100, 0.1, 1000
            );
            camera.position.set(0, 0, 100);
            camera.lookAt(0, 0, 0);
            
            renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(container.clientWidth, container.clientHeight);
            container.appendChild(renderer.domElement);
            
            const gridHelper = new THREE.GridHelper(200, 20, 0xcccccc, 0xe0e0e0);
            gridHelper.rotation.x = Math.PI / 2;
            scene.add(gridHelper);
            
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
            scene.add(ambientLight);
            
            dxfGroup = new THREE.Group();
            scene.add(dxfGroup);
            
            // エンティティを描画
            const entities = {entities_json};
            renderEntities(entities);
            
            renderer.render(scene, camera);
        }}
        
        function renderEntities(entities) {{
            entities.forEach(entity => {{
                try {{
                    if (entity.type === 'CIRCLE' && entity.center && entity.radius) {{
                        const curve = new THREE.EllipseCurve(
                            entity.center[0], entity.center[1],
                            entity.radius, entity.radius,
                            0, 2 * Math.PI, false, 0
                        );
                        const points = curve.getPoints(50).map(p => 
                            new THREE.Vector3(p.x, p.y, 0)
                        );
                        const geometry = new THREE.BufferGeometry().setFromPoints(points);
                        const material = new THREE.LineBasicMaterial({{ color: 0x2196f3, linewidth: 2 }});
                        const circle = new THREE.Line(geometry, material);
                        dxfGroup.add(circle);
                    }} else if (entity.type === 'LINE' && entity.start && entity.end) {{
                        const points = [
                            new THREE.Vector3(entity.start[0], entity.start[1], 0),
                            new THREE.Vector3(entity.end[0], entity.end[1], 0)
                        ];
                        const geometry = new THREE.BufferGeometry().setFromPoints(points);
                        const material = new THREE.LineBasicMaterial({{ color: 0x000000, linewidth: 2 }});
                        const line = new THREE.Line(geometry, material);
                        dxfGroup.add(line);
                    }} else if (entity.type === 'LWPOLYLINE' && entity.points) {{
                        const points = entity.points.map(p => 
                            new THREE.Vector3(p[0], p[1], 0)
                        );
                        if (entity.is_closed && points.length > 0) {{
                            points.push(points[0]);
                        }}
                        const geometry = new THREE.BufferGeometry().setFromPoints(points);
                        const material = new THREE.LineBasicMaterial({{ color: 0x4caf50, linewidth: 2 }});
                        const polyline = new THREE.Line(geometry, material);
                        dxfGroup.add(polyline);
                    }}
                }} catch (e) {{
                    console.error('描画エラー:', e);
                }}
            }});
        }}
        
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', init);
        }} else {{
            init();
        }}
    </script>
    """
    
    components.html(html_code, height=height)

def extract_info_from_payload(payload: str) -> Dict[str, str]:
    """payloadから情報を抽出"""
    info = {
        "material": None,
        "tolerance": None,
        "thread": None,
        "finish": None,
        "type": None
    }
    
    parts = payload.split()
    for part in parts:
        if "material:" in part.lower():
            idx = parts.index(part)
            if idx + 1 < len(parts):
                info["material"] = parts[idx + 1]
        elif "tol:" in part.lower():
            idx = parts.index(part)
            if idx + 1 < len(parts):
                info["tolerance"] = parts[idx + 1]
        elif "thread:" in part.lower():
            idx = parts.index(part)
            if idx + 1 < len(parts):
                info["thread"] = parts[idx + 1]
        elif "finish:" in part.lower():
            idx = parts.index(part)
            if idx + 1 < len(parts):
                info["finish"] = parts[idx + 1]
        elif "type:" in part.lower():
            idx = parts.index(part)
            if idx + 1 < len(parts):
                info["type"] = parts[idx + 1]
    
    return info

# メインUI
st.markdown('<h1 class="main-header">🔍 Drawing Search</h1>', unsafe_allow_html=True)
st.markdown("### 自然言語でDXF図面を検索")

# 検索バー
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input(
        "検索キーワード",
        placeholder="例: ステンレス製のブラケット、M8のねじ穴、公差±0.01",
        key="search_query",
        label_visibility="collapsed"
    )
with col2:
    search_button = st.button("🔍 検索", type="primary", use_container_width=True)

# サンプルクエリ
st.markdown("**サンプルクエリ:**")
col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1:
    if st.button("ステンレス製の部品"):
        query = "ステンレス製の部品"
        search_button = True
with col_s2:
    if st.button("スリーブ"):
        query = "スリーブ"
        search_button = True
with col_s3:
    if st.button("M12のねじ"):
        query = "M12のねじ"
        search_button = True
with col_s4:
    if st.button("ブラケット"):
        query = "ブラケット"
        search_button = True

st.markdown("---")

# 検索実行
if search_button and query:
    with st.spinner("🔍 検索中..."):
        # クエリをベクトル化
        query_vec = embed_query(query)
        
        # ベクトル検索
        results = search_drawings(query_vec, limit=10)
        
        if not results:
            st.warning("検索結果が見つかりませんでした。")
        else:
            st.success(f"✨ {len(results)}件の結果が見つかりました")
            
            # 図面IDとエンティティIDを収集
            drawing_ids = list(set([r["drawing_id"] for r in results]))
            entity_ids = [r["entity_id"] for r in results if r["entity_id"]]
            
            # 詳細情報を取得
            drawings_map = get_drawing_details(drawing_ids)
            entities_map = get_entity_details(entity_ids)
            
            # 結果を表示
            for idx, result in enumerate(results, 1):
                drawing = drawings_map.get(result["drawing_id"], {})
                entity = entities_map.get(result["entity_id"]) if result["entity_id"] else None
                
                # 情報抽出
                info = extract_info_from_payload(result["payload"])
                
                # カード表示
                with st.container():
                    col_main, col_score = st.columns([5, 1])
                    
                    with col_main:
                        st.markdown(f"### {idx}. {drawing.get('filename', 'Unknown')}")
                        
                        # バッジ表示
                        badges = []
                        if info["material"]:
                            badges.append(f'<span class="material-badge">🔩 {info["material"]}</span>')
                        if info["thread"]:
                            badges.append(f'<span class="thread-badge">🔧 {info["thread"]}</span>')
                        if info["tolerance"]:
                            badges.append(f'<span class="tolerance-badge">📏 {info["tolerance"]}</span>')
                        
                        if badges:
                            st.markdown(" ".join(badges), unsafe_allow_html=True)
                        
                        # 詳細情報
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.markdown(f"**種類**: {result['kind']}")
                            if entity:
                                st.markdown(f"**エンティティタイプ**: {entity.get('type', 'N/A')}")
                                st.markdown(f"**レイヤー**: {entity.get('layer', 'N/A')}")
                        with col_info2:
                            st.markdown(f"**エンティティ数**: {drawing.get('entity_count', 0)}")
                            st.markdown(f"**レイヤー数**: {drawing.get('layer_count', 0)}")
                        
                        # Payload表示
                        with st.expander("詳細情報を表示"):
                            st.text(result["payload"])
                            if entity and entity.get("text"):
                                st.markdown(f"**テキスト**: {entity['text']}")
                    
                    with col_score:
                        score_pct = result["score"] * 100
                        st.metric("スコア", f"{score_pct:.1f}%")
                
                # DXFプレビューを表示
                with st.expander("🖼️ 図面プレビューを表示", expanded=False):
                    # この図面のすべてのエンティティを取得
                    drawing_entities_result = supabase.table("entities").select("*").eq(
                        "drawing_id", result["drawing_id"]
                    ).execute()
                    
                    if drawing_entities_result.data:
                        render_dxf_viewer(drawing_entities_result.data, height=400)
                    else:
                        st.info("プレビュー情報がありません")
                
                st.markdown("---")

elif not query and search_button:
    st.warning("検索キーワードを入力してください。")

# フッター
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>Drawing Analysis API powered by OpenAI + Supabase</p>
    <p>🔗 <a href='http://localhost:8000/docs' target='_blank'>API Documentation</a></p>
</div>
""", unsafe_allow_html=True)
