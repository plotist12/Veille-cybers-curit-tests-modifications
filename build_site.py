# build_site.py
# Transforme output/*.md -> docs/YYYY-MM-DD.html + docs/index.html (simple & propre)

import os, re, glob, pathlib
from datetime import date

try:
    import markdown  # pip install markdown
except ImportError:
    raise SystemExit("Installe d'abord 'markdown' : pip install markdown")

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "output"
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / ".nojekyll").write_text("", encoding="utf-8")  # désactiver Jekyll

STYLE = """
<style>
:root{--bg:#0b1020;--card:#121a34;--text:#e6e9f3;--muted:#9aa3b2;--accent:#6aa3ff;--line:#1d274d}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);
font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial}
a{color:var(--accent);text-decoration:none}
header,footer{border-bottom:1px solid var(--line);padding:18px 16px}
footer{border-top:1px solid var(--line);border-bottom:0;margin-top:20px}
.wrap{max-width:1000px;margin:0 auto}
h1{margin:0 0 6px;font-size:28px}
.sub{color:var(--muted)}
.grid{display:grid;grid-template-columns:1fr;gap:14px;padding:18px 0 40px}
@media(min-width:760px){.grid{grid-template-columns:1fr 1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.25)}
.card h2{margin:0 0 10px;font-size:17px}
.card .meta{color:var(--muted);font-size:12px;margin:-4px 0 10px}
ul{margin:0 0 0 18px}.index ul{line-height:1.9}
.btn{display:inline-block;padding:9px 12px;background:#1a2345;border:1px solid #263367;
color:#cfe0ff;border-radius:12px;margin-right:8px}
.topnav{margin-top:8px}
</style>
"""

HTML = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{style}</head><body>
<header><div class="wrap">
  <h1>{h1}</h1>
  <div class="topnav"><a class="btn" href="./index.html">Accueil</a></div>
  <div class="sub">{sub}</div>
</div></header>
<main><div class="wrap">{content}</div></main>
<footer><div class="wrap">Publié automatiquement via GitHub Pages.</div></footer>
</body></html>"""

md = markdown.Markdown(extensions=["extra", "tables"])

def split_by_article(md_text: str):
    lines = md_text.splitlines()
    blocks, cur = [], []
    for ln in lines:
        if ln.startswith("## "):
            if cur: blocks.append("\n".join(cur).strip())
            cur = [ln]
        else:
            if cur: cur.append(ln)
    if cur: blocks.append("\n".join(cur).strip())
    return blocks

def render_card(md_segment: str) -> str:
    html = markdown.markdown(md_segment, extensions=["extra", "tables"])
    # meta en italique "*Source : ... | Publication : ...*"
    meta_html = ""
    m = re.search(r"<em>(.*?)</em>", html)
    if m:
        raw = re.sub("<.*?>", "", m.group(1))
        html = html.replace(m.group(0), "")
        meta_html = f'<div class="meta">{raw}</div>'
    return f'<article class="card">{meta_html}{html}</article>'

def build_day(md_path: pathlib.Path, day: str):
    text = md_path.read_text(encoding="utf-8")
    cards = [render_card(seg) for seg in split_by_article(text)]
    grid = '<section class="grid">' + "".join(cards or ['<p class="sub">Aucun article.</p>']) + "</section>"
    page = HTML.format(title=f"Veille – {day}", h1=f"Veille – {day}", sub="Résumé du jour", content=grid, style=STYLE)
    (DOCS / f"{day}.html").write_text(page, encoding="utf-8")

def build_index():
    days = []
    for p in DOCS.glob("*.html"):
        if p.name in ("index.html",): continue
        if re.match(r"\d{4}-\d{2}-\d{2}\.html$", p.name): days.append(p.stem)
    days.sort(reverse=True)
    lis = "".join(f'<li><a href="./{d}.html">{d}</a></li>' for d in days) or "<li>(vide)</li>"
    content = f'<section class="index"><h2>Jours disponibles</h2><ul>{lis}</ul></section>'
    page = HTML.format(title="Veille – Index", h1="Veille – index", sub="Pages générées", content=content, style=STYLE)
    (DOCS / "index.html").write_text(page, encoding="utf-8")

def main():
    today = date.today().isoformat()
    # construire la page du jour si le fichier existe
    p = OUT / f"{today}.md"
    if p.exists(): build_day(p, today)
    # reconstruire l’index
    build_index()
    print("OK: docs/index.html + docs/YYYY-MM-DD.html")

if __name__ == "__main__":
    main()
