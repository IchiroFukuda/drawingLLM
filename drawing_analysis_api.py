#!/usr/bin/env python3

"""
Drawing Analysis API
統合図面解析REST API - DXF/DWG/PDF/画像の包括的な解析
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import openai

# ローカルモジュール
from enhanced_dxf_parser import EnhancedDXFParser

# FastAPIアプリ
app = FastAPI(
    title="Drawing Analysis API",
    description="包括的な図面解析API - DXF/DWG/PDF/画像の自動解析、BOM生成、寸法抽出",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 環境変数
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_KEY = os.getenv("API_KEY", "dev-key-12345")  # 本番環境では必ず設定

# OpenAI設定
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# 一時ファイル保存ディレクトリ
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============================================
# データモデル
# ============================================

class DimensionInfo(BaseModel):
    """寸法情報"""
    type: str
    measurement: Optional[float] = None
    text: Optional[str] = None
    position: Optional[List[float]] = None
    layer: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class TextInfo(BaseModel):
    """テキスト情報"""
    content: str
    category: str  # material, tolerance, thread, surface_finish, annotation, etc.
    position: Optional[List[float]] = None
    layer: Optional[str] = None
    height: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)


class BOMItem(BaseModel):
    """BOM項目"""
    part_number: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    material: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class DrawingSummary(BaseModel):
    """図面要約"""
    natural_language_summary: Optional[str] = None  # LLM生成
    key_dimensions: List[DimensionInfo]
    materials: List[str]
    total_entities: int
    has_bom: bool
    annotation_count: int


class AnalysisResult(BaseModel):
    """解析結果"""
    job_id: str
    filename: str
    file_type: str  # dxf, dwg, pdf, image
    timestamp: str
    
    # メタデータ
    metadata: Dict[str, Any]
    
    # 抽出情報
    dimensions: Dict[str, Any]
    texts: Dict[str, Any]
    material_info: Dict[str, Any]
    annotations: Dict[str, Any]
    tables: Dict[str, Any]  # BOM候補
    entities: Dict[str, Any]
    
    # 要約
    summary: DrawingSummary
    
    # ステータス
    status: str = "completed"  # pending, processing, completed, failed
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """ヘルスチェック"""
    status: str
    version: str
    timestamp: str
    features: Dict[str, bool]


# ============================================
# 認証
# ============================================

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """APIキー認証"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key required")
    
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    return x_api_key


# ============================================
# ヘルパー関数
# ============================================

def generate_job_id() -> str:
    """ジョブIDを生成"""
    return str(uuid.uuid4())


def detect_file_type(filename: str) -> str:
    """ファイルタイプを検出"""
    ext = Path(filename).suffix.lower()
    
    if ext in ['.dxf', '.dwg']:
        return 'dxf'
    elif ext == '.pdf':
        return 'pdf'
    elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
        return 'image'
    else:
        return 'unknown'


async def analyze_dxf(filepath: Path) -> Dict[str, Any]:
    """DXFファイルを解析"""
    try:
        parser = EnhancedDXFParser(filepath)
        result = parser.parse()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DXF parsing failed: {str(e)}")


async def analyze_pdf(filepath: Path) -> Dict[str, Any]:
    """PDFファイルを解析（未実装）"""
    # TODO: PyMuPDF/pypdfで実装
    return {
        "metadata": {"filename": filepath.name},
        "dimensions": {"count": 0, "items": []},
        "texts": {"count": 0, "items": []},
        "material_info": {"count": 0, "items": []},
        "annotations": {"count": 0, "items": []},
        "tables": {"count": 0, "bom_candidates": []},
        "entities": {"count": 0, "summary": {}, "items": []},
        "summary": {
            "key_dimensions": [],
            "materials": [],
            "total_entities": 0,
            "has_bom": False,
            "annotation_count": 0
        }
    }


async def analyze_image(filepath: Path) -> Dict[str, Any]:
    """画像ファイルを解析（未実装）"""
    # TODO: OpenCV + Vision Transformerで実装
    return {
        "metadata": {"filename": filepath.name},
        "dimensions": {"count": 0, "items": []},
        "texts": {"count": 0, "items": []},
        "material_info": {"count": 0, "items": []},
        "annotations": {"count": 0, "items": []},
        "tables": {"count": 0, "bom_candidates": []},
        "entities": {"count": 0, "summary": {}, "items": []},
        "summary": {
            "key_dimensions": [],
            "materials": [],
            "total_entities": 0,
            "has_bom": False,
            "annotation_count": 0
        }
    }


async def generate_llm_summary(analysis_data: Dict[str, Any]) -> Optional[str]:
    """LLMで自然言語要約を生成"""
    if not OPENAI_API_KEY:
        return None
    
    try:
        # 要約生成用のプロンプト
        prompt = f"""
以下の図面解析データを、技術者向けに簡潔に要約してください：

ファイル名: {analysis_data['metadata']['filename']}
エンティティ数: {analysis_data['entities']['count']}
寸法数: {analysis_data['dimensions']['count']}
材質情報: {', '.join(analysis_data['summary']['materials']) if analysis_data['summary']['materials'] else 'なし'}

要約（100文字以内）：
"""
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは機械図面の解析専門家です。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM summary generation failed: {e}")
        return None


# ============================================
# エンドポイント
# ============================================

@app.get("/", tags=["General"])
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Drawing Analysis API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "analyze": "POST /api/v1/analyze",
            "health": "GET /api/v1/health"
        }
    }


@app.get("/api/v1/health", response_model=HealthResponse, tags=["General"])
async def health():
    """ヘルスチェック"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        features={
            "dxf_analysis": True,
            "pdf_analysis": False,  # TODO: 実装後にTrue
            "image_analysis": False,  # TODO: 実装後にTrue
            "llm_summary": OPENAI_API_KEY is not None,
            "bom_extraction": True,
            "dimension_extraction": True
        }
    )


@app.post("/api/v1/analyze", response_model=AnalysisResult, tags=["Analysis"])
async def analyze_drawing(
    file: UploadFile = File(...),
    generate_summary: bool = True,
    api_key: str = Depends(verify_api_key)
):
    """
    図面ファイルを解析
    
    対応フォーマット:
    - DXF (✅ 完全対応)
    - DWG (🚧 今後対応)
    - PDF (🚧 今後対応)
    - 画像 (PNG, JPEG, TIFF) (🚧 今後対応)
    
    Returns:
    - 寸法情報
    - BOM（部品表）
    - 材質情報
    - テキスト注記
    - 幾何学的エンティティ
    - 自然言語要約（オプション）
    """
    job_id = generate_job_id()
    
    # ファイルタイプを検出
    file_type = detect_file_type(file.filename)
    
    if file_type == 'unknown':
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.filename}"
        )
    
    # 一時ファイルに保存
    temp_file = UPLOAD_DIR / f"{job_id}_{file.filename}"
    try:
        with temp_file.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # ファイルタイプ別に解析
        if file_type == 'dxf':
            analysis_data = await analyze_dxf(temp_file)
        elif file_type == 'pdf':
            analysis_data = await analyze_pdf(temp_file)
        elif file_type == 'image':
            analysis_data = await analyze_image(temp_file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # LLM要約を生成（オプション）
        llm_summary = None
        if generate_summary and OPENAI_API_KEY:
            llm_summary = await generate_llm_summary(analysis_data)
        
        # 要約を更新
        summary = DrawingSummary(
            natural_language_summary=llm_summary,
            key_dimensions=[
                DimensionInfo(**dim) for dim in analysis_data['summary']['key_dimensions']
            ],
            materials=analysis_data['summary']['materials'],
            total_entities=analysis_data['summary']['total_entities'],
            has_bom=analysis_data['summary']['has_bom'],
            annotation_count=analysis_data['summary']['annotation_count']
        )
        
        # 結果を構築
        result = AnalysisResult(
            job_id=job_id,
            filename=file.filename,
            file_type=file_type,
            timestamp=datetime.now().isoformat(),
            metadata=analysis_data['metadata'],
            dimensions=analysis_data['dimensions'],
            texts=analysis_data['texts'],
            material_info=analysis_data['material_info'],
            annotations=analysis_data['annotations'],
            tables=analysis_data['tables'],
            entities=analysis_data['entities'],
            summary=summary,
            status="completed"
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        # 一時ファイルを削除
        if temp_file.exists():
            temp_file.unlink()


@app.get("/api/v1/formats", tags=["General"])
async def supported_formats():
    """対応フォーマット一覧"""
    return {
        "supported": [
            {
                "format": "DXF",
                "extensions": [".dxf"],
                "status": "fully_supported",
                "features": ["dimensions", "bom", "materials", "annotations", "entities"]
            },
            {
                "format": "DWG",
                "extensions": [".dwg"],
                "status": "planned",
                "features": []
            },
            {
                "format": "PDF",
                "extensions": [".pdf"],
                "status": "planned",
                "features": []
            },
            {
                "format": "Images",
                "extensions": [".png", ".jpg", ".jpeg", ".tiff"],
                "status": "planned",
                "features": []
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    print("🚀 Drawing Analysis API starting...")
    print(f"   Version: 1.0.0")
    print(f"   OpenAI: {'✓ Enabled' if OPENAI_API_KEY else '✗ Disabled (no summary)'}")
    print(f"\n📍 API Documentation: http://localhost:8000/docs")
    print(f"🔐 API Key required: X-API-Key header\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
