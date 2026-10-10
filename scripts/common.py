"""Shared helpers for the OpenInfinity asset build."""
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source"
OUT = ROOT / "assets"
DIST = ROOT / "dist"
CACHE = ROOT / ".cache"

G = 0.618                      # small : big
ICON_SPAN = 460 / 864          # mark width / icon width (approved 4A proportion)

INK, PAPER = "#000000", "#FFFFFF"

PALETTE = [
    # id, zh name, en name, hex, role zh, role en
    ("ink", "墨", "Ink", "#000000", "主色：标志、正文", "Primary: logo, text"),
    ("paper", "白", "Paper", "#FFFFFF", "主色：底色", "Primary: background"),
    ("graphite", "石墨", "Graphite", "#18181B", "界面深色文字", "UI dark text"),
    ("mist", "雾白", "Mist", "#F5F5F4", "界面浅色底", "UI light surface"),
    ("midnight", "午夜", "Midnight", "#0B1220", "深色模式、演示", "Dark mode, slides"),
    ("signal", "信号橙", "Signal", "#FF4D00", "强调色（可选）", "Accent (optional)"),
    ("electric", "电光蓝", "Electric", "#2440FF", "强调色（可选）", "Accent (optional)"),
    ("lime", "青柠", "Lime", "#C8F560", "强调色（可选）", "Accent (optional)"),
]


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def src(name):
    """(viewBox tuple, path d) of a black master in source/."""
    t = (SRC / f"openinfinity-{name}-black.svg").read_text()
    vb = tuple(float(x) for x in re.search(r'viewBox="([^"]+)"', t).group(1).split())
    d = re.search(r' d="([^"]+)"', t).group(1)
    return vb, d


def nest(name, x, y, w=None, h=None, color=INK):
    vb, d = src(name)
    if w is None:
        w = h * vb[2] / vb[3]
    if h is None:
        h = w * vb[3] / vb[2]
    return (f'<svg x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" viewBox="{" ".join(f(v) for v in vb)}">'
            f'<path fill="{color}" d="{d}"/></svg>')


def mark_at(cx, cy, span, color=INK):
    return nest("mark", cx - span / 2, cy - span / 2, span, span, color)


def lockup_at(cx, cy, width, color=INK, kind="horizontal"):
    vb, _ = src(f"lockup-{kind}")
    h = width * vb[3] / vb[2]
    return nest(f"lockup-{kind}", cx - width / 2, cy - h / 2, width, h, color)


def doc(w, h, body, bg=None, unit="", extra=""):
    rect = f'<rect width="{f(w)}" height="{f(h)}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}{unit}" height="{f(h)}{unit}" '
            f'viewBox="0 0 {f(w)} {f(h)}">{extra}{rect}{body}</svg>\n')


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def fonts_env():
    """fontconfig setup so rsvg-convert can see the Geist fonts in .cache/geist."""
    conf = CACHE / "fonts.conf"
    geist = CACHE / "geist"
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text(f"""<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig><dir>{geist}</dir><dir>/System/Library/Fonts</dir><dir>/Library/Fonts</dir>
<dir>~/Library/Fonts</dir><cachedir>{CACHE}/fc-cache</cachedir></fontconfig>""")
    env = dict(os.environ)
    env["FONTCONFIG_FILE"] = str(conf)
    return env


ENV = None


def rsvg(svg_text_or_path, out, w=None, h=None, fmt="png"):
    """Render SVG (text or path) to png/pdf with rsvg-convert."""
    global ENV
    if ENV is None:
        ENV = fonts_env()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    if isinstance(svg_text_or_path, str) and svg_text_or_path.lstrip().startswith("<"):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False)
        tmp.write(svg_text_or_path)
        tmp.close()
        srcp = tmp.name
    else:
        srcp = str(svg_text_or_path)
    cmd = ["rsvg-convert", "-f", fmt, "-o", str(out)]
    if w:
        cmd += ["-w", str(int(w))]
    if h:
        cmd += ["-h", str(int(h))]
    subprocess.run(cmd + [srcp], check=True, env=ENV)
    if tmp:
        os.unlink(tmp.name)
    return out


def rsvg_pdf_pages(svg_paths, out):
    global ENV
    if ENV is None:
        ENV = fonts_env()
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(out)] + [str(p) for p in svg_paths], check=True, env=ENV)


def parallel(fn, items, workers=8):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def reset(path):
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
