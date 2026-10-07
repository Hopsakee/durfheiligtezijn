"""Add a Commons image (with maker and licence) to each saint card in the review HTML.

Usage: python pipeline/add_images.py <review.html> data/heiligen.json <out.html>

Images load straight from Wikimedia Commons via Special:FilePath. Idempotent:
a page that already has images is left unchanged.
"""
import sys, json, re, html
from urllib.parse import quote
src, js, out = sys.argv[1:4]
h = open(src, encoding="utf-8").read()
if 'class="pic"' in h:
    open(out, "w", encoding="utf-8").write(h)
    sys.exit("page already has images; copied unchanged")
recs = {r["qid"]: r for r in json.load(open(js, encoding="utf-8"))["records"]}
css = "figure.pic{margin:8px 0 12px}figure.pic img{max-width:100%;max-height:340px;border-radius:8px;display:block}figure.pic figcaption{font-size:.75rem;color:var(--mut)}"
h = h.replace("</style>", css + "</style>", 1)
n = 0
def add(m):
    global n
    r = recs.get(m.group(1))
    a = (r or {}).get("afbeelding") or {}
    if not a.get("bestand"):
        return m.group(0)
    f = a["bestand"].replace(" ", "_")
    img = "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(f) + "?width=600"
    cap = f'{html.escape(a.get("maker") or "onbekend")} · {html.escape(a.get("licentie") or "")} · <a href="{html.escape(a["url"])}" target="_blank" rel="noopener">bron</a>'
    n += 1
    return m.group(0) + f'<figure class="pic"><img loading="lazy" src="{html.escape(img)}" alt="{html.escape(r["naam"])}"><figcaption>{cap}</figcaption></figure>'
h = re.sub(r'<section id="h\d+" class="card" data-q="(Q\d+)"><h2>.*?</h2>', add, h, flags=re.S)
open(out, "w", encoding="utf-8").write(h)
print("figures added:", n)
