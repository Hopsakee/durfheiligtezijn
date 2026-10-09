"""Gedeelde bouwstenen voor alle pagina's: stijl, menu, paginakader, afbeeldingen en de groepen die leiding zijn.

Staat los van `app.py` en `raadspel.py`, zodat die twee dit allebei kunnen gebruiken zonder elkaar te importeren.
"""

import contextvars
from functools import lru_cache

from fasthtml.common import A, Details, Div, Nav, P, RedirectResponse, Script, Summary, Titled

from .data import DATA_DIR, Heilige

LEIDING_GROEPEN = {"admins", "durfte-leiding"}


def is_leiding(headers) -> bool:
    return bool(set((headers.get("remote-groups") or "").replace(" ", "").split(",")) & LEIDING_GROEPEN)


def naar(route: str = "/quiz") -> RedirectResponse:
    return RedirectResponse(route, status_code=303)


CSS = """
:root{--bg:#fffaf0;--ink:#2a2a2a;--accent:#b4452c;--kaart:#fff;--rand:#e5d9c3}
*{box-sizing:border-box}body{margin:0;font:18px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
main{max-width:34rem;margin:0 auto;padding:1rem 16px 3rem}h1{font-size:1.5rem}h2{font-size:1.2rem;margin:.2rem 0}
button,.knop{display:block;width:100%;padding:1rem;margin:.6rem 0;font:inherit;font-weight:600;text-align:left;
border:2px solid var(--rand);border-radius:14px;background:var(--kaart);color:var(--ink);text-decoration:none;cursor:pointer}
button.hoofd{background:var(--accent);border-color:var(--accent);color:#fff;text-align:center}
.icoon{font-size:1.6rem;margin-right:.6rem}input[type=text],textarea{width:100%;padding:.8rem;font:inherit;border:2px solid var(--rand);border-radius:12px}
.kaart{background:var(--kaart);border:2px solid var(--rand);border-radius:14px;padding:1rem;margin:1rem 0}
.kaart img{display:block;width:100%;max-height:24rem;object-fit:contain;background:#f1eadb;border-radius:10px}.klein{font-size:.8rem;color:#666}
.kaart.gekozen{border:6px solid var(--accent);background:#fff4ee}.badge{display:inline-block;background:var(--accent);color:#fff;border-radius:999px;padding:.2rem .8rem;font-weight:700;font-size:.9rem}
details{margin:.5rem 0;padding:.6rem .8rem;border:1px solid var(--rand);border-radius:10px;background:var(--kaart)}summary{cursor:pointer;font-weight:600}
#laden{position:fixed;inset:0;background:rgba(255,250,240,.94);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2rem;z-index:10}#laden[hidden]{display:none}
.draai{width:3.2rem;height:3.2rem;border:.4rem solid var(--rand);border-top-color:var(--accent);border-radius:50%;animation:draai 1s linear infinite}@keyframes draai{to{transform:rotate(360deg)}}
.menu{position:fixed;top:.5rem;right:.5rem;z-index:5}.menu summary{list-style:none;cursor:pointer;background:var(--accent);color:#fff;border-radius:999px;padding:.4rem 1rem;font-weight:700}
.menu summary::-webkit-details-marker{display:none}.menu nav{position:absolute;right:0;margin-top:.4rem;min-width:15rem;background:#fff;border:2px solid var(--rand);border-radius:12px;padding:.4rem;box-shadow:0 4px 14px rgba(0,0,0,.15)}
.menu nav a{display:block;padding:.7rem .8rem;color:var(--ink);text-decoration:none;border-radius:8px}.menu nav a:active{background:#f1eadb}
main{padding-top:3rem}
.voortgang{color:#666;font-size:.9rem}label.optie{display:block;padding:.8rem;margin:.4rem 0;border:2px solid var(--rand);border-radius:12px;background:var(--kaart)}
table{width:100%;border-collapse:collapse;font-size:.9rem}td,th{padding:.4rem;border-bottom:1px solid var(--rand);text-align:left}
@media print{.geen-print,#laden{display:none!important}body{background:#fff}.tegel{break-inside:avoid}}
"""


@lru_cache(maxsize=None)
def _lokaal(bestand: str) -> bool:
    return (DATA_DIR / "afbeeldingen" / bestand).is_file()


def afbeelding_url(h: Heilige) -> str:
    """Lokaal bestand als dat er is (data/afbeeldingen), anders Wikimedia Commons."""
    bestand = h.record["afbeelding"]["bestand"]
    if _lokaal(bestand):
        return f"/img/{bestand}"
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{bestand.replace(' ', '_')}?width=640"


# Some steps wait for Gemini for several seconds. The cover shows that the app is working and blocks a second tap.
LAADSCRIPT = """
document.addEventListener('submit', function (e) {
  var bron = e.submitter && e.submitter.getAttribute('data-laad') || e.target.getAttribute('data-laad');
  if (!bron) return;
  var o = document.getElementById('laden');
  o.querySelector('p').textContent = bron;
  o.hidden = false;
  setTimeout(function () { o.hidden = true; }, 60000);   // a cancelled navigation must never leave the kid stuck
}, true);
window.addEventListener('pageshow', function () { document.getElementById('laden').hidden = true; });
"""


# Who is looking, for the menu on every page. Set once per request by the (async) login check, so that code running after it
# in the same request sees it; the pages are built far from the request. `profiel` looks the viewer up, but only when a menu is built.
KIJKER: contextvars.ContextVar = contextvars.ContextVar("kijker", default=None)

# (href, title, explanation for the start page, only for leaders). The menu and the start page both come from this list.
PAGINAS = [
    ("/menu", "Alle pagina's", None, False),
    ("/quiz", "Mijn quiz", None, False),
    ("/mijn", "Mijn heilige", "Lees je drie heiligen en je keuze nog eens terug.", False),
    ("/spel", "Het raadspel", "Stem op je telefoon tijdens het spel op de middag.", False),
    ("/beheer", "Overzicht en uitleg lezen", "Wie is klaar, welke uitleg is gemarkeerd. Een uitleg openen telt als lezen.", True),
    ("/beheer/spel", "Het raadspel bedienen", "Het spel starten en de rondes doorlopen, vanaf je eigen scherm.", True),
    ("/beheer/tv", "Tv-scherm", "Open dit op de tv; het ververst zichzelf.", True),
    ("/beheer/print", "Printversie van het bord", "Een genummerd bord op papier, voor als de app uitvalt.", True),
    ("/beheer/export", "Alles downloaden", "Alle antwoorden en het spel als JSON.", True),
]


def kijker() -> dict:
    return KIJKER.get() or {}


def mag_zien(href: str, leiding_only: bool) -> bool:
    k = kijker()
    if leiding_only and not k.get("leiding"):
        return False
    return href != "/mijn" or bool(k.get("profiel", dict)().get("heeft_match"))


def menu_items() -> list[tuple[str, str]]:
    return [(h, t) for h, t, _, l in PAGINAS if mag_zien(h, l)] + list(kijker().get("extra", ()))


def pagina(titel: str, *inhoud, voortgang: str | None = None, toon_menu: bool = True):
    menu = Details(Summary("☰ Menu"), Nav(*[A(t, href=h) for h, t in menu_items()]), cls="menu geen-print") if toon_menu else ""
    laden = Div(Div(cls="draai"), P("Even geduld…", style="font-size:1.2rem;font-weight:600"), id="laden", hidden=True, role="status",
                onclick="this.hidden=true")
    return Titled(titel, menu, *([P(voortgang, cls="voortgang")] if voortgang else []), *inhoud, laden, Script(LAADSCRIPT))
