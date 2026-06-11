"""Build a clean PDF of the client-facing strategy document.

MD -> HTML (with embedded CSS) -> PDF (via Edge headless).
"""
import subprocess
from pathlib import Path
import markdown

EXPORTS_DIR = Path(__file__).parent
MD_PATH = EXPORTS_DIR / 'SecondKind-Bold-Organic-Strategy.md'
HTML_PATH = EXPORTS_DIR / 'SecondKind-Bold-Organic-Strategy.html'
PDF_PATH = EXPORTS_DIR / 'SecondKind-Bold-Organic-Strategy.pdf'

# Read markdown
md_text = MD_PATH.read_text(encoding='utf-8')

# Convert markdown to HTML
html_body = markdown.markdown(
    md_text,
    extensions=['extra', 'tables', 'sane_lists', 'smarty']
)

# Wrap with clean professional CSS
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SecondKind Bold — Organic Content Strategy</title>
<style>
  @page {
    size: Letter;
    margin: 1in 0.9in;
    @bottom-center { content: counter(page); font-family: 'Inter', sans-serif; font-size: 9pt; color: #888; }
  }
  html {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1c1917;
    line-height: 1.55;
  }
  body {
    max-width: 7.5in;
    margin: 0 auto;
    padding: 0;
  }
  h1 {
    font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
    font-size: 32pt;
    font-weight: 700;
    color: #1c1917;
    margin-top: 0;
    margin-bottom: 8pt;
    letter-spacing: -0.5pt;
    line-height: 1.1;
  }
  h2 {
    font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
    font-size: 20pt;
    font-weight: 600;
    color: #1c1917;
    margin-top: 32pt;
    margin-bottom: 12pt;
    letter-spacing: -0.3pt;
    line-height: 1.2;
    page-break-after: avoid;
  }
  h3 {
    font-family: 'Inter', -apple-system, sans-serif;
    font-size: 13pt;
    font-weight: 600;
    color: #1c1917;
    margin-top: 24pt;
    margin-bottom: 8pt;
    letter-spacing: 0;
    page-break-after: avoid;
  }
  p {
    margin-top: 0;
    margin-bottom: 12pt;
    text-align: left;
  }
  strong {
    font-weight: 600;
    color: #1c1917;
  }
  em {
    font-style: italic;
    color: #555;
  }
  hr {
    border: none;
    border-top: 1px solid #d4d4d4;
    margin: 32pt 0;
  }
  ul, ol {
    margin-top: 0;
    margin-bottom: 14pt;
    padding-left: 22pt;
  }
  li {
    margin-bottom: 4pt;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 16pt 0;
    font-size: 10pt;
    page-break-inside: avoid;
  }
  th, td {
    text-align: left;
    padding: 8pt 12pt 8pt 0;
    border-bottom: 1px solid #e4e4e4;
    vertical-align: top;
  }
  th {
    font-weight: 600;
    border-bottom: 1.5px solid #1c1917;
    padding-bottom: 6pt;
  }
  blockquote {
    border-left: 3px solid #d4d4d4;
    padding-left: 16pt;
    margin: 16pt 0;
    color: #444;
    font-style: italic;
  }
  code {
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    background: #f4f4f2;
    padding: 1pt 4pt;
    border-radius: 2pt;
    font-size: 10pt;
  }
  /* Lead paragraph styling for the subtitle line */
  body > p:first-of-type {
    font-size: 13pt;
    color: #555;
    margin-bottom: 28pt;
    line-height: 1.4;
  }
  /* Tighter spacing in tables */
  table p { margin: 0; }

  /* Print-friendly page breaks */
  h2 { page-break-before: auto; }
  table, blockquote, ul, ol { page-break-inside: avoid; }
</style>
</head>
<body>
{body}
</body>
</html>
"""

html_full = HTML_TEMPLATE.replace('{body}', html_body)
HTML_PATH.write_text(html_full, encoding='utf-8')
print(f"Wrote HTML: {HTML_PATH}")
print(f"  Size: {HTML_PATH.stat().st_size / 1024:.1f} KB")

# Convert HTML to PDF using Edge headless
import os, time

# Try Chrome first (more reliable on Windows for --print-to-pdf), then Edge.
candidates = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    os.path.expanduser(r'~\AppData\Local\Google\Chrome\Application\chrome.exe'),
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
]
browser = next((p for p in candidates if os.path.exists(p)), None)

if not browser:
    print("\nNo Chrome or Edge found. Open the HTML in any browser and use 'Print -> Save as PDF'.")
    raise SystemExit(0)

# Clean any existing PDF so we can detect a fresh write
if PDF_PATH.exists():
    PDF_PATH.unlink()

file_url = HTML_PATH.as_uri()
cmd = [
    browser,
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    f'--print-to-pdf={PDF_PATH}',
    '--no-pdf-header-footer',
    '--virtual-time-budget=5000',
    file_url
]
print(f"\nRunning headless print-to-PDF via: {browser}")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

# Wait briefly for the file to materialize
for _ in range(10):
    if PDF_PATH.exists():
        break
    time.sleep(0.3)

if PDF_PATH.exists():
    print(f"PDF generated: {PDF_PATH}")
    print(f"  Size: {PDF_PATH.stat().st_size / 1024:.1f} KB")
else:
    print("\nBrowser ran but PDF not found.")
    print(f"  stdout: {result.stdout[:500]}")
    print(f"  stderr: {result.stderr[:500]}")
    print(f"\nFallback: open {HTML_PATH} in a browser and use 'Print -> Save as PDF'.")
