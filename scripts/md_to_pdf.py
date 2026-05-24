"""Convert a Markdown file to a styled PDF.

Used for the SecondKind Bold Phase 1 synthesis. Built on `markdown-pdf` which
internally uses `markdown-it-py` for parsing and `pdfkit`-free PDF generation.

Usage:
    python scripts/md_to_pdf.py <input.md> <output.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

from markdown_pdf import MarkdownPdf, Section

CSS = """
@page {
    margin: 0.75in 0.7in;
}

body {
    font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1c1917;
}

h1 {
    font-size: 22pt;
    font-weight: 700;
    color: #1c1917;
    margin-top: 0;
    margin-bottom: 0.4em;
    page-break-after: avoid;
    border-bottom: 2px solid #1c1917;
    padding-bottom: 0.2em;
}

h2 {
    font-size: 16pt;
    font-weight: 700;
    color: #1c1917;
    margin-top: 1.6em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    border-bottom: 1px solid #d2d2cd;
    padding-bottom: 0.15em;
}

h3 {
    font-size: 13pt;
    font-weight: 700;
    color: #1c1917;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
    page-break-after: avoid;
}

h4 {
    font-size: 11.5pt;
    font-weight: 700;
    color: #1c1917;
    margin-top: 1em;
    margin-bottom: 0.3em;
    page-break-after: avoid;
}

p {
    margin: 0 0 0.7em 0;
}

ul, ol {
    margin: 0 0 0.7em 1.4em;
    padding: 0;
}

li {
    margin-bottom: 0.25em;
}

li > p {
    margin: 0;
}

blockquote {
    margin: 0.8em 0;
    padding: 0.5em 1em;
    border-left: 4px solid #fcb348;
    background: #faf8f3;
    color: #3f3a36;
    font-style: italic;
}

code {
    font-family: "Menlo", "Consolas", "Courier New", monospace;
    font-size: 9.5pt;
    background: #f2efe8;
    padding: 1px 4px;
    border-radius: 3px;
    color: #1c1917;
}

pre {
    background: #f2efe8;
    padding: 0.7em 1em;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.4;
}

pre code {
    background: none;
    padding: 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.8em 0 1em 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

th {
    background: #1c1917;
    color: #fefcf6;
    text-align: left;
    padding: 0.4em 0.6em;
    font-weight: 600;
    border: 1px solid #1c1917;
}

td {
    padding: 0.35em 0.6em;
    border: 1px solid #d2d2cd;
    vertical-align: top;
}

tr:nth-child(even) td {
    background: #faf8f3;
}

hr {
    border: none;
    border-top: 1px solid #d2d2cd;
    margin: 1.4em 0;
}

a {
    color: #1c1917;
    text-decoration: underline;
}

strong {
    font-weight: 700;
}

em {
    font-style: italic;
}

/* Cover page title block */
.cover-title {
    font-size: 28pt;
    font-weight: 700;
    margin-bottom: 0.2em;
}

.cover-subtitle {
    font-size: 11pt;
    font-style: italic;
    color: #6b665e;
    margin-bottom: 2em;
}
"""


def convert(md_path: Path, pdf_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")

    pdf = MarkdownPdf(toc_level=2, optimize=True)
    pdf.meta["title"] = "SecondKind Bold — Phase 1 Strategic Synthesis"
    pdf.meta["author"] = "AdCreatives strategy pipeline"
    pdf.meta["subject"] = "Phase 1 research, ICPs, gap map, creative matrix"

    pdf.add_section(Section(text, toc=True), user_css=CSS)
    pdf.save(str(pdf_path))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/md_to_pdf.py <input.md> <output.pdf>", file=sys.stderr)
        return 2

    md_path = Path(sys.argv[1])
    pdf_path = Path(sys.argv[2])

    if not md_path.exists():
        print(f"Input file not found: {md_path}", file=sys.stderr)
        return 1

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    convert(md_path, pdf_path)
    size_kb = pdf_path.stat().st_size / 1024
    print(f"Wrote {pdf_path} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
