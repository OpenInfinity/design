"""Outline the OpenInfinity wordmark (Geist Medium, tracking -2.5%, no ligatures) and build lockups.
Usage: python wordmark.py <font.otf> <out_dir>"""
import json, subprocess, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

FONT, OUT = sys.argv[1], sys.argv[2]
TEXT, TRACK = "OpenInfinity", -0.025
G = 0.618

font = TTFont(FONT)
upm = font["head"].unitsPerEm
cap = font["OS/2"].sCapHeight
gs = font.getGlyphSet()
shaped = json.loads(subprocess.check_output(
    ["hb-shape", "--features=-liga,-clig,-dlig,-calt", "--output-format=json", FONT, TEXT]))

def wordmark_paths(scale, x0, baseline):
    """Return SVG path data for the wordmark at font scale, origin x0, baseline y (SVG y-down)."""
    d, x = [], 0.0
    bp = BoundsPen(gs)
    for i, g in enumerate(shaped):
        t = (scale, 0, 0, -scale, x0 + (x + g["dx"]) * scale, baseline - g["dy"] * scale)
        sp = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        gs[g["g"]].draw(TransformPen(sp, t))
        gs[g["g"]].draw(TransformPen(bp, t))
        d.append(sp.getCommands())
        x += g["ax"] + (TRACK * upm if i < len(shaped) - 1 else 0)
    return "".join(d), bp.bounds  # bounds: xMin, yMin, xMax, yMax in SVG space

def leaf(px, py, s, dirn):
    r = s / 2; cx, cy = px + dirn * r, py + dirn * r
    f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    return f"M{f(px)} {f(py)}L{f(px)} {f(cy)}A{f(r)} {f(r)} 0 1 0 {f(cx)} {f(py)}Z"

def mark(x, y, span):
    B = span / (1 + G); P = B  # contact point offset from top-left
    return leaf(x + P, y + P, B, -1) + leaf(x + P, y + P, span - B, +1)

H = 1000.0                      # mark span in lockup units
X = H * (1 - 1 / (1 + G)) / 2   # small-leaf radius = 0.191 H
f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")

def svg(vb, d, color):
    x0, y0, x1, y1 = vb
    w, h = x1 - x0, y1 - y0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{f(x0)} {f(y0)} {f(w)} {f(h)}" '
            f'width="{f(w)}" height="{f(h)}"><path fill="{color}" d="{d}"/></svg>\n')

out = {}
# 1) wordmark alone at 1000 units per em
wd, wb = wordmark_paths(1000 / upm, 0, 0)
out["wordmark"] = ((wb[0], wb[1], wb[2], wb[3]), wd)
# 2) horizontal lockup: wordmark size = 0.7 H, ink gap 1.5X, cap height centred on the mark
s = 0.7 * H / upm
probe, pb = wordmark_paths(s, 0, 0)
x0 = H + 1.5 * X - pb[0]
base = H / 2 + cap * s / 2
hd, hb = wordmark_paths(s, x0, base)
out["lockup-horizontal"] = ((0, min(0, hb[1]), hb[2], max(H, hb[3])), mark(0, 0, H) + hd)
# 3) vertical lockup: wordmark size = 0.36 H, gap 1.25X from mark bottom to cap top, centred
s = 0.36 * H / upm
probe, pb = wordmark_paths(s, 0, 0)
wwidth = pb[2] - pb[0]
x0 = H / 2 - wwidth / 2 - pb[0]
base = H + 1.25 * X + cap * s
vd, vb = wordmark_paths(s, x0, base)
out["lockup-vertical"] = ((min(0, vb[0]), 0, max(H, vb[2]), vb[3]), mark(0, 0, H) + vd)
# 4) mark alone
out["mark"] = ((0, 0, H, H), mark(0, 0, H))

for name, (vb, d) in out.items():
    for cname, col in (("black", "#000000"), ("white", "#FFFFFF")):
        open(f"{OUT}/openinfinity-{name}-{cname}.svg", "w").write(svg(vb, d, col))
json.dump({"unitsPerEm": upm, "capHeight": cap, "tracking": TRACK, "X": X,
           "glyphs": [g["g"] for g in shaped]}, open(f"{OUT}/wordmark-metrics.json", "w"), indent=2)
print("ok", upm, cap, {k: [round(v, 1) for v in vb] for k, (vb, _) in out.items()})
