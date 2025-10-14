#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_mock_dxfs.py - synthetic DXF generator for MVP demos.
"""
import argparse
import json
import random
from pathlib import Path
from datetime import datetime

try:
    import ezdxf
except Exception as e:
    raise SystemExit("Please install ezdxf: pip install ezdxf") from e

MATERIALS = ["S45C", "SUS304", "A5052", "SKD11", "SCM435"]
TOLERANCES = ["±0.01", "±0.02", "±0.05"]
THREADS = ["M6", "M8", "M10", "M12"]
FINISHES = ["Ra3.2", "Ra1.6", "Ra0.8"]
PART_TYPES = ["sleeve", "bracket", "cover", "shaft"]

def make_layers(doc):
    for name in ["0", "Defpoints", "Dim", "Text", "Plan 1"]:
        if name not in doc.layers:
            doc.layers.add(name)

def add_title_block(msp, filename, pos=(0, -40)):
    x, y = pos
    msp.add_lwpolyline([(x, y), (x+180, y), (x+180, y+30), (x, y+30), (x, y)], dxfattribs={"layer": "Plan 1"})
    msp.add_text(f"{filename}", dxfattribs={"layer": "Text", "height": 3, "insert": (x+5, y+22)})
    msp.add_text(f"DATE: {datetime.now().strftime('%Y-%m-%d')}", dxfattribs={"layer": "Text", "height": 2.5, "insert": (x+5, y+14)})
    msp.add_text("DRAWN BY: AI-GEN", dxfattribs={"layer": "Text", "height": 2.5, "insert": (x+5, y+7)})

def annotate_notes(msp, notes, origin=(100, 60)):
    x, y = origin
    line_h = 4
    for i, note in enumerate(notes):
        msp.add_text(note, dxfattribs={"layer": "Text", "height": 3, "insert": (x, y - i*line_h)})

def draw_sleeve(msp, params):
    R = params["outer_d"]/2
    r = params["inner_d"]/2
    msp.add_circle((0, 0), R, dxfattribs={"layer": "Plan 1"})
    msp.add_circle((0, 0), r, dxfattribs={"layer": "Plan 1"})
    msp.add_line((-R-10, 0), (R+10, 0), dxfattribs={"layer": "Dim"})
    msp.add_line((0, -R-10), (0, R+10), dxfattribs={"layer": "Dim"})
    msp.add_lwpolyline([(-R, -R-5), (-R, -R-8), (R, -R-8), (R, -R-5)], dxfattribs={"layer": "Plan 1"})

def draw_bracket(msp, params):
    w, h = params["width"], params["height"]
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2), (-w/2, -h/2)]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "Plan 1"})
    for dx in (-w*0.3, w*0.3):
        for dy in (-h*0.3, h*0.3):
            msp.add_circle((dx, dy), params["hole_d"]/2, dxfattribs={"layer": "Plan 1"})
    msp.add_lwpolyline([(-w*0.15, 0), (w*0.15, 0)], dxfattribs={"layer": "Plan 1"})

def draw_cover(msp, params):
    w, h = params["width"], params["height"]
    r = min(w, h) * 0.15
    pts = [(-w/2+r, -h/2), (w/2-r, -h/2), (w/2, -h/2+r),
           (w/2, h/2-r), (w/2-r, h/2), (-w/2+r, h/2),
           (-w/2, h/2-r), (-w/2, -h/2+r), (-w/2+r, -h/2)]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "Plan 1"})
    msp.add_circle((0, 0), params["center_hole_d"]/2, dxfattribs={"layer": "Plan 1"})

def draw_shaft(msp, params):
    L = params["length"]; d1 = params["d1"]; d2 = params["d2"]
    steps = [(-L/2, d1/2), (-L/4, d1/2), (-L/4, d2/2), (L/4, d2/2), (L/4, d1/2), (L/2, d1/2),
             (L/2, -d1/2), (L/4, -d1/2), (L/4, -d2/2), (-L/4, -d2/2), (-L/4, -d1/2), (-L/2, -d1/2), (-L/2, d1/2)]
    msp.add_lwpolyline(steps, dxfattribs={"layer": "Plan 1"})

def random_params(ptype, rng):
    if ptype == "sleeve":
        outer = rng.choice([24, 30, 36, 40])
        inner = rng.choice([6, 8, 10, 12, 16])
        if inner >= outer: inner = outer - 4
        return {"outer_d": outer, "inner_d": inner, "length": rng.choice([20,25,30])}
    if ptype == "bracket":
        return {"width": rng.choice([80,100,120]), "height": rng.choice([60,80,100]),
                "thickness": rng.choice([6,8,10]), "hole_d": rng.choice([6,8,10])}
    if ptype == "cover":
        return {"width": rng.choice([80,100,120]), "height": rng.choice([60,80,100]),
                "center_hole_d": rng.choice([8,12,16])}
    if ptype == "shaft":
        return {"length": rng.choice([80,100,120]), "d1": rng.choice([12,16,20]), "d2": rng.choice([8,10,12])}
    raise ValueError("unknown part type")

def generate_one(out_dir: Path, idx: int, ptype: str, rng: random.Random) -> dict:
    params = random_params(ptype, rng)
    material = rng.choice(MATERIALS)
    tol = rng.choice(TOLERANCES)
    thread = rng.choice(THREADS)
    finish = rng.choice(FINISHES)

    filename = f"{datetime.now().strftime('%y%m%d')}_{ptype}_{idx:03d}.dxf"
    path = out_dir / filename

    doc = ezdxf.new(setup=True)
    make_layers(doc)
    msp = doc.modelspace()

    # geometry
    if ptype == "sleeve":
        draw_sleeve(msp, params)
    elif ptype == "bracket":
        draw_bracket(msp, params)
    elif ptype == "cover":
        draw_cover(msp, params)
    elif ptype == "shaft":
        draw_shaft(msp, params)

    # notes
    notes = [
        f"PART: {ptype.upper()}",
        f"MATERIAL: {material}",
        f"TOL: {tol}",
        f"THREAD: {thread}",
        f"FINISH: {finish}",
    ]
    if ptype == "sleeve":
        notes.append(f"⌀{params['inner_d']}.0 {tol}")
        notes.append(f"⌀{params['outer_d']}.0")
    elif ptype == "bracket":
        notes.append(f"PLATE t={params['thickness']}")
        notes.append(f"HOLE ⌀{params['hole_d']} x4")
    elif ptype == "cover":
        notes.append(f"CENTER ⌀{params['center_hole_d']}")
    elif ptype == "shaft":
        notes.append(f"L={params['length']} d1={params['d1']} d2={params['d2']}")

    # place notes & title
    x0 = 60; y0 = 60
    for i, note in enumerate(notes):
        msp.add_text(note, dxfattribs={"layer": "Text", "height": 3, "insert": (x0, y0 - i*4)})
    # title block
    x, y = (0, -40)
    msp.add_lwpolyline([(x, y), (x+180, y), (x+180, y+30), (x, y+30), (x, y)], dxfattribs={"layer": "Plan 1"})
    msp.add_text(f"{filename}", dxfattribs={"layer": "Text", "height": 3, "insert": (x+5, y+22)})
    msp.add_text(f"DATE: {datetime.now().strftime('%Y-%m-%d')}", dxfattribs={"layer": "Text", "height": 2.5, "insert": (x+5, y+14)})
    msp.add_text("DRAWN BY: AI-GEN", dxfattribs={"layer": "Text", "height": 2.5, "insert": (x+5, y+7)})
    # border
    msp.add_lwpolyline([(-150, -100), (150, -100), (150, 100), (-150, 100), (-150, -100)], dxfattribs={"layer": "0"})

    doc.saveas(path.as_posix())

    return {
        "filename": filename,
        "path": str(path),
        "part_type": ptype,
        "params": params,
        "material": material,
        "tolerance": tol,
        "thread": thread,
        "finish": finish,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="mock_dxfs")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--types", nargs="*", choices=PART_TYPES, default=PART_TYPES)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = out_dir / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for i in range(1, args.count + 1):
            ptype = args.types[(i-1) % len(args.types)]
            rec = generate_one(out_dir, i, ptype, rng)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Generated {args.count} DXFs in {out_dir}")
    print(f"Manifest: {manifest}")

if __name__ == "__main__":
    main()
