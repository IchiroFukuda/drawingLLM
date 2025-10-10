
#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Union

# You need: pip install ezdxf
try:
    import ezdxf
except Exception as e:
    print("ERROR: ezdxf is not installed. Please run: pip install ezdxf", file=sys.stderr)
    raise

SAFE_ENTITY_TYPES = {
    "LINE", "CIRCLE", "ARC", "ELLIPSE",
    "LWPOLYLINE", "POLYLINE", "SPLINE",
    "POINT",
    "TEXT", "MTEXT",
    "INSERT",
    "DIMENSION",
    "HATCH",
}

def bbox_of_entity(e) -> Union[None, List[float]]:
    # bbox() requires ezdxf>=1.0; fall back silently
    try:
        box = e.bbox()
        if box is None:
            return None
        # box is ((minx, miny, minz), (maxx, maxy, maxz))
        (minx, miny, _), (maxx, maxy, _) = box
        return [float(minx), float(miny), float(maxx), float(maxy)]
    except Exception:
        return None

def extract_basic(e) -> Dict[str, Any]:
    d = {
        "type": e.dxftype(),
        "layer": e.dxf.layer if hasattr(e, "dxf") and hasattr(e.dxf, "layer") else None,
        "color": getattr(e.dxf, "color", None),
        "linetype": getattr(e.dxf, "linetype", None),
        "lineweight": getattr(e.dxf, "lineweight", None),
        "bbox": bbox_of_entity(e),
    }
    t = d["type"]

    # Geometry fields per type (safe ones only)
    try:
        if t == "LINE":
            d["start"] = list(map(float, e.dxf.start[:2]))
            d["end"] = list(map(float, e.dxf.end[:2]))
        elif t == "CIRCLE":
            d["center"] = list(map(float, e.dxf.center[:2]))
            d["radius"] = float(e.dxf.radius)
        elif t == "ARC":
            d["center"] = list(map(float, e.dxf.center[:2]))
            d["radius"] = float(e.dxf.radius)
            d["start_angle"] = float(e.dxf.start_angle)
            d["end_angle"] = float(e.dxf.end_angle)
        elif t in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = []
                if t == "LWPOLYLINE":
                    pts = [list(map(float, (p[0], p[1]))) for p in e.get_points()]
                    d["is_closed"] = bool(e.closed)
                else:
                    pts = [list(map(float, (v.dxf.location[0], v.dxf.location[1]))) for v in e.vertices()]
                    d["is_closed"] = bool(e.is_closed)
                d["points"] = pts
            except Exception:
                pass
        elif t == "ELLIPSE":
            d["center"] = list(map(float, e.dxf.center[:2]))
            d["major_axis"] = list(map(float, e.dxf.major_axis[:2]))
            d["ratio"] = float(e.dxf.radius_ratio)
        elif t == "SPLINE":
            try:
                fit_points = [list(map(float, (p[0], p[1]))) for p in e.fit_points]
                d["fit_points"] = fit_points
            except Exception:
                pass
        elif t == "POINT":
            d["location"] = list(map(float, e.dxf.location[:2]))
        elif t in ("TEXT", "MTEXT"):
            d["text"] = e.dxf.text if hasattr(e.dxf, "text") else getattr(e, "plain_text", lambda: "")()
            # Position
            if hasattr(e.dxf, "insert"):
                d["position"] = list(map(float, e.dxf.insert[:2]))
        elif t == "DIMENSION":
            # ezdxf stores the measurement in various places depending on the style.
            # We extract what we safely can.
            d["text"] = getattr(e.dxf, "text", None)
            # measurement might be available via dimtype specific interface
            try:
                d["measurement"] = float(e.measurement)
            except Exception:
                d["measurement"] = None
        elif t == "HATCH":
            d["solid_fill"] = bool(getattr(e.dxf, "solid_fill", 0))
            d["pattern_name"] = getattr(e.dxf, "pattern_name", None)
        elif t == "INSERT":
            # Block reference (e.g., title blocks, symbols)
            d["name"] = e.dxf.name if hasattr(e.dxf, "name") else None
            try:
                d["insert"] = list(map(float, e.dxf.insert[:2]))
                d["xscale"] = float(getattr(e.dxf, "xscale", 1.0))
                d["yscale"] = float(getattr(e.dxf, "yscale", 1.0))
                d["rotation"] = float(getattr(e.dxf, "rotation", 0.0))
            except Exception:
                pass
    except Exception:
        # Be forgiving; we don't want to crash the whole run for a single odd entity
        pass
    return d

def parse_dxf(path: Path) -> Dict[str, Any]:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    ents = []
    counts = {}
    for e in msp:
        t = e.dxftype()
        if t not in SAFE_ENTITY_TYPES:
            counts[t] = counts.get(t, 0) + 1
            continue
        try:
            rec = extract_basic(e)
            ents.append(rec)
            counts[t] = counts.get(t, 0) + 1
        except Exception:
            counts[t] = counts.get(t, 0) + 1
            continue

    try:
        layers = [layer.dxf.name for layer in doc.layers] if hasattr(doc, "layers") else []
    except Exception:
        layers = []
    meta = {
        "filename": path.name,
        "path": str(path),
        "version": getattr(doc, "acad_release", None),
        "layer_count": len(layers),
        "layers": layers,
        "entity_counts": counts,
        "entity_sampled": len(ents),
    }
    return {"meta": meta, "entities": ents}

def write_json(data: Dict[str, Any], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def process_file(src: Path, out_dir: Path) -> Dict[str, Any]:
    try:
        data = parse_dxf(src)
        out_file = out_dir / (src.stem + ".json")
        write_json(data, out_file)
        return {
            "file": str(src),
            "ok": True,
            "json": str(out_file),
            "entities": data["meta"]["entity_counts"],
            "layers": data["meta"]["layer_count"],
        }
    except Exception as e:
        return {"file": str(src), "ok": False, "error": str(e)}

def iter_dxf_files(target: Path):
    if target.is_file() and target.suffix.lower() == ".dxf":
        yield target
    elif target.is_dir():
        for p in target.rglob("*.dxf"):
            yield p

def main():
    ap = argparse.ArgumentParser(description="DXF → JSON extractor (PoC)")
    ap.add_argument("input", help="DXF file or directory")
    ap.add_argument("-o", "--out", default="out_json", help="Output directory for JSON files")
    ap.add_argument("--index", action="store_true", help="Write index.jsonl with per-file summary")
    args = ap.parse_args()

    src = Path(args.input)
    out_dir = Path(args.out)
    summaries = []

    found = False
    for dxf_path in iter_dxf_files(src):
        found = True
        s = process_file(dxf_path, out_dir)
        summaries.append(s)
        status = "OK" if s.get("ok") else "FAIL"
        print(f"[{status}] {dxf_path}")

    if not found:
        print("No DXF files found.", file=sys.stderr)
        sys.exit(1)

    if args.index:
        out_dir.mkdir(parents=True, exist_ok=True)
        idx_path = out_dir / "index.jsonl"
        with idx_path.open("w", encoding="utf-8") as f:
            for s in summaries:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"Wrote index: {idx_path}")

if __name__ == "__main__":
    main()
