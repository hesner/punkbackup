"""Converts the project's Markdown manuals into bilingual PDFs.

Usage: .venv\\Scripts\\python.exe docs\\build_pdfs.py

Pure-Python pipeline (markdown -> HTML -> PDF via xhtml2pdf) — no system
dependencies like Cairo/Pango, so it installs cleanly with plain pip on
Windows. Output goes to docs/pdf/.
"""
from __future__ import annotations

from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "docs" / "pdf"

CSS = """
@page {
    size: letter;
    margin: 2.2cm 1.8cm;
    @frame footer {
        -pdf-frame-content: footerContent;
        bottom: 1cm; margin-left: 1.8cm; margin-right: 1.8cm; height: 1cm;
    }
}
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; line-height: 1.45; }
h1 { color: #c81d4a; font-size: 20pt; border-bottom: 3px solid #c81d4a; padding-bottom: 6px; margin-top: 0; }
h2 { color: #1a1a1a; font-size: 14pt; margin-top: 20px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }
h3 { color: #333; font-size: 11.5pt; margin-top: 14px; }
p, li { font-size: 10.5pt; }
code { background: #f2f2f2; padding: 1px 4px; border-radius: 3px; font-family: Courier, monospace; font-size: 9.5pt; }
pre { background: #f2f2f2; padding: 8px; border-radius: 4px; font-family: Courier, monospace; font-size: 9pt; }
blockquote { border-left: 3px solid #c81d4a; margin-left: 0; padding-left: 12px; color: #444; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { border: 1px solid #ccc; padding: 5px 8px; font-size: 9.5pt; text-align: left; }
th { background: #f2f2f2; }
a { color: #c81d4a; }
.brand { color: #888; font-size: 8.5pt; }
"""

FOOTER = """<div id="footerContent" class="brand">PunkBackup — Tus recuerdos. Tu USB. Cero dependencia de la nube.</div>"""

# (markdown source, output pdf filename)
MANUALS = [
    (ROOT / "docs" / "es" / "manual_instalacion.md", "PunkBackup - Manual de Instalacion (ES).pdf"),
    (ROOT / "docs" / "es" / "manual_troubleshooting.md", "PunkBackup - Manual de Solucion de Problemas (ES).pdf"),
    (ROOT / "docs" / "es" / "manual_desinstalacion.md", "PunkBackup - Manual de Desinstalacion (ES).pdf"),
    (ROOT / "shortcuts" / "INSTRUCCIONES_ATAJO.md", "PunkBackup - Configuracion del iPhone (ES).pdf"),
    (ROOT / "docs" / "en" / "installation_manual.md", "PunkBackup - Installation Manual (EN).pdf"),
    (ROOT / "docs" / "en" / "troubleshooting_manual.md", "PunkBackup - Troubleshooting Manual (EN).pdf"),
    (ROOT / "docs" / "en" / "uninstallation_manual.md", "PunkBackup - Uninstallation Manual (EN).pdf"),
    (ROOT / "shortcuts" / "SHORTCUT_INSTRUCTIONS.md", "PunkBackup - iPhone Setup Manual (EN).pdf"),
]


def build_pdf(md_path: Path, out_name: str) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    html = f"<html><head><style>{CSS}</style></head><body>{FOOTER}{body_html}</body></html>"

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PDF_DIR / out_name
    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f)
    status = "OK" if not result.err else f"ERROR ({result.err})"
    print(f"{status}: {out_path.name}")


def main() -> None:
    for md_path, out_name in MANUALS:
        if not md_path.exists():
            print(f"MISSING SOURCE: {md_path}")
            continue
        build_pdf(md_path, out_name)


if __name__ == "__main__":
    main()
