#!/usr/bin/env python3
"""Print the guideline PDFs from the site and pack the release archives into dist/.

1. Assemble the site (site/ + assets/) in .cache/_site
2. Print index.html?lang=zh|en to assets/guidelines/*.pdf with headless Chrome
3. Refresh assets/manifest.json and site/data.js
4. Zip the brand kit and per-category archives into dist/
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, DIST, OUT, ROOT  # noqa: E402

CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "",
]
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def assemble():
    site = CACHE / "_site"
    if site.exists():
        shutil.rmtree(site)
    shutil.copytree(ROOT / "site", site)
    shutil.copytree(OUT, site / "assets")
    return site


def print_guidelines(site):
    chrome = next((c for c in CHROME if c and Path(c).exists()), None)
    if not chrome:
        print("! Chrome not found — guideline PDFs skipped")
        return
    out = OUT / "guidelines"
    out.mkdir(parents=True, exist_ok=True)
    for lang in ("zh", "en"):
        pdf = out / f"openinfinity-brand-guidelines-{lang}.pdf"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--hide-scrollbars",
                        "--virtual-time-budget=8000", f"--print-to-pdf={pdf}",
                        (site / "index.html").as_uri() + f"?lang={lang}"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("·", pdf.name, pdf.stat().st_size // 1024, "KB")


def zip_tree(out, entries):
    """entries: list of (source path, path inside zip)."""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries:
            src = Path(src)
            files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())
            for p in files:
                name = arc if src.is_file() else str(Path(arc) / p.relative_to(src))
                zi = zipfile.ZipInfo(name, FIXED_TIME)
                zi.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(zi, p.read_bytes())
    print("·", out.name, out.stat().st_size // 1024, "KB")


def pack():
    DIST.mkdir(exist_ok=True)
    top = "OpenInfinity-Brand-Kit"
    legal = [(ROOT / "README.md", f"{top}/README.md"), (ROOT / "TRADEMARK.md", f"{top}/TRADEMARK.md")]
    kit = [(OUT / d, f"{top}/{d}") for d in ("logo", "app-icon", "color", "motion", "templates", "social", "guidelines")]
    zip_tree(DIST / "OpenInfinity-Brand-Kit.zip", legal + kit)
    cats = {"Logo": ["logo"], "App-Icons": ["app-icon"], "Color": ["color"], "Motion": ["motion"],
            "Templates": ["templates", "social"]}
    for name, dirs in cats.items():
        zip_tree(DIST / f"OpenInfinity-{name}.zip",
                 [(ROOT / "TRADEMARK.md", f"OpenInfinity-{name}/TRADEMARK.md")] +
                 [(OUT / d, f"OpenInfinity-{name}/{d}") for d in dirs])
    movs = DIST / "motion"
    if movs.exists():
        zip_tree(DIST / "OpenInfinity-Motion-ProRes.zip",
                 [(ROOT / "TRADEMARK.md", "OpenInfinity-Motion-ProRes/TRADEMARK.md"), (movs, "OpenInfinity-Motion-ProRes")])


if __name__ == "__main__":
    site = assemble()
    print_guidelines(site)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"), "manifest"], check=True)
    pack()
