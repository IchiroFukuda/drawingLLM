# CAD Explorer

DXFファイルをJSON経由でPostgreSQL/Supabaseに格納し、SQL検索・集計・Embedding検索を可能にするシステム

## 🎯 目的

- DXFファイルを解析してJSON形式で出力
- PostgreSQL/Supabaseに構造化データとして格納
- SQL検索・フィルタリング・集計を実現
- 将来的にEmbedding検索（類似図面検索）に対応

## 📁 プロジェクト構成

```
cad-explorer/
├── dxf_to_json.py         # DXF → JSON変換スクリプト
├── json_to_db.py          # JSON → PostgreSQL インポートスクリプト
├── test_connection.py     # DB接続テストスクリプト
├── schema.sql             # データベーススキーマ定義（DDL）
├── sample_queries.sql     # サンプルクエリ集（30種類）
├── requirements.txt       # Python依存パッケージ
└── README.md              # このファイル
```

## 🗄️ データベース設計

### `drawings` テーブル
1つのDXFファイル = 1レコード

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | 主キー |
| filename | TEXT | ファイル名 |
| version | TEXT | AutoCADバージョン (例: R2000) |
| layer_count | INTEGER | レイヤー数 |
| entity_count | INTEGER | エンティティ数 |
| layers | JSONB | レイヤー名のリスト |
| entity_counts | JSONB | エンティティタイプごとのカウント |
| created_at | TIMESTAMP | 作成日時 |

### `entities` テーブル
1つの図形要素 = 1レコード

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | 主キー |
| drawing_id | UUID | 所属する図面 (外部キー) |
| type | TEXT | エンティティタイプ (LINE, CIRCLE等) |
| layer | TEXT | レイヤー名 |
| color | INTEGER | 色番号 |
| bbox | REAL[] | バウンディングボックス [minx, miny, maxx, maxy] |
| start, end | REAL[] | 線分の始点・終点 |
| center, radius | REAL[], REAL | 円・円弧の中心・半径 |
| points | JSONB | ポリラインの頂点配列 |
| text | TEXT | テキスト内容 |
| embedding | VECTOR(1536) | 埋め込みベクトル（将来使用） |

## 🚀 セットアップ

### 1. 依存パッケージのインストール

```bash
# 仮想環境の作成と有効化
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# パッケージのインストール
pip install -r requirements.txt
```

### 2. Supabaseプロジェクトの準備

#### Supabaseプロジェクトを作成
1. [Supabase](https://supabase.com/) でプロジェクトを作成
2. Settings → Database → Connection string (URI) をコピー

#### 環境変数の設定

```bash
export DATABASE_URL='postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres'
```

### 3. データベーススキーマの作成

```bash
# schema.sqlを実行してテーブルを作成
psql $DATABASE_URL -f schema.sql

# または
cat schema.sql | psql $DATABASE_URL
```

### 4. 接続テスト

```bash
python test_connection.py
```

正常に接続できれば、以下のような出力が表示されます：

```
====================================
環境変数の確認
====================================
✓ DATABASE_URL: postgresql://postgres:***@...

====================================
データベース接続テスト
====================================
✓ データベースに接続成功
✓ PostgreSQL バージョン: PostgreSQL 15.x

====================================
テーブルの確認
====================================
✓ drawings テーブルが存在します
✓ entities テーブルが存在します
```

## 📊 使用方法

### ステップ1: DXFファイルをJSONに変換

```bash
# 単一ファイルを変換
python dxf_to_json.py input.dxf -o out_json --index

# フォルダ内のすべてのDXFを一括変換
python dxf_to_json.py dxf_folder/ -o out_json --index
```

生成されるファイル：
- `out_json/input.json` - DXFデータのJSON表現
- `out_json/index.jsonl` - 処理結果のサマリー

### ステップ2: JSONをデータベースにインポート

```bash
# 環境変数が設定済みの場合
python json_to_db.py out_json/

# または接続文字列を直接指定
python json_to_db.py out_json/ --db "postgresql://..."

# ドライラン（実際には挿入しない）
python json_to_db.py out_json/ --dry-run
```

### ステップ3: SQLで検索・分析

```bash
# psqlで接続
psql $DATABASE_URL
```

```sql
-- すべての図面を一覧表示
SELECT id, filename, entity_count, layer_count, created_at
FROM drawings
ORDER BY created_at DESC;

-- テキストを含むエンティティを検索
SELECT d.filename, e.layer, e.text, e.position
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type IN ('TEXT', 'MTEXT')
  AND e.text IS NOT NULL;

-- レイヤーごとのエンティティ数
SELECT layer, COUNT(*) as count
FROM entities
GROUP BY layer
ORDER BY count DESC;
```

詳細なクエリ例は `sample_queries.sql` を参照してください（30種類のクエリを収録）。

## 📝 サンプルクエリ

`sample_queries.sql` には以下のようなクエリが含まれています：

1. **基本検索** - ファイル名、エンティティタイプ、レイヤーで検索
2. **幾何検索** - バウンディングボックス、半径、座標範囲で検索
3. **テキスト検索** - 全文検索、パターンマッチング
4. **集計・統計** - エンティティタイプ別カウント、レイヤー分布
5. **複雑な検索** - 図面間の共通レイヤー、テキスト分布分析

実行例：

```bash
psql $DATABASE_URL -f sample_queries.sql
```

## 🔍 検索例

### 特定の文字列を含む図面を検索

```sql
SELECT d.filename, e.text, e.layer
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.text ILIKE '%タイトル%';
```

### 円の半径が100以上のエンティティを検索

```sql
SELECT d.filename, e.layer, e.center, e.radius
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.type = 'CIRCLE'
  AND e.radius >= 100
ORDER BY e.radius DESC;
```

### エンティティ数が最も多い図面トップ5

```sql
SELECT filename, entity_count, layer_count
FROM drawings
ORDER BY entity_count DESC
LIMIT 5;
```

## 🎨 将来の拡張

### Embedding検索の実装

```python
# OpenAI APIでテキストをEmbedding化
import openai
embedding = openai.Embedding.create(input="図面のテキスト", model="text-embedding-ada-002")

# PostgreSQLに保存
UPDATE entities SET embedding = %s WHERE id = %s
```

```sql
-- 類似検索クエリ
SELECT d.filename, e.text, e.embedding <=> %s AS distance
FROM entities e
JOIN drawings d ON e.drawing_id = d.id
WHERE e.embedding IS NOT NULL
ORDER BY distance
LIMIT 10;
```

## 🛠️ トラブルシューティング

### `ezdxf` のインストールエラー

```bash
pip install --upgrade pip
pip install ezdxf
```

### データベース接続エラー

1. DATABASE_URLが正しく設定されているか確認
2. Supabaseプロジェクトが起動しているか確認
3. ファイアウォール設定を確認

```bash
python test_connection.py
```

### pgvector拡張機能が見つからない

Supabaseでは標準で有効化されていますが、自前のPostgreSQLの場合：

```sql
CREATE EXTENSION vector;
```

## 📚 参考

- [ezdxf Documentation](https://ezdxf.readthedocs.io/)
- [Supabase Documentation](https://supabase.com/docs)
- [pgvector](https://github.com/pgvector/pgvector)

## 📄 ライセンス

MIT License

## 🤝 コントリビューション

Issue・PRを歓迎します！
