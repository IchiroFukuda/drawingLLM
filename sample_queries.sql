-- ========================================
-- CAD Explorer - サンプルクエリ集
-- PostgreSQL/Supabase用
-- ========================================

-- ========================================
-- 基本的な検索
-- ========================================

-- 1. すべての図面を一覧表示
SELECT id, filename, version, layer_count, entity_count, created_at
FROM drawings
ORDER BY created_at DESC;

-- 2. 特定のファイル名で検索
SELECT * FROM drawings
WHERE filename LIKE '%test%';

-- 3. 図面内のすべてのエンティティを取得
SELECT e.id, e.type, e.layer, e.color, e.text
FROM entities e
WHERE e.drawing_id = 'YOUR_DRAWING_ID_HERE'
ORDER BY e.type, e.layer;

-- ========================================
-- エンティティタイプ別の検索
-- ========================================

-- 4. すべてのSPLINE（スプライン曲線）を検索
SELECT d.filename, e.layer, e.color, e.fit_points
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type = 'SPLINE';

-- 5. すべてのテキストエンティティを検索
SELECT d.filename, e.layer, e.text, e.position
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type IN ('TEXT', 'MTEXT')
  AND e.text IS NOT NULL;

-- 6. 特定の文字列を含むテキストを全文検索
SELECT d.filename, e.layer, e.text, e.position
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.text ILIKE '%キーワード%';

-- ========================================
-- レイヤー別の検索
-- ========================================

-- 7. 特定のレイヤーのエンティティを取得
SELECT d.filename, e.type, e.layer, e.text
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.layer = 'Plan 1';

-- 8. レイヤーごとのエンティティ数を集計
SELECT layer, COUNT(*) as entity_count, COUNT(DISTINCT drawing_id) as drawing_count
FROM entities
GROUP BY layer
ORDER BY entity_count DESC;

-- ========================================
-- 幾何的な検索
-- ========================================

-- 9. バウンディングボックスが存在するエンティティ
SELECT d.filename, e.type, e.layer, e.bbox
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.bbox IS NOT NULL
LIMIT 100;

-- 10. 特定の範囲内にあるエンティティ（空間検索）
-- bbox = [minx, miny, maxx, maxy]
SELECT d.filename, e.type, e.layer, e.bbox
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.bbox IS NOT NULL
  AND e.bbox[1] >= 0 AND e.bbox[2] >= 0  -- minx >= 0, miny >= 0
  AND e.bbox[3] <= 1000 AND e.bbox[4] <= 1000;  -- maxx <= 1000, maxy <= 1000

-- 11. すべてのLINE（線分）とその座標を取得
SELECT d.filename, e.layer, e.start, e."end"
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type = 'LINE'
  AND e.start IS NOT NULL
  AND e."end" IS NOT NULL;

-- 12. すべてのCIRCLE（円）とその半径を取得
SELECT d.filename, e.layer, e.center, e.radius
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type = 'CIRCLE'
  AND e.radius IS NOT NULL
ORDER BY e.radius DESC;

-- 13. 半径が特定の範囲の円を検索
SELECT d.filename, e.layer, e.center, e.radius
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type IN ('CIRCLE', 'ARC')
  AND e.radius BETWEEN 10 AND 100;

-- ========================================
-- 色・線種による検索
-- ========================================

-- 14. 特定の色のエンティティを検索
SELECT d.filename, e.type, e.layer, e.color
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.color = 250;

-- 15. 色ごとのエンティティ数を集計
SELECT color, COUNT(*) as count
FROM entities
WHERE color IS NOT NULL
GROUP BY color
ORDER BY count DESC;

-- ========================================
-- 統計・集計
-- ========================================

-- 16. 図面ごとのエンティティタイプの内訳
SELECT d.filename, e.type, COUNT(*) as count
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
GROUP BY d.filename, e.type
ORDER BY d.filename, count DESC;

-- 17. エンティティタイプ別の統計（ビュー使用）
SELECT * FROM entity_type_stats;

-- 18. 図面の統計情報（ビュー使用）
SELECT * FROM drawing_stats;

-- 19. 最もエンティティが多い図面トップ10
SELECT filename, entity_count, layer_count
FROM drawings
ORDER BY entity_count DESC
LIMIT 10;

-- 20. レイヤー数が多い図面
SELECT filename, layer_count, layers
FROM drawings
WHERE layer_count > 5
ORDER BY layer_count DESC;

-- ========================================
-- ポリライン・スプラインの検索
-- ========================================

-- 21. 閉じたポリラインのみ取得
SELECT d.filename, e.layer, e.points, e.is_closed
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type IN ('LWPOLYLINE', 'POLYLINE')
  AND e.is_closed = true;

-- 22. 頂点数が多いポリラインを検索
SELECT d.filename, e.layer, jsonb_array_length(e.points) as point_count
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type IN ('LWPOLYLINE', 'POLYLINE')
  AND e.points IS NOT NULL
ORDER BY point_count DESC
LIMIT 20;

-- ========================================
-- 複雑な検索
-- ========================================

-- 23. 図面ごとのレイヤー一覧と各レイヤーのエンティティ数
SELECT 
    d.filename,
    e.layer,
    COUNT(*) as entity_count,
    array_agg(DISTINCT e.type) as entity_types
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
GROUP BY d.filename, e.layer
ORDER BY d.filename, entity_count DESC;

-- 24. 図面間での共通レイヤーを検索
SELECT layer, COUNT(DISTINCT drawing_id) as drawing_count
FROM entities
GROUP BY layer
HAVING COUNT(DISTINCT drawing_id) > 1
ORDER BY drawing_count DESC;

-- 25. テキストを含むエンティティの分布
SELECT 
    d.filename,
    COUNT(*) FILTER (WHERE e.text IS NOT NULL) as text_entity_count,
    COUNT(*) as total_entity_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE e.text IS NOT NULL) / COUNT(*), 2) as text_percentage
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
GROUP BY d.filename
ORDER BY text_entity_count DESC;

-- ========================================
-- データクリーンアップ
-- ========================================

-- 26. 特定の図面を削除（CASCADE設定により関連entitiesも自動削除）
-- DELETE FROM drawings WHERE filename = 'test.dxf';

-- 27. すべてのエンティティを削除（図面メタデータは保持）
-- DELETE FROM entities;

-- 28. すべてのデータを削除
-- TRUNCATE TABLE entities, drawings RESTART IDENTITY CASCADE;

-- ========================================
-- パフォーマンス確認
-- ========================================

-- 29. テーブルサイズの確認
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 30. インデックスの使用状況
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
