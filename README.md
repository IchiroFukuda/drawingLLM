# Drawing Analysis API (drawingLLM)

包括的な図面解析REST API - DXF/DWG/PDF/画像の自動解析、BOM生成、寸法抽出、LLM要約

## 🎯 プロジェクト概要

技術図面（DXF/DWG/PDF/画像）を解析し、構造化データとして抽出・要約する統合APIシステム。

### 主要機能

- ✅ **DXF解析エンジン** - 寸法、BOM、材質、注記の自動抽出
- ✅ **REST API** - FastAPI + OpenAPI/Swagger文書
- ✅ **LLM要約** - GPT-4による自然言語での図面要約
- ✅ **ベクトル検索** - Supabase + pgvectorで類似図面検索
- ✅ **構造化データベース** - PostgreSQL/Supabaseに格納
- 🚧 **PDF解析** - ベクター/ラスター対応（準備中）
- 🚧 **画像解析** - OCR + Vision Transformer（準備中）

---

## 🚀 クイックスタート

### 1. セットアップ

```bash
# リポジトリをクローン
git clone https://github.com/IchiroFukuda/drawingLLM.git
cd drawingLLM

# 仮想環境を作成
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 2. 環境変数を設定

```bash
# OpenAI APIキー（LLM要約用）
export OPENAI_API_KEY='sk-...'

# Supabase（オプション、ベクトル検索用）
export SUPABASE_URL='https://your-project.supabase.co'
export SUPABASE_SERVICE_ROLE_KEY='eyJ...'
```

### 3. APIサーバーを起動

```bash
python3 drawing_analysis_api.py
```

APIが起動したら、ブラウザで以下にアクセス：
- **Swagger UI**: http://localhost:8000/docs
- **ヘルスチェック**: http://localhost:8000/api/v1/health

---

## 📡 API使用方法

### ヘルスチェック

```bash
curl http://localhost:8000/api/v1/health
```

**レスポンス:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "features": {
    "dxf_analysis": true,
    "llm_summary": true,
    "bom_extraction": true,
    "dimension_extraction": true
  }
}
```

### 図面ファイルを解析

```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "X-API-Key: dev-key-12345" \
  -F "file=@drawing.dxf" \
  -F "generate_summary=true"
```

**レスポンス:**
```json
{
  "job_id": "c9ca1459-8154-4a4f-bc2d-52d0933daa86",
  "filename": "drawing.dxf",
  "status": "completed",
  "dimensions": {
    "count": 15,
    "items": [...]
  },
  "entities": {
    "count": 248,
    "summary": {
      "LINE": 150,
      "CIRCLE": 45,
      "ARC": 30,
      "TEXT": 23
    }
  },
  "summary": {
    "natural_language_summary": "SUS304製の取付ブラケットの図面で、全体寸法は150x75x50mm。4つのM6タップ穴があります。",
    "key_dimensions": [...],
    "materials": ["SUS304"],
    "has_bom": true
  }
}
```

### 対応フォーマット

```bash
curl http://localhost:8000/api/v1/formats
```

| フォーマット | 拡張子 | ステータス | 機能 |
|------------|--------|----------|------|
| DXF | .dxf | ✅ 完全対応 | 寸法、BOM、材質、注記、エンティティ |
| DWG | .dwg | 🚧 準備中 | - |
| PDF | .pdf | 🚧 準備中 | - |
| 画像 | .png, .jpg, .tiff | 🚧 準備中 | - |

---

## 📁 プロジェクト構成

```
drawingLLM/
├── drawing_analysis_api.py    # 統合REST APIサーバー
├── enhanced_dxf_parser.py     # 拡張DXF解析エンジン
├── dxf_to_json.py              # 基本DXF→JSON変換
├── generate_embeddings.py      # ベクトル埋め込み生成
├── import_to_supabase.py       # Supabaseデータ投入
├── schema.sql                  # データベーススキーマ
├── migration_embeddings.sql    # ベクトル検索用マイグレーション
├── sample_queries.sql          # SQLクエリサンプル（30種類）
├── requirements.txt            # Python依存パッケージ
└── README.md                   # このファイル
```

---

## 🗄️ データベース設計

### `drawings` テーブル
1つのDXFファイル = 1レコード

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | 主キー |
| filename | TEXT | ファイル名 |
| version | TEXT | AutoCADバージョン |
| layer_count | INTEGER | レイヤー数 |
| entity_count | INTEGER | エンティティ数 |
| layers | JSONB | レイヤー名のリスト |

### `entities` テーブル
1つの図形要素 = 1レコード

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | 主キー |
| drawing_id | UUID | 所属する図面 |
| type | TEXT | エンティティタイプ |
| layer | TEXT | レイヤー名 |
| text | TEXT | テキスト内容 |
| bbox | REAL[] | バウンディングボックス |

### `embeddings` テーブル
ベクトル検索用

| カラム | 型 | 説明 |
|--------|-----|------|
| id | BIGSERIAL | 主キー |
| drawing_id | UUID | 図面ID |
| entity_id | UUID | エンティティID |
| payload | TEXT | 埋め込み対象テキスト |
| embedding | VECTOR(3072) | 埋め込みベクトル |

---

## 🔍 ベクトル検索（類似図面検索）

### 1. データベースをセットアップ

```bash
# Supabaseでスキーマを作成
psql $DATABASE_URL -f schema.sql
psql $DATABASE_URL -f migration_embeddings.sql
```

### 2. 埋め込みベクトルを生成

```bash
# DXFファイルをSupabaseに投入
python3 import_to_supabase.py out_json/

# 埋め込みを生成
export OPENAI_API_KEY='sk-...'
python3 generate_embeddings.py --all
```

### 3. 意味検索を実行

```python
import openai
from supabase import create_client

# クエリをベクトル化
query = "ステンレス製のブラケット"
embedding = openai.embeddings.create(
    model="text-embedding-3-large",
    input=query
).data[0].embedding

# 類似検索
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# ... (詳細はapi.pyを参照)
```

---

## 🛠️ 技術スタック

### バックエンド
- **FastAPI** - REST APIフレームワーク
- **ezdxf** - DXF解析ライブラリ
- **OpenAI API** - LLM要約・埋め込み生成
- **Supabase/PostgreSQL** - データベース
- **pgvector** - ベクトル検索

### 今後追加予定
- **PyMuPDF / pypdf** - PDF解析
- **OpenCV** - 画像前処理
- **Vision Transformer** - 画像解析
- **Tesseract OCR** - テキスト抽出

---

## 📊 使用例

### 例1：DXFファイルから寸法を抽出

```python
from enhanced_dxf_parser import EnhancedDXFParser

parser = EnhancedDXFParser("drawing.dxf")
result = parser.parse()

# 寸法情報
for dim in result['dimensions']['items']:
    print(f"寸法: {dim['measurement']}mm")

# 材質情報
for material in result['material_info']['items']:
    print(f"材質: {material['content']}")
```

### 例2：API経由で解析

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/analyze",
    headers={"X-API-Key": "dev-key-12345"},
    files={"file": open("drawing.dxf", "rb")},
    data={"generate_summary": True}
)

result = response.json()
print(result['summary']['natural_language_summary'])
```

### 例3：バッチ処理

```bash
# 複数のDXFファイルを一括変換
python3 dxf_to_json.py dxf_folder/ -o out_json --index

# Supabaseに一括投入
python3 import_to_supabase.py out_json/

# 埋め込みを生成
python3 generate_embeddings.py --all
```

---

## 🧪 テスト

### APIテスト

```bash
# ヘルスチェック
curl http://localhost:8000/api/v1/health

# DXF解析
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "X-API-Key: dev-key-12345" \
  -F "file=@test.dxf"

# Swagger UIでインタラクティブテスト
# http://localhost:8000/docs
```

### データベーステスト

```bash
python3 test_connection.py
```

---

## 🚀 デプロイ

### Docker（準備中）

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "drawing_analysis_api.py"]
```

### クラウドプラットフォーム

- **Railway**: `railway up`
- **Render**: Web Serviceとして設定
- **AWS Lambda**: Serverless Framework

---

## 📚 参考資料

- [ezdxf Documentation](https://ezdxf.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [pgvector](https://github.com/pgvector/pgvector)
- [OpenAI API](https://platform.openai.com/docs)

---

## 🤝 コントリビューション

Issue・PRを歓迎します！

### 優先度の高い実装予定機能

- [ ] PDF解析（PyMuPDF）
- [ ] 画像OCR（Tesseract + OpenCV）
- [ ] BOM自動生成ロジック
- [ ] GD&T記号認識（Vision Transformer）
- [ ] Dockerコンテナ化
- [ ] CI/CDパイプライン

---

## 📄 ライセンス

MIT License

---

## 👤 Author

IchiroFukuda

---

## ⚙️ トラブルシューティング

### `ezdxf` インストールエラー

```bash
pip install --upgrade pip
pip install ezdxf
```

### APIが起動しない

```bash
# 依存パッケージを確認
pip install -r requirements.txt
pip install python-multipart

# ポートを変更
uvicorn drawing_analysis_api:app --port 8001
```

### OpenAI APIエラー

```bash
# APIキーを確認
echo $OPENAI_API_KEY

# 環境変数を再設定
export OPENAI_API_KEY='sk-...'
```

---

**🎉 Let's analyze drawings with AI!**
