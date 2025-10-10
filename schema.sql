-- ========================================
-- CAD Explorer Database Schema
-- for Supabase / PostgreSQL
-- ========================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector"; -- For embedding support (pgvector)

-- ========================================
-- drawings テーブル (1DXF = 1レコード)
-- ========================================
CREATE TABLE IF NOT EXISTS drawings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename TEXT NOT NULL,
    file_path TEXT,
    version TEXT,  -- AutoCAD version (e.g., "R2000")
    layer_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    layers JSONB,  -- レイヤー名のリスト
    entity_counts JSONB,  -- エンティティタイプごとのカウント
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_drawings_filename ON drawings(filename);
CREATE INDEX IF NOT EXISTS idx_drawings_created_at ON drawings(created_at DESC);

-- ========================================
-- entities テーブル (1図形 = 1レコード)
-- ========================================
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drawing_id UUID NOT NULL REFERENCES drawings(id) ON DELETE CASCADE,
    type TEXT NOT NULL,  -- LINE, CIRCLE, ARC, SPLINE, etc.
    layer TEXT,
    color INTEGER,
    linetype TEXT,
    lineweight INTEGER,
    
    -- 幾何データ（エンティティタイプによって異なる）
    bbox REAL[],  -- [minx, miny, maxx, maxy]
    
    -- LINE用
    start REAL[],  -- [x, y]
    "end" REAL[],  -- [x, y] (endはSQL予約語なのでクォート)
    
    -- CIRCLE, ARC用
    center REAL[],  -- [x, y]
    radius REAL,
    start_angle REAL,
    end_angle REAL,
    
    -- POLYLINE用
    points JSONB,  -- [[x1, y1], [x2, y2], ...]
    is_closed BOOLEAN,
    
    -- SPLINE用
    fit_points JSONB,  -- [[x1, y1], [x2, y2], ...]
    
    -- ELLIPSE用
    major_axis REAL[],  -- [x, y]
    ratio REAL,
    
    -- TEXT, MTEXT用
    text TEXT,
    position REAL[],  -- [x, y]
    
    -- INSERT (ブロック参照)用
    name TEXT,
    insert REAL[],  -- [x, y]
    xscale REAL,
    yscale REAL,
    rotation REAL,
    
    -- DIMENSION用
    measurement REAL,
    
    -- HATCH用
    solid_fill BOOLEAN,
    pattern_name TEXT,
    
    -- Embedding用 (後で追加可能)
    embedding vector(1536),  -- OpenAI embedding dimension
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_entities_drawing_id ON entities(drawing_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_layer ON entities(layer);
CREATE INDEX IF NOT EXISTS idx_entities_text ON entities USING GIN (to_tsvector('english', COALESCE(text, '')));

-- Embedding用のインデックス (pgvectorが有効な場合)
-- CREATE INDEX IF NOT EXISTS idx_entities_embedding ON entities USING ivfflat (embedding vector_cosine_ops);

-- ========================================
-- ビュー: 図面ごとの統計情報
-- ========================================
CREATE OR REPLACE VIEW drawing_stats AS
SELECT 
    d.id,
    d.filename,
    d.version,
    d.layer_count,
    d.entity_count,
    COUNT(e.id) as actual_entity_count,
    COUNT(DISTINCT e.type) as unique_entity_types,
    COUNT(DISTINCT e.layer) as unique_layers,
    d.created_at
FROM drawings d
LEFT JOIN entities e ON d.id = e.drawing_id
GROUP BY d.id, d.filename, d.version, d.layer_count, d.entity_count, d.created_at;

-- ========================================
-- ビュー: エンティティタイプ別の統計
-- ========================================
CREATE OR REPLACE VIEW entity_type_stats AS
SELECT 
    type,
    COUNT(*) as count,
    COUNT(DISTINCT drawing_id) as drawing_count,
    COUNT(DISTINCT layer) as layer_count
FROM entities
GROUP BY type
ORDER BY count DESC;

-- ========================================
-- 関数: 更新日時の自動更新
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_drawings_updated_at BEFORE UPDATE ON drawings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- コメント
-- ========================================
COMMENT ON TABLE drawings IS 'DXFファイルのメタデータ（1ファイル = 1レコード）';
COMMENT ON TABLE entities IS 'CADエンティティ（図形要素）のデータ（1図形 = 1レコード）';
COMMENT ON COLUMN entities.bbox IS 'バウンディングボックス [minx, miny, maxx, maxy]';
COMMENT ON COLUMN entities.embedding IS 'テキストまたは図形の埋め込みベクトル（検索用）';
