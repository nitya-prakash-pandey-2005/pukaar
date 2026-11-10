"""Render PITCH.md to a one-page A4 PITCH.pdf with the Pukaar logo and clickable links.

Usage (from the repo root; needs Google Chrome):
    uv run --no-project --with markdown --with pypdf python scripts/make_pitch_pdf.py

Steps: Markdown -> HTML (A4 print CSS, logo header) -> headless Chrome --print-to-pdf.
If the PDF has more than one page, the font shrinks in 0.2 pt steps until it fits.
Set CHROME=<path to chrome.exe> if Chrome is not in the default location.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "PITCH.md"
OUT = ROOT / "PITCH.pdf"
LOGO = ROOT / "docs" / "brand" / "logo.svg"
REPO = "https://github.com/nitya-prakash-pandey-2005/pukaar/blob/main/"

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "google-chrome",
    "chromium",
]

CSS = """
@page { size: A4; margin: 11mm 13mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: 'Segoe UI', 'Nirmala UI', 'Noto Sans', Arial, sans-serif;
       font-size: __SIZE__pt; line-height: 1.38; color: #0f172a; }
.head { display: flex; align-items: center; gap: 11px; padding: 0 0 7px; margin-bottom: 7px;
        border-bottom: 2px solid #0e7490; }
.head svg { width: 46px; height: 46px; flex: none; }
.head h1 { margin: 0; font-size: 1.62em; line-height: 1.15; letter-spacing: -0.01em; color: #0b1a36; }
.head h1 .tag { display: block; font-size: 0.62em; font-weight: 600; color: #0e7490; letter-spacing: 0; }
h2 { font-size: 1.12em; margin: 8px 0 3px; color: #0e7490; text-transform: uppercase; letter-spacing: .06em; }
p { margin: 3px 0; }
ul { margin: 2px 0 3px; padding-left: 16px; }
li { margin: 1.5px 0; }
a { color: #1d4ed8; text-decoration: none; border-bottom: 0.5px solid #93c5fd; }
strong { color: #0b1a36; }
em { color: #b45309; font-style: normal; font-weight: 600; }
code { font-family: Consolas, monospace; font-size: 0.92em; background: #f1f5f9; padding: 0 3px; border-radius: 3px; }
.foot { margin-top: 6px; padding-top: 4px; border-top: 1px solid #cbd5e1; font-size: 0.85em; color: #475569; }
"""


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    sys.exit("Chrome not found; set CHROME=<path>")


def build_html(size: float) -> str:
    md = SRC.read_text(encoding="utf-8")
    lines = md.splitlines()
    title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("# ") else "Pukaar"
    body_md = "\n".join(lines[1:]) if lines and lines[0].startswith("# ") else md
    # the last line of hashtags becomes a footer
    footer = ""
    m = re.search(r"\n(#\w[^\n]*)\s*$", body_md)
    if m:
        footer = m.group(1).strip()
        body_md = body_md[: m.start()]
    # Python-Markdown needs a blank line before a list; GitHub does not, so add one
    body_md = re.sub(r"(?m)^(?![-*] )(.+)\n(?=[-*] )", r"\1\n\n", body_md)
    body = markdown.markdown(body_md, extensions=["sane_lists"])
    # relative links point to the repo on GitHub so they stay clickable in the PDF
    body = re.sub(r'href="(?!https?:|mailto:|#)([^"]+)"', lambda mm: f'href="{REPO}{mm.group(1)}"', body)
    if ":" in title:
        name, tag = title.split(":", 1)
        h1 = f'{name.strip()}<span class="tag">{tag.strip()}</span>'
    else:
        h1 = title
    logo = LOGO.read_text(encoding="utf-8")
    logo = re.sub(r"<title>.*?</title>", "", logo, flags=re.S)
    foot = f'<div class="foot">{footer}</div>' if footer else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Pukaar · one-page pitch</title>'
        f"<style>{CSS.replace('__SIZE__', f'{size:.1f}')}</style></head><body>"
        f'<div class="head">{logo}<h1>{h1}</h1></div>{body}{foot}</body></html>'
    )


def render(chrome: str, html: str, out: Path) -> int:
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "pitch.html"
        page.write_text(html, encoding="utf-8")
        tmp_pdf = Path(td) / "pitch.pdf"
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={tmp_pdf}", page.as_uri()],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
        n = len(PdfReader(str(tmp_pdf)).pages)
        shutil.copyfile(tmp_pdf, out)
        if os.environ.get("KEEP_HTML"):
            (ROOT / "cache").mkdir(exist_ok=True)
            (ROOT / "cache" / "pitch.html").write_text(html, encoding="utf-8")
    return n


def main() -> None:
    chrome = find_chrome()
    size = float(os.environ.get("PITCH_PT", "10.6"))
    while size >= 7.0:
        pages = render(chrome, build_html(size), OUT)
        print(f"{size:.1f} pt -> {pages} page(s)")
        if pages == 1:
            print(f"wrote {OUT.relative_to(ROOT)}")
            return
        size = round(size - 0.2, 1)
    sys.exit("PITCH.md does not fit on one page even at 7 pt; shorten it.")


if __name__ == "__main__":
    main()
