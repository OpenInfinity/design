#!/usr/bin/env python3
"""Build every static OpenInfinity brand asset into assets/ from the masters in source/.

Requires python3, rsvg-convert (librsvg) and, for the macOS .icns, iconutil (macOS only).
Text in templates uses Geist from .cache/geist (see scripts/fetch-fonts.sh).
Motion is built separately by scripts/motion.py.
"""
import json
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CACHE, ICON_SPAN, INK, OUT, PALETTE, PAPER, ROOT, SRC, doc, f, lockup_at,  # noqa: E402
                    mark_at, parallel, rsvg, rsvg_pdf_pages, write)

FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def zip_dir(folder, out):
    folder, out = Path(folder), Path(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                zi = zipfile.ZipInfo(str(Path(folder.name) / p.relative_to(folder)), FIXED_TIME)
                zi.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(zi, p.read_bytes())


# ---------------------------------------------------------------- logo
def build_logo():
    jobs = []
    sizes = {"mark": ("s", [256, 512, 1024, 2048]),
             "wordmark": ("w", [800, 1600, 3200]),
             "lockup-horizontal": ("w", [800, 1600, 3200]),
             "lockup-vertical": ("w", [600, 1200, 2400])}
    for name, (axis, px) in sizes.items():
        for color in ("black", "white"):
            d = OUT / "logo" / name
            d.mkdir(parents=True, exist_ok=True)
            svg = d / f"openinfinity-{name}-{color}.svg"
            shutil.copyfile(SRC / f"openinfinity-{name}-{color}.svg", svg)
            jobs.append((svg, d / f"openinfinity-{name}-{color}.pdf", None, "pdf"))
            for p in px:
                jobs.append((svg, d / f"openinfinity-{name}-{color}-{p}.png", p, "png"))
    parallel(lambda j: rsvg(j[0], j[1], w=j[2], fmt=j[3]), jobs)


# ---------------------------------------------------------------- app icons
def icon_svg(size, bg, ink, span=ICON_SPAN):
    return doc(size, size, mark_at(size / 2, size / 2, size * span, ink), bg=bg)


def macos_legacy_svg():
    body = ('<defs><filter id="s" x="-10%" y="-10%" width="120%" height="125%">'
            '<feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000" flood-opacity="0.22"/></filter></defs>'
            '<rect x="100" y="100" width="824" height="824" rx="185.4" fill="#FFFFFF" filter="url(#s)"/>'
            + mark_at(512, 512, 824 * ICON_SPAN, INK))
    return doc(1024, 1024, body)


def build_apple():
    base = OUT / "app-icon" / "apple"
    srcd = base / "source"
    light = write(srcd / "app-icon-1024.svg", icon_svg(1024, PAPER, INK))
    dark = write(srcd / "app-icon-dark-1024.svg", icon_svg(1024, INK, PAPER))
    tinted = write(srcd / "app-icon-tinted-1024.svg", icon_svg(1024, INK, PAPER))
    legacy = write(srcd / "macos-legacy-1024.svg", macos_legacy_svg())
    for p in (light, dark, legacy):
        rsvg(p, p.with_suffix(".png"), w=1024)

    # iOS / iPadOS asset catalog (Xcode 16+: single 1024 + dark + tinted)
    ios = base / "ios" / "AppIcon.appiconset"
    ios.mkdir(parents=True, exist_ok=True)
    rsvg(light, ios / "AppIcon-1024.png", w=1024)
    rsvg(dark, ios / "AppIcon-1024-dark.png", w=1024)
    rsvg(tinted, ios / "AppIcon-1024-tinted.png", w=1024)
    img = lambda fn, app=None: dict({"filename": fn, "idiom": "universal", "platform": "ios", "size": "1024x1024"},
                                    **({"appearances": [{"appearance": "luminosity", "value": app}]} if app else {}))
    write(ios / "Contents.json", json.dumps({"images": [img("AppIcon-1024.png"), img("AppIcon-1024-dark.png", "dark"),
                                                        img("AppIcon-1024-tinted.png", "tinted")],
                                             "info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    zip_dir(ios, ios.parent / "AppIcon.appiconset.zip")

    # macOS 11–15: .iconset, .icns and an asset catalog, all from the 824-grid master
    mac = base / "macos"
    iconset = mac / "OpenInfinity.iconset"
    appset = mac / "AppIcon.appiconset"
    iconset.mkdir(parents=True, exist_ok=True)
    appset.mkdir(parents=True, exist_ok=True)
    entries, jobs = [], []
    for pt in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f"icon_{pt}x{pt}{'@2x' if scale == 2 else ''}.png"
            jobs.append((iconset / name, pt * scale))
            entries.append({"filename": name, "idiom": "mac", "scale": f"{scale}x", "size": f"{pt}x{pt}"})
    parallel(lambda j: rsvg(legacy, j[0], w=j[1]), jobs)
    for p, _ in jobs:
        shutil.copyfile(p, appset / p.name)
    write(appset / "Contents.json", json.dumps({"images": entries, "info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    if shutil.which("iconutil"):
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(mac / "OpenInfinity.icns")], check=True)
    zip_dir(iconset, mac / "OpenInfinity.iconset.zip")
    zip_dir(appset, mac / "AppIcon.appiconset.zip")

    # Icon Composer layers (macOS 26 / iOS 26 .icon)
    ic = base / "icon-composer"
    write(ic / "layer-mark-black.svg", doc(1024, 1024, mark_at(512, 512, 1024 * ICON_SPAN, INK)))
    write(ic / "layer-mark-white.svg", doc(1024, 1024, mark_at(512, 512, 1024 * ICON_SPAN, PAPER)))
    write(ic / "README.md", ICON_COMPOSER_README)


ICON_COMPOSER_README = """# Icon Composer · 图标分层

[中文](#中文) · [English](#english)

## 中文

macOS 26 / iOS 26 起，推荐用 Xcode 自带的 Icon Composer 制作 `.icon` 文件，系统会统一加圆角和玻璃效果。

1. 打开 Icon Composer，新建图标。
2. 背景（Background）设为纯色 `#FFFFFF`。
3. 把 `layer-mark-black.svg` 拖进来作为前景层。它是 1024 × 1024 透明画布，标志已经居中、比例正确，不要再缩放。
4. 切到深色外观（Dark）：背景改为 `#000000`，前景填充改为 `#FFFFFF`（或换用 `layer-mark-white.svg`）。
5. 透明（Clear）和着色（Tinted）外观由系统根据前景层自动生成，检查一遍即可。
6. 存储为 `OpenInfinity.icon`，拖进 Xcode 工程，在 Target 的 App Icon 中选择它。
7. 先关掉阴影、高光、半透明等玻璃参数，确认图形没问题后再按需开启。

需要兼容 macOS 15 及更早版本时，另外使用 `../macos/` 里的 `.icns` 或 `AppIcon.appiconset`。

## English

From macOS 26 / iOS 26, build a `.icon` file in Xcode's Icon Composer; the system applies the shape and Liquid Glass.

1. Open Icon Composer and create a new icon.
2. Set the Background to a solid `#FFFFFF`.
3. Drop in `layer-mark-black.svg` as the foreground layer. It is a 1024 × 1024 transparent canvas with the mark already centred and sized — do not rescale it.
4. In the Dark appearance, set the background to `#000000` and the foreground fill to `#FFFFFF` (or use `layer-mark-white.svg`).
5. Clear and Tinted appearances are generated from the foreground; review them.
6. Save as `OpenInfinity.icon`, add it to the Xcode project and select it as the target's App Icon.
7. Keep shadows, specular highlights and translucency off until the artwork is approved.

For macOS 15 and earlier, also ship the `.icns` or `AppIcon.appiconset` from `../macos/`.
"""


def write_ico(pngs, out):
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset, entries, data = 6 + 16 * len(pngs), b"", b""
    for size, blob in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset + len(data))
        data += blob
    Path(out).write_bytes(head + entries + data)


def build_web():
    d = OUT / "app-icon" / "web"
    tile = doc(64, 64, '<rect width="64" height="64" rx="14" fill="#FFFFFF"/>' + mark_at(32, 32, 64 * 0.62, INK))
    fav = write(d / "favicon.svg", tile)
    for s in (16, 32, 48):
        rsvg(fav, d / f"favicon-{s}.png", w=s)
    write_ico([(s, (d / f"favicon-{s}.png").read_bytes()) for s in (16, 32, 48)], d / "favicon.ico")
    full = icon_svg(1024, PAPER, INK)
    rsvg(full, d / "apple-touch-icon.png", w=180)
    rsvg(full, d / "icon-192.png", w=192)
    rsvg(full, d / "icon-512.png", w=512)
    rsvg(full, d / "icon-maskable-512.png", w=512)
    write(d / "site.webmanifest", json.dumps({
        "name": "OpenInfinity", "short_name": "OpenInfinity", "theme_color": "#000000", "background_color": "#FFFFFF",
        "display": "standalone",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]},
        indent=2) + "\n")
    write(d / "head-snippet.html", """<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#000000">
""")


DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def build_android():
    base = OUT / "app-icon" / "android"
    res = base / "res"
    fg = doc(108, 108, mark_at(54, 54, 72 * ICON_SPAN, INK))
    mono = fg
    legacy = doc(48, 48, '<rect width="48" height="48" rx="10" fill="#FFFFFF"/>' + mark_at(24, 24, 48 * ICON_SPAN, INK))
    rnd = doc(48, 48, '<circle cx="24" cy="24" r="24" fill="#FFFFFF"/>' + mark_at(24, 24, 48 * 0.5, INK))
    jobs = []
    for dens, k in DENSITIES.items():
        m = res / f"mipmap-{dens}"
        jobs += [(fg, m / "ic_launcher_foreground.png", 108 * k), (mono, m / "ic_launcher_monochrome.png", 108 * k),
                 (legacy, m / "ic_launcher.png", 48 * k), (rnd, m / "ic_launcher_round.png", 48 * k)]
    parallel(lambda j: rsvg(j[0], j[1], w=j[2]), jobs)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />
</adaptive-icon>
"""
    write(res / "mipmap-anydpi-v26" / "ic_launcher.xml", xml)
    write(res / "mipmap-anydpi-v26" / "ic_launcher_round.xml", xml)
    write(res / "values" / "ic_launcher_background.xml",
          '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#FFFFFF</color>\n</resources>\n')
    rsvg(icon_svg(1024, PAPER, INK), base / "play-store-512.png", w=512)
    zip_dir(res, base / "android-res.zip")


# ---------------------------------------------------------------- social
def build_social():
    d = OUT / "social"
    jobs = []
    for theme, bg, ink in (("light", PAPER, INK), ("dark", INK, PAPER)):
        av = doc(1024, 1024, mark_at(512, 512, 1024 * 0.52, ink), bg=bg)
        jobs += [(av, d / f"avatar-{theme}-1024.png", 1024), (av, d / f"avatar-{theme}-400.png", 400)]
        for name, (w, h, lw) in {"github-social-preview": (1280, 640, 640), "og-image": (1200, 630, 600),
                                 "x-header": (1500, 500, 560), "linkedin-banner": (1584, 396, 520)}.items():
            jobs.append((doc(w, h, lockup_at(w / 2, h / 2, lw, ink), bg=bg), d / f"{name}-{theme}.png", w))
    parallel(lambda j: rsvg(j[0], j[1], w=j[2]), jobs)


# ---------------------------------------------------------------- color
def write_ase(colors, out):
    def name(n):
        return struct.pack(">H", len(n) + 1) + (n + "\0").encode("utf-16-be")
    blocks, count = b"", 0
    g = name("OpenInfinity")
    blocks += struct.pack(">HI", 0xC001, len(g)) + g
    count += 1
    for n, hx in colors:
        r, gg, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
        body = name(n) + b"RGB " + struct.pack(">fff", r, gg, b) + struct.pack(">H", 2)
        blocks += struct.pack(">HI", 0x0001, len(body)) + body
        count += 1
    blocks += struct.pack(">HI", 0xC002, 0)
    count += 1
    Path(out).write_bytes(b"ASEF" + struct.pack(">HHI", 1, 0, count) + blocks)


def rgb(hx):
    return tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))


def cmyk(hx):
    r, g, b = (v / 255 for v in rgb(hx))
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0, 0, 0, 100)
    return tuple(round(v * 100) for v in ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k))


def build_color():
    d = OUT / "color"
    tokens = {"color": {"$type": "color"}}
    for pid, zh, en, hx, rzh, ren in PALETTE:
        tokens["color"][pid] = {"$value": hx, "$description": f"{en} / {zh} — {ren} / {rzh}"}
    write(d / "tokens.json", json.dumps(tokens, ensure_ascii=False, indent=2) + "\n")
    css = ":root {\n" + "".join(f"  --oi-{pid}: {hx}; /* {en} · {zh} */\n" for pid, zh, en, hx, *_ in PALETTE) + "}\n"
    write(d / "colors.css", css)
    write(d / "colors.scss", "".join(f"$oi-{pid}: {hx}; // {en} · {zh}\n" for pid, zh, en, hx, *_ in PALETTE))
    write_ase([(f"OpenInfinity {en}", hx) for pid, zh, en, hx, *_ in PALETTE], d / "openinfinity.ase")
    write(d / "openinfinity.gpl", "GIMP Palette\nName: OpenInfinity\nColumns: 4\n#\n" +
          "".join(f"{r:3d} {g:3d} {b:3d}\t{en}\n" for pid, zh, en, hx, *_ in PALETTE for r, g, b in [rgb(hx)]))
    table = [{"id": pid, "name": {"zh": zh, "en": en}, "hex": hx, "rgb": rgb(hx), "cmyk": cmyk(hx),
              "role": {"zh": rzh, "en": ren}} for pid, zh, en, hx, rzh, ren in PALETTE]
    write(d / "palette.json", json.dumps(table, ensure_ascii=False, indent=2) + "\n")
    # preview sheet
    cells = []
    for i, (pid, zh, en, hx, *_r) in enumerate(PALETTE):
        x, y = 80 + (i % 4) * 370, 80 + (i // 4) * 380
        fg = "#000000" if sum(rgb(hx)) > 380 else "#FFFFFF"
        cells.append(f'<rect x="{x}" y="{y}" width="340" height="340" rx="16" fill="{hx}" stroke="#E5E5E5"/>'
                     f'<text x="{x + 28}" y="{y + 270}" font-family="Geist" font-weight="500" font-size="30" fill="{fg}">{en}</text>'
                     f'<text x="{x + 28}" y="{y + 310}" font-family="Geist Mono, Menlo" font-size="22" fill="{fg}">{hx}</text>')
    rsvg(doc(1600, 900, "".join(cells), bg="#FFFFFF"), d / "palette-preview.png", w=1600)


# ---------------------------------------------------------------- templates
TXT = {
    "zh": {"name": "[姓名]", "title": "[职位]", "contact": "[邮箱] · [网址]", "slide": "[演示标题]",
           "slide_sub": "[日期] · [演讲人]", "font": "PingFang SC, Geist, sans-serif"},
    "en": {"name": "[Name]", "title": "[Title]", "contact": "[Email] · [Website]", "slide": "[Presentation title]",
           "slide_sub": "[Date] · [Speaker]", "font": "Geist, PingFang SC, sans-serif"},
}


def build_templates():
    d = OUT / "templates"
    # business card 90 x 54 mm + 3 mm bleed
    front = doc(96, 60, mark_at(48, 30, 13, PAPER), bg=INK, unit="mm")
    fpath = write(d / "business-card" / "business-card-front.svg", front)
    for lang, t in TXT.items():
        lw = 25.0
        back = doc(96, 60,
                   lockup_at(8 + lw / 2, 8 + lw / 5.068 / 2, lw, INK) +
                   f'<text x="8" y="42.5" font-family="{t["font"]}" font-weight="500" font-size="3.5" fill="#000">{t["name"]}</text>'
                   f'<text x="8" y="46.6" font-family="{t["font"]}" font-size="2.4" fill="#5E5E5E">{t["title"]}</text>'
                   f'<text x="8" y="51.5" font-family="Geist Mono, Menlo, {t["font"]}" font-size="2.2" fill="#5E5E5E">{t["contact"]}</text>',
                   bg=PAPER, unit="mm")
        bpath = write(d / "business-card" / f"business-card-back-{lang}.svg", back)
        rsvg_pdf_pages([fpath, bpath], d / "business-card" / f"business-card-{lang}.pdf")
    # slide cover 1920 x 1080
    for theme, bg, ink, sub in (("light", PAPER, INK, "#5E5E5E"), ("dark", "#0B1220", PAPER, "#9AA3B2")):
        for lang, t in TXT.items():
            lw = 64 * 5.068
            body = (lockup_at(120 + lw / 2, 120 + 32, lw, ink) +
                    f'<text x="120" y="760" font-family="{t["font"]}" font-weight="500" font-size="112" letter-spacing="-2" fill="{ink}">{t["slide"]}</text>'
                    f'<text x="120" y="850" font-family="Geist Mono, Menlo, {t["font"]}" font-size="34" fill="{sub}">{t["slide_sub"]}</text>')
            p = write(d / "slides" / f"slide-cover-{theme}-{lang}.svg", doc(1920, 1080, body, bg=bg))
            rsvg(p, p.with_suffix(".png"), w=1920)
    # video-call backgrounds and wallpapers
    jobs = []
    for theme, bg, ink in (("light", PAPER, INK), ("dark", INK, PAPER)):
        lw = 48 * 5.068
        jobs.append((doc(1920, 1080, lockup_at(1920 - 120 - lw / 2, 100 + 24, lw, ink), bg=bg),
                     d / "backgrounds" / f"virtual-background-{theme}.png", 1920))
        jobs.append((doc(5120, 2880, mark_at(2560, 1440, 480, ink), bg=bg), d / "wallpapers" / f"wallpaper-desktop-{theme}.png", 5120))
        jobs.append((doc(1290, 2796, mark_at(645, 1258, 300, ink), bg=bg), d / "wallpapers" / f"wallpaper-phone-{theme}.png", 1290))
    parallel(lambda j: rsvg(j[0], j[1], w=j[2]), jobs, workers=4)


def build_manifest():
    files = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "manifest.json" and not p.name.startswith("."):
            files.append({"path": str(p.relative_to(OUT)), "bytes": p.stat().st_size})
    write(OUT / "manifest.json", json.dumps({"files": files}, indent=1) + "\n")
    site_data = {"files": files,
                 "palette": json.loads((OUT / "color" / "palette.json").read_text()),
                 "headSnippet": (OUT / "app-icon" / "web" / "head-snippet.html").read_text()}
    write(ROOT / "site" / "data.js", "window.OI_DATA = " + json.dumps(site_data, ensure_ascii=False) + ";\n")
    return len(files)


STEPS = {"logo": build_logo, "apple": build_apple, "web": build_web, "android": build_android,
         "social": build_social, "color": build_color, "templates": build_templates}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(STEPS)
    if wanted == ["manifest"]:
        wanted = []
    elif not (CACHE / "geist").exists():
        sys.exit("Geist fonts missing: run scripts/fetch-fonts.sh first")
    for name in wanted:
        print("·", name, flush=True)
        STEPS[name]()
    print("manifest:", build_manifest(), "files")
