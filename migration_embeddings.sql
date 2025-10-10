-- ========================================
-- 意味検索のためのマイグレーション
-- pgvector + embeddings テーブル
-- ========================================

-- pgvector拡張を有効化（一度だけ）
CREATE EXTENSION IF NOT EXISTS vector;

-- 埋め込みテーブル
CREATE TABLE IF NOT EXISTS embeddings (
  id BIGSERIAL PRIMARY KEY,
  drawing_id UUID REFERENCES drawings(id) ON DELETE CASCADE,
  entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                         -- 'entity' | 'drawing'
  payload TEXT NOT NULL,                      -- 埋め込み対象のテキスト
  embedding vector(3072) NOT NULL,            -- text-embedding-3-large
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス（検索高速化）
-- 注意: HNSWインデックスは大量データがある場合のみ作成推奨
-- 少量データの場合は不要（スキャンの方が速い）
-- CREATE INDEX IF NOT EXISTS idx_embeddings_vector 
--   ON embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_embeddings_drawing_id ON embeddings (drawing_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_entity_id ON embeddings (entity_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_kind ON embeddings (kind);

-- コメント
COMMENT ON TABLE embeddings IS 'エンティティと図面の埋め込みベクトル（意味検索用）';
COMMENT ON COLUMN embeddings.kind IS 'エンティティまたは図面全体のフラグ';
COMMENT ON COLUMN embeddings.payload IS '埋め込み生成時に使用したテキスト（検索結果表示用）';
COMMENT ON COLUMN embeddings.embedding IS 'text-embedding-3-large による3072次元ベクトル';

-- 統計ビュー
CREATE OR REPLACE VIEW embedding_stats AS
SELECT 
    kind,
    COUNT(*) as count,
    COUNT(DISTINCT drawing_id) as unique_drawings,
    COUNT(DISTINCT entity_id) as unique_entities
FROM embeddings
GROUP BY kind;
