#!/usr/bin/env python3

"""
拡張DXF解析エンジン
寸法、BOM、注記、材質情報などを抽出
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

try:
    import ezdxf
except ImportError:
    print("ERROR: ezdxf is not installed. Please run: pip install ezdxf", file=sys.stderr)
    sys.exit(1)


class EnhancedDXFParser:
    """拡張DXF解析クラス"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.doc = ezdxf.readfile(str(filepath))
        self.msp = self.doc.modelspace()
        
        # 抽出結果を格納
        self.dimensions = []
        self.texts = []
        self.tables = []  # BOMテーブル候補
        self.entities = []
        self.annotations = []
        self.material_info = []
        
    def parse(self) -> Dict[str, Any]:
        """すべての情報を解析"""
        self._extract_dimensions()
        self._extract_texts()
        self._extract_tables()
        self._extract_entities()
        self._extract_material_info()
        self._extract_metadata()
        
        return self._compile_results()
    
    def _extract_dimensions(self):
        """寸法情報を抽出"""
        for entity in self.msp.query('DIMENSION'):
            try:
                dim_data = {
                    "type": entity.dxftype(),
                    "layer": entity.dxf.layer if hasattr(entity.dxf, 'layer') else None,
                    "measurement": None,
                    "text": None,
                    "position": None,
                    "confidence": 1.0  # ベクターデータなので信頼度は高い
                }
                
                # 測定値を取得
                try:
                    dim_data["measurement"] = float(entity.measurement)
                except:
                    pass
                
                # 寸法テキストを取得
                if hasattr(entity.dxf, 'text'):
                    dim_data["text"] = entity.dxf.text
                
                # 位置情報
                if hasattr(entity.dxf, 'defpoint'):
                    dim_data["position"] = list(map(float, entity.dxf.defpoint[:2]))
                
                self.dimensions.append(dim_data)
            except Exception as e:
                continue
    
    def _extract_texts(self):
        """テキスト情報を抽出（注記、材質、公差など）"""
        for entity in self.msp.query('TEXT MTEXT'):
            try:
                # テキスト内容を取得
                if entity.dxftype() == 'TEXT':
                    text_content = entity.dxf.text if hasattr(entity.dxf, 'text') else ""
                else:  # MTEXT
                    text_content = getattr(entity, "plain_text", lambda: "")()
                
                if not text_content or not text_content.strip():
                    continue
                
                text_data = {
                    "content": text_content,
                    "layer": entity.dxf.layer if hasattr(entity.dxf, 'layer') else None,
                    "position": None,
                    "height": getattr(entity.dxf, 'height', None),
                    "category": self._classify_text(text_content),
                    "confidence": 1.0
                }
                
                # 位置情報
                if hasattr(entity.dxf, 'insert'):
                    text_data["position"] = list(map(float, entity.dxf.insert[:2]))
                
                self.texts.append(text_data)
                
                # カテゴリ別に振り分け
                if text_data["category"] == "material":
                    self.material_info.append(text_data)
                elif text_data["category"] == "annotation":
                    self.annotations.append(text_data)
                    
            except Exception as e:
                continue
    
    def _classify_text(self, text: str) -> str:
        """テキストの種類を分類"""
        text_upper = text.upper()
        
        # 材質パターン
        material_keywords = ['SUS', 'SS', 'STEEL', 'ALUMINUM', 'AL', 'BRASS', 
                           '鋼', 'アルミ', 'ステンレス', '材質']
        if any(kw in text_upper for kw in material_keywords):
            return "material"
        
        # 公差パターン
        tolerance_keywords = ['±', '±', 'TOL', 'H7', 'G6', 'JS', 'Ra', 'Rz']
        if any(kw in text_upper for kw in tolerance_keywords):
            return "tolerance"
        
        # タップ・ねじパターン
        thread_pattern = r'M\d+|UNC|UNF|Rc|Rp|PT'
        if re.search(thread_pattern, text):
            return "thread"
        
        # 表面粗さパターン
        if 'Ra' in text or 'Rz' in text or '▽' in text:
            return "surface_finish"
        
        # 数値のみ（寸法候補）
        if re.match(r'^[\d.±]+$', text.strip()):
            return "dimension_value"
        
        return "annotation"
    
    def _extract_tables(self):
        """テーブル（BOM候補）を抽出"""
        # TABLEエンティティまたはBLOCKから部品表を検出
        for entity in self.msp.query('INSERT'):
            try:
                block_name = entity.dxf.name if hasattr(entity.dxf, 'name') else None
                
                # BOMらしいブロック名をチェック
                if block_name and any(keyword in block_name.upper() for keyword in 
                                     ['BOM', 'PARTS', 'LIST', '部品表', '部品リスト']):
                    table_data = {
                        "name": block_name,
                        "position": list(map(float, entity.dxf.insert[:2])) if hasattr(entity.dxf, 'insert') else None,
                        "type": "bom_candidate",
                        "confidence": 0.7  # ヒューリスティックなので中程度の信頼度
                    }
                    self.tables.append(table_data)
            except:
                continue
    
    def _extract_entities(self):
        """幾何学的エンティティを抽出"""
        entity_types = ['LINE', 'CIRCLE', 'ARC', 'LWPOLYLINE', 'POLYLINE', 
                       'SPLINE', 'ELLIPSE']
        
        for etype in entity_types:
            for entity in self.msp.query(etype):
                try:
                    entity_data = {
                        "type": entity.dxftype(),
                        "layer": entity.dxf.layer if hasattr(entity.dxf, 'layer') else None,
                        "color": getattr(entity.dxf, 'color', None),
                    }
                    
                    # タイプ別の幾何情報
                    if etype == 'CIRCLE':
                        entity_data["geometry"] = {
                            "center": list(map(float, entity.dxf.center[:2])),
                            "radius": float(entity.dxf.radius)
                        }
                    elif etype == 'LINE':
                        entity_data["geometry"] = {
                            "start": list(map(float, entity.dxf.start[:2])),
                            "end": list(map(float, entity.dxf.end[:2]))
                        }
                    elif etype == 'ARC':
                        entity_data["geometry"] = {
                            "center": list(map(float, entity.dxf.center[:2])),
                            "radius": float(entity.dxf.radius),
                            "start_angle": float(entity.dxf.start_angle),
                            "end_angle": float(entity.dxf.end_angle)
                        }
                    
                    self.entities.append(entity_data)
                except:
                    continue
    
    def _extract_material_info(self):
        """材質情報を抽出（既にテキスト解析で分類済み）"""
        # material_infoは_extract_textsで既に収集されている
        pass
    
    def _extract_metadata(self):
        """図面のメタデータを抽出"""
        self.metadata = {
            "filename": self.filepath.name,
            "version": getattr(self.doc, 'acad_release', None),
            "layer_count": len(list(self.doc.layers)) if hasattr(self.doc, 'layers') else 0,
            "layers": [layer.dxf.name for layer in self.doc.layers] if hasattr(self.doc, 'layers') else []
        }
    
    def _compile_results(self) -> Dict[str, Any]:
        """結果をまとめる"""
        return {
            "metadata": self.metadata,
            "dimensions": {
                "count": len(self.dimensions),
                "items": self.dimensions
            },
            "texts": {
                "count": len(self.texts),
                "items": self.texts
            },
            "material_info": {
                "count": len(self.material_info),
                "items": self.material_info
            },
            "annotations": {
                "count": len(self.annotations),
                "items": self.annotations
            },
            "tables": {
                "count": len(self.tables),
                "bom_candidates": self.tables
            },
            "entities": {
                "count": len(self.entities),
                "summary": self._summarize_entities(),
                "items": self.entities[:100]  # 最初の100個のみ（APIでは全件返す）
            },
            "summary": self._generate_summary()
        }
    
    def _summarize_entities(self) -> Dict[str, int]:
        """エンティティの統計"""
        summary = {}
        for entity in self.entities:
            etype = entity["type"]
            summary[etype] = summary.get(etype, 0) + 1
        return summary
    
    def _generate_summary(self) -> Dict[str, Any]:
        """図面の要約を生成"""
        # 主要寸法を検出（最大値）
        key_dimensions = []
        if self.dimensions:
            sorted_dims = sorted(
                [d for d in self.dimensions if d.get("measurement")],
                key=lambda x: x["measurement"],
                reverse=True
            )
            key_dimensions = sorted_dims[:5]  # 上位5つ
        
        # 材質情報
        materials = [m["content"] for m in self.material_info]
        
        return {
            "key_dimensions": key_dimensions,
            "materials": materials,
            "total_entities": len(self.entities),
            "has_bom": len(self.tables) > 0,
            "annotation_count": len(self.annotations)
        }


def main():
    ap = argparse.ArgumentParser(description="拡張DXF解析エンジン")
    ap.add_argument("input", help="DXFファイル")
    ap.add_argument("-o", "--output", help="出力JSONファイル")
    ap.add_argument("--pretty", action="store_true", help="整形して出力")
    args = ap.parse_args()
    
    filepath = Path(args.input)
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    
    print(f"📄 解析中: {filepath.name}")
    
    try:
        parser = EnhancedDXFParser(filepath)
        result = parser.parse()
        
        # 結果を出力
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2 if args.pretty else None)
            print(f"✓ 出力: {output_path}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
        
        # サマリー表示
        print(f"\n📊 解析結果:")
        print(f"  寸法: {result['dimensions']['count']}件")
        print(f"  テキスト: {result['texts']['count']}件")
        print(f"  材質情報: {result['material_info']['count']}件")
        print(f"  注記: {result['annotations']['count']}件")
        print(f"  BOM候補: {result['tables']['count']}件")
        print(f"  エンティティ: {result['entities']['count']}件")
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
