#!/usr/bin/env python3
"""Render the three brand animations (reveal, infinite, loading) to
MP4 / WebM (alpha) / GIF / animated SVG / Lottie JSON in assets/motion,
plus ProRes 4444 MOV (alpha) into dist/motion for the release.

Requires python3, rsvg-convert and ffmpeg (libx264, libvpx-vp9, prores_ks)."""
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DIST, G, INK, OUT, PAPER, f, parallel, rsvg, src, write  # noqa: E402

FPS = 60
EASE_OUT = (0.22, 1, 0.36, 1)
EASE_IN_OUT = (0.65, 0, 0.35, 1)


def bezier(x1, y1, x2, y2):
    def sample(a1, a2, t):
        return 3 * a1 * (1 - t) ** 2 * t + 3 * a2 * (1 - t) * t ** 2 + t ** 3

    def solve(x):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if sample(x1, x2, mid) < x:
                lo = mid
            else:
                hi = mid
        return sample(y1, y2, (lo + hi) / 2)
    return lambda x: 0.0 if x <= 0 else 1.0 if x >= 1 else solve(x)


ease_out, ease_in_out = bezier(*EASE_OUT), bezier(*EASE_IN_OUT)
clamp = lambda v: max(0.0, min(1.0, v))


# ------------------------------------------------------------ geometry
def leaf_pts(px, py, size, dirn):
    """Vertices for a leaf with its square corner at P (Lottie-style: v, in, out)."""
    r = size / 2
    k = r * 0.5522847498
    cx, cy = px + dirn * r, py + dirn * r
    s = dirn  # -1: lobe up-left, +1: lobe down-right
    v = [(px, py), (px, cy), (cx, cy + s * r), (cx + s * r, cy), (cx, py)]
    # tangents (relative) going round the arc: side point -> far point -> far side -> back to corner side
    i = [(0, 0), (0, 0), (-s * k, 0), (0, s * k), (s * k, 0)]
    o = [(0, 0), (0, s * k), (s * k, 0), (0, -s * k), (0, 0)]
    return v, i, o


def pts_to_d(v, i, o):
    d = f"M{f(v[0][0])} {f(v[0][1])}"
    n = len(v)
    for a in range(n):
        b = (a + 1) % n
        c1 = (v[a][0] + o[a][0], v[a][1] + o[a][1])
        c2 = (v[b][0] + i[b][0], v[b][1] + i[b][1])
        if o[a] == (0, 0) and i[b] == (0, 0):
            d += f"L{f(v[b][0])} {f(v[b][1])}" if b != 0 else ""
        else:
            d += f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(v[b][0])} {f(v[b][1])}"
    return d + "Z"


TOKEN = re.compile(r"[MLHVCQZ]|-?\d*\.?\d+(?:e-?\d+)?", re.I)


def parse_path(d):
    """Absolute M/L/H/V/C/Q/Z (fontTools SVGPathPen output) -> list of subpaths of cubic segments."""
    toks, i, subs, cur, pos = TOKEN.findall(d), 0, [], None, (0.0, 0.0)
    num = lambda: float(toks[i])
    while i < len(toks):
        cmd = toks[i]
        i += 1
        if cmd == "M":
            pos = (float(toks[i]), float(toks[i + 1])); i += 2
            cur = {"start": pos, "segs": []}
            subs.append(cur)
        elif cmd == "L":
            p = (float(toks[i]), float(toks[i + 1])); i += 2
            cur["segs"].append(("L", pos, p)); pos = p
        elif cmd == "H":
            p = (float(toks[i]), pos[1]); i += 1
            cur["segs"].append(("L", pos, p)); pos = p
        elif cmd == "V":
            p = (pos[0], float(toks[i])); i += 1
            cur["segs"].append(("L", pos, p)); pos = p
        elif cmd == "C":
            c1 = (float(toks[i]), float(toks[i + 1])); c2 = (float(toks[i + 2]), float(toks[i + 3]))
            p = (float(toks[i + 4]), float(toks[i + 5])); i += 6
            cur["segs"].append(("C", pos, c1, c2, p)); pos = p
        elif cmd == "Q":
            q = (float(toks[i]), float(toks[i + 1])); p = (float(toks[i + 2]), float(toks[i + 3])); i += 4
            c1 = (pos[0] + 2 / 3 * (q[0] - pos[0]), pos[1] + 2 / 3 * (q[1] - pos[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            cur["segs"].append(("C", pos, c1, c2, p)); pos = p
        elif cmd.upper() == "Z":
            if cur and pos != cur["start"]:
                cur["segs"].append(("L", pos, cur["start"]))
            pos = cur["start"] if cur else pos
        else:
            raise ValueError(f"unsupported path token {cmd}")
    return subs


def transform_subs(subs, k, tx, ty):
    t = lambda p: (p[0] * k + tx, p[1] * k + ty)
    out = []
    for s in subs:
        segs = []
        for seg in s["segs"]:
            segs.append((seg[0],) + tuple(t(p) for p in seg[1:]))
        out.append({"start": t(s["start"]), "segs": segs})
    return out


def subs_to_d(subs):
    d = ""
    for s in subs:
        d += f"M{f(s['start'][0])} {f(s['start'][1])}"
        for seg in s["segs"]:
            if seg[0] == "L":
                d += f"L{f(seg[2][0])} {f(seg[2][1])}"
            else:
                d += "C" + " ".join(f"{f(p[0])} {f(p[1])}" for p in seg[2:])
        d += "Z"
    return d


def subs_to_lottie(subs):
    shapes = []
    for s in subs:
        v, ii, oo = [], [], []
        for seg in s["segs"]:
            v.append(list(seg[1]))
            ii.append([0, 0])
            oo.append([seg[2][0] - seg[1][0], seg[2][1] - seg[1][1]] if seg[0] == "C" else [0, 0])
        # in-tangents belong to the segment end point
        for n, seg in enumerate(s["segs"]):
            nxt = (n + 1) % len(s["segs"])
            if seg[0] == "C":
                ii[nxt] = [seg[3][0] - seg[4][0], seg[3][1] - seg[4][1]]
        shapes.append({"ty": "sh", "ks": {"a": 0, "k": {"i": ii, "o": oo, "v": v, "c": True}}})
    return shapes


# ------------------------------------------------------------ scenes
def mark_scene(span, cx, cy):
    """Mark whose contact point sits at (cx, cy)."""
    big = span / (1 + G)
    small = span - big
    return {"P": (cx, cy), "big": leaf_pts(cx, cy, big, -1), "small": leaf_pts(cx, cy, small, +1)}


def reveal_scene():
    W, H = 1920, 1080
    vb, d = src("lockup-horizontal")
    width = 1200
    k = width / vb[2]
    x0, y0 = (W - width) / 2, (H - vb[3] * k) / 2
    span = 1000 * k
    P = (x0 + span / (1 + G), y0 + span / (1 + G))
    subs = parse_path_wordmark(d)
    word = transform_subs(subs, k, x0, y0)
    sc = mark_scene(span, *P)
    sc.update({"W": W, "H": H, "word": word, "dx": 60 * k})
    return sc


def parse_path_wordmark(d):
    """Drop the two leaf subpaths (they use arcs) and parse the glyph outlines."""
    parts = re.findall(r"M[^M]*", d)
    glyphs = "".join(p for p in parts if "A" not in p)
    return parse_path(glyphs)


def square_scene():
    return dict(mark_scene(540, 540, 540), W=1080, H=1080)


def reveal_state(t, loop):
    big = ease_out(clamp(t / 0.6))
    small = ease_out(clamp((t - 0.23) / 0.37))
    word = ease_out(clamp((t - 0.6) / 0.37))
    fade = 1.0
    if loop:
        fade = 1 - ease_out(clamp((t - 2.6) / 0.35))
    return {"big": big, "small": small, "word": word, "fade": fade}


def infinite_state(t):
    u = (t % 2.4) / 2.4
    if u < 0.5:
        e = ease_in_out(u * 2)
        return {"big": 1 - (1 - G) * e, "small": 1 + (1 / G - 1) * e}
    e = ease_in_out((u - 0.5) * 2)
    return {"big": G + (1 - G) * e, "small": 1 / G - (1 / G - 1) * e}


def loading_state(t):
    q = (t % 2.4) / 0.6
    n = math.floor(q)
    return {"angle": 90 * (n + ease_in_out(q - n))}


def frame_svg(kind, sc, st, ink, bg=None):
    P = sc["P"]
    body = ""
    tr = lambda s: f'translate({f(P[0])} {f(P[1])}) scale({s:.5f}) translate({f(-P[0])} {f(-P[1])})'
    if kind == "loading":
        body = (f'<g transform="rotate({st["angle"]:.4f} {f(P[0])} {f(P[1])})">'
                f'<path fill="{ink}" d="{pts_to_d(*sc["big"])}"/><path fill="{ink}" d="{pts_to_d(*sc["small"])}"/></g>')
    else:
        if st.get("big", 1) > 1e-4:
            body += f'<path fill="{ink}" transform="{tr(st["big"])}" d="{pts_to_d(*sc["big"])}"/>'
        if st.get("small", 1) > 1e-4:
            body += f'<path fill="{ink}" transform="{tr(st["small"])}" d="{pts_to_d(*sc["small"])}"/>'
        if kind == "reveal" and st["word"] > 1e-4:
            dx = -sc["dx"] * (1 - st["word"])
            body += f'<path fill="{ink}" opacity="{st["word"]:.4f}" transform="translate({dx:.3f} 0)" d="{subs_to_d(sc["word"])}"/>'
        if kind == "reveal":
            body = f'<g opacity="{st["fade"]:.4f}">{body}</g>'
    rect = f'<rect width="{sc["W"]}" height="{sc["H"]}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{sc["W"]}" height="{sc["H"]}" viewBox="0 0 {sc["W"]} {sc["H"]}">{rect}{body}</svg>'


def render_frames(kind, sc, state, seconds, ink, folder, fps=FPS):
    folder.mkdir(parents=True, exist_ok=True)
    n = round(seconds * fps)
    jobs = [(frame_svg(kind, sc, state(i / fps), ink), folder / f"f{i:04d}.png") for i in range(n)]
    parallel(lambda j: rsvg(j[0], j[1]), jobs)
    return folder / "f%04d.png"


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True)


def encode(pattern, out_mp4=None, bg="white", webm=None, mov=None, gif=None, gif_w=None, size=None, fps=FPS):
    W, H = size
    if out_mp4:
        ff("-framerate", fps, "-i", pattern, "-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r={fps}",
           "-filter_complex", "[1][0]overlay=shortest=1,format=yuv420p", "-c:v", "libx264", "-crf", "16",
           "-preset", "slow", "-movflags", "+faststart", out_mp4)
    if webm:
        ff("-framerate", fps, "-i", pattern, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28",
           "-auto-alt-ref", "0", "-row-mt", "1", webm)
    if mov:
        ff("-framerate", fps, "-i", pattern, "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
           "-vendor", "apl0", mov)
    if gif:
        ff("-framerate", fps, "-i", pattern, "-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r={fps}",
           "-filter_complex",
           f"[1][0]overlay=shortest=1,fps=30,scale={gif_w}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=32[p];[b][p]paletteuse=dither=none",
           "-loop", "0", gif)


# ------------------------------------------------------------ animated SVG (CSS keyframes)
def anim_svg(kind, sc, ink):
    P = sc["P"]
    W, H = sc["W"], sc["H"]
    o = f"transform-box:view-box;transform-origin:{f(P[0])}px {f(P[1])}px"
    if kind == "reveal":
        eo = "cubic-bezier(.22,1,.36,1)"
        css = (f".b{{{o};animation:b 3.2s {eo} infinite}}.s{{{o};animation:s 3.2s {eo} infinite}}"
               f".w{{animation:w 3.2s {eo} infinite}}"
               "@keyframes b{0%{transform:scale(0)}18.75%{transform:scale(1);opacity:1}81.25%{transform:scale(1);opacity:1}92.2%,100%{transform:scale(1);opacity:0}}"
               "@keyframes s{0%,7.2%{transform:scale(0)}18.75%{transform:scale(1);opacity:1}81.25%{transform:scale(1);opacity:1}92.2%,100%{transform:scale(1);opacity:0}}"
               f"@keyframes w{{0%,18.75%{{opacity:0;transform:translateX({f(-sc['dx'])}px)}}30.3%{{opacity:1;transform:translateX(0)}}81.25%{{opacity:1;transform:translateX(0)}}92.2%,100%{{opacity:0;transform:translateX(0)}}}}")
        body = (f'<path class="b" fill="{ink}" d="{pts_to_d(*sc["big"])}"/><path class="s" fill="{ink}" d="{pts_to_d(*sc["small"])}"/>'
                f'<path class="w" fill="{ink}" d="{subs_to_d(sc["word"])}"/>')
    elif kind == "infinite":
        e = "cubic-bezier(.65,0,.35,1)"
        css = (f".b{{{o};animation:b 2.4s {e} infinite}}.s{{{o};animation:s 2.4s {e} infinite}}"
               "@keyframes b{0%,100%{transform:scale(1)}50%{transform:scale(.618)}}"
               "@keyframes s{0%,100%{transform:scale(1)}50%{transform:scale(1.618)}}")
        body = f'<path class="b" fill="{ink}" d="{pts_to_d(*sc["big"])}"/><path class="s" fill="{ink}" d="{pts_to_d(*sc["small"])}"/>'
    else:
        e = "cubic-bezier(.65,0,.35,1)"
        css = (f".r{{{o};animation:r 2.4s {e} infinite}}"
               "@keyframes r{0%{transform:rotate(0)}25%{transform:rotate(90deg)}50%{transform:rotate(180deg)}75%{transform:rotate(270deg)}100%{transform:rotate(360deg)}}")
        body = f'<g class="r"><path fill="{ink}" d="{pts_to_d(*sc["big"])}"/><path fill="{ink}" d="{pts_to_d(*sc["small"])}"/></g>'
    css += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f"<style>{css}</style>{body}</svg>\n")


# ------------------------------------------------------------ Lottie
def kf(t, s, ease=None, hold=False):
    k = {"t": t, "s": s}
    if hold:
        k["h"] = 1
    elif ease:
        k["o"] = {"x": [ease[0]], "y": [ease[1]]}
        k["i"] = {"x": [ease[2]], "y": [ease[3]]}
    return k


def static(v):
    return {"a": 0, "k": v}


def layer(ind, name, shapes, P, op, scale=None, rot=None, opacity=None, pos=None):
    ks = {"o": opacity or static(100), "r": rot or static(0),
          "p": pos or static([P[0], P[1], 0]), "a": static([P[0], P[1], 0]), "s": scale or static([100, 100, 100])}
    return {"ddd": 0, "ind": ind, "ty": 4, "nm": name, "sr": 1, "ks": ks, "ao": 0, "ip": 0, "op": op, "st": 0, "bm": 0,
            "shapes": [{"ty": "gr", "nm": name, "it": shapes + [
                {"ty": "fl", "c": static([0, 0, 0, 1]), "o": static(100), "r": 1},
                {"ty": "tr", "p": static([0, 0]), "a": static([0, 0]), "s": static([100, 100]), "r": static(0), "o": static(100)}]}]}


def leaf_shape(pts):
    v, i, o = pts
    return [{"ty": "sh", "ks": {"a": 0, "k": {"v": [list(p) for p in v], "i": [list(p) for p in i], "o": [list(p) for p in o], "c": True}}}]


def lottie(kind, sc):
    P = sc["P"]
    fr = lambda s: round(s * FPS)
    if kind == "reveal":
        op = fr(3.2)
        fade = {"a": 1, "k": [kf(0, [100]), kf(fr(2.6), [100], EASE_OUT), kf(fr(2.95), [0], hold=True), kf(op, [0])]}
        sb = {"a": 1, "k": [kf(0, [0, 0, 100], EASE_OUT), kf(fr(0.6), [100, 100, 100], hold=True), kf(op, [100, 100, 100])]}
        ss = {"a": 1, "k": [kf(0, [0, 0, 100], hold=True), kf(fr(0.23), [0, 0, 100], EASE_OUT),
                            kf(fr(0.6), [100, 100, 100], hold=True), kf(op, [100, 100, 100])]}
        wo = {"a": 1, "k": [kf(0, [0], hold=True), kf(fr(0.6), [0], EASE_OUT), kf(fr(0.97), [100]),
                            kf(fr(2.6), [100], EASE_OUT), kf(fr(2.95), [0], hold=True), kf(op, [0])]}
        wp = {"a": 1, "k": [kf(0, [-sc["dx"], 0, 0], hold=True), kf(fr(0.6), [-sc["dx"], 0, 0], EASE_OUT),
                            kf(fr(0.97), [0, 0, 0], hold=True), kf(op, [0, 0, 0])]}
        word = {"ddd": 0, "ind": 3, "ty": 4, "nm": "wordmark", "sr": 1, "ao": 0, "ip": 0, "op": op, "st": 0, "bm": 0,
                "ks": {"o": wo, "r": static(0), "p": wp, "a": static([0, 0, 0]), "s": static([100, 100, 100])},
                "shapes": [{"ty": "gr", "nm": "wordmark", "it": subs_to_lottie(sc["word"]) + [
                    {"ty": "fl", "c": static([0, 0, 0, 1]), "o": static(100), "r": 1},
                    {"ty": "tr", "p": static([0, 0]), "a": static([0, 0]), "s": static([100, 100]), "r": static(0), "o": static(100)}]}]}
        layers = [layer(1, "big", leaf_shape(sc["big"]), P, op, scale=sb, opacity=fade),
                  layer(2, "small", leaf_shape(sc["small"]), P, op, scale=ss, opacity=fade), word]
    elif kind == "infinite":
        op = fr(2.4)
        sb = {"a": 1, "k": [kf(0, [100, 100, 100], EASE_IN_OUT), kf(fr(1.2), [61.8, 61.8, 100], EASE_IN_OUT), kf(op, [100, 100, 100])]}
        ss = {"a": 1, "k": [kf(0, [100, 100, 100], EASE_IN_OUT), kf(fr(1.2), [161.8, 161.8, 100], EASE_IN_OUT), kf(op, [100, 100, 100])]}
        layers = [layer(1, "big", leaf_shape(sc["big"]), P, op, scale=sb),
                  layer(2, "small", leaf_shape(sc["small"]), P, op, scale=ss)]
    else:
        op = fr(2.4)
        rot = {"a": 1, "k": [kf(fr(0.6 * q), [90 * q], EASE_IN_OUT) for q in range(4)] + [kf(op, [360])]}
        layers = [layer(1, "big", leaf_shape(sc["big"]), P, op, rot=rot),
                  layer(2, "small", leaf_shape(sc["small"]), P, op, rot=rot)]
    return {"v": "5.7.4", "fr": FPS, "ip": 0, "op": op, "w": sc["W"], "h": sc["H"], "nm": f"OpenInfinity {kind}",
            "ddd": 0, "assets": [], "layers": layers}


# ------------------------------------------------------------ main
def main():
    out = OUT / "motion"
    out.mkdir(parents=True, exist_ok=True)
    rel = DIST / "motion"
    rel.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="oi-motion-"))
    scenes = {"reveal": reveal_scene(), "infinite": square_scene(), "loading": square_scene()}
    plans = {
        # kind: (video state, video seconds, loop state, loop seconds, gif width)
        "reveal": (lambda t: reveal_state(t, False), 3.0, lambda t: reveal_state(t, True), 3.2, 960),
        "infinite": (infinite_state, 2.4, infinite_state, 2.4, 540),
        "loading": (loading_state, 2.4, loading_state, 2.4, 540),
    }
    for kind, (vstate, vsec, lstate, lsec, gw) in plans.items():
        sc = scenes[kind]
        size = (sc["W"], sc["H"])
        print("·", kind, flush=True)
        black = render_frames(kind, sc, vstate, vsec, INK, tmp / kind / "black")
        white = render_frames(kind, sc, vstate, vsec, PAPER, tmp / kind / "white")
        encode(black, out_mp4=out / f"{kind}.mp4", bg="white", webm=out / f"{kind}-transparent-black.webm",
               mov=rel / f"{kind}-transparent-black.mov", size=size)
        encode(white, out_mp4=out / f"{kind}-dark.mp4", bg="black", webm=out / f"{kind}-transparent-white.webm",
               mov=rel / f"{kind}-transparent-white.mov", size=size)
        loopf = render_frames(kind, sc, lstate, lsec, INK, tmp / kind / "loop") if kind == "reveal" else black
        encode(loopf, gif=out / f"{kind}.gif", gif_w=gw, size=size)
        write(out / f"{kind}.svg", anim_svg(kind, sc, INK))
        write(out / f"{kind}-white.svg", anim_svg(kind, sc, PAPER))
        write(out / f"{kind}.json", json.dumps(lottie(kind, sc), separators=(",", ":")))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
