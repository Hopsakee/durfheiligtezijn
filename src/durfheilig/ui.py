"""Gedeelde bouwstenen voor alle pagina's: stijl, menu, paginakader, afbeeldingen en de groepen die leiding zijn.

Staat los van `app.py` en `raadspel.py`, zodat die twee dit allebei kunnen gebruiken zonder elkaar te importeren.
"""

import contextvars
from functools import lru_cache
from urllib.parse import urlparse

from fasthtml.common import A, Details, Div, H1, H2, Header, I, Input, Label, Main, Nav, P, RedirectResponse, Script, Span, Summary, Title

from .data import DATA_DIR, Heilige

LEIDING_GROEPEN = {"admins", "durfte-leiding"}


def is_leiding(headers) -> bool:
    return bool(set((headers.get("remote-groups") or "").replace(" ", "").split(",")) & LEIDING_GROEPEN)


def naar(route: str = "/quiz") -> RedirectResponse:
    return RedirectResponse(route, status_code=303)


# The dark palette, written once: the dark-mode media query below and the tv screen (raadspel.py) both use it.
DONKER = ("--bg:#14161f;--kaart:#1f2230;--ink:#f4f1ea;--zacht:#a5a9bc;--rand:#32364a;--accent:#ff7a52;--accent-ink:#1a0d08;--accent-zacht:#3a2a27;"
          "--geel:#ffd35c;--fout:#ff8a80;--schaduw:0 2px 0 rgba(0,0,0,.3),0 10px 24px rgba(0,0,0,.25)")

CSS = """
:root{--bg:#fff6e9;--kaart:#fff;--ink:#1e2235;--zacht:#5b6178;--rand:#eadfcb;--accent:#e5522b;--accent-ink:#fff;--accent-zacht:#ffe6dc;--geel:#ffc93c;--fout:#c7352b;--schaduw:0 2px 0 rgba(30,34,53,.07),0 10px 24px rgba(30,34,53,.08)}
@media (prefers-color-scheme:dark){:root{""" + DONKER + """}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink)}
.top{position:sticky;top:0;z-index:5;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.7rem 16px;background:var(--bg)}
.merk{font-weight:800;letter-spacing:-.01em;font-size:1.05rem}.merk span{color:var(--accent)}
main{max-width:36rem;margin:0 auto;padding:.5rem 16px 4rem}
h1{font-size:clamp(1.65rem,6.5vw,2.2rem);line-height:1.15;letter-spacing:-.02em;font-weight:800;margin:.4rem 0 .8rem}
h2{font-size:1.25rem;line-height:1.25;font-weight:800;margin:1.4rem 0 .5rem}
p{margin:.5rem 0}.klein{font-size:.85rem;color:var(--zacht)}.fout{color:var(--fout);font-weight:700}
a{color:var(--accent)}
:focus-visible{outline:3px solid var(--geel);outline-offset:2px}
button,.knop,.keuze .vorm{display:flex;align-items:center;gap:.8rem;padding:.9rem 1.1rem;background:var(--kaart);border:2px solid var(--rand);border-radius:18px;box-shadow:var(--schaduw);transition:transform .08s ease,border-color .15s ease,background .15s ease}
button,.knop{width:100%;min-height:3.4rem;margin:.6rem 0;font:inherit;font-weight:700;text-align:left;color:var(--ink);text-decoration:none;cursor:pointer}
button:active,.knop:active{transform:translateY(2px) scale(.99);box-shadow:none}
button:hover,.knop:hover{border-color:var(--accent)}
button.hoofd{justify-content:center;text-align:center;background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-size:1.1rem;min-height:3.6rem}
button.sec,.knop.sec{background:transparent;box-shadow:none;border-style:dashed;font-weight:600;justify-content:center;color:var(--zacht)}
.knop .uitleg{display:block;font-weight:400;color:var(--zacht);font-size:.88rem}.knop b{display:block}
input[type=text],textarea,select{width:100%;padding:.9rem 1rem;font:inherit;color:var(--ink);background:var(--kaart);border:2px solid var(--rand);border-radius:14px}
input[type=text]:focus,textarea:focus,select:focus{border-color:var(--accent);outline:none}
label.veld{display:block;font-weight:700;margin:1rem 0 .3rem}
.verborgen{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none}
.keuze{display:block;margin:.5rem 0;cursor:pointer}
.keuze .vorm{font-weight:700}
.keuze:active .vorm{transform:translateY(2px)}.keuze:hover .vorm{border-color:var(--accent)}
.keuze input:checked + .vorm{border-color:var(--accent);background:var(--accent-zacht)}
.keuze input:checked + .vorm::after{content:"✓";margin-left:auto;color:var(--accent);font-size:1.3rem;font-weight:800}
.keuze input:focus-visible + .vorm{outline:3px solid var(--geel);outline-offset:2px}
.icoon{display:inline-flex;align-items:center;justify-content:center;flex:none;width:3rem;height:3rem;font-size:1.7rem;background:var(--accent-zacht);border-radius:50%}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 1rem}
.chips .keuze{margin:0}.chips .vorm{padding:.6rem .95rem;border-radius:999px;box-shadow:none;font-weight:600}.chips .vorm::after{display:none}
.chips input:checked + .vorm{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.stappen{display:flex;gap:.35rem;margin:.2rem 0 .3rem}.stappen i{flex:1;height:.4rem;border-radius:999px;background:var(--rand)}.stappen i.klaar{background:var(--accent)}
.balk{height:.7rem;border-radius:999px;background:var(--rand);overflow:hidden;margin:.3rem 0 .4rem}.balk i{display:block;height:100%;background:linear-gradient(90deg,var(--geel),var(--accent));border-radius:999px;transition:width .3s ease}
.voortgang{color:var(--zacht);font-size:.9rem;font-weight:600;margin:.2rem 0}
.hero{margin:.5rem 0 1rem;padding:1.2rem;border-radius:24px;background:var(--accent-zacht);border:2px solid var(--rand)}
.hero .groot{font-size:2.6rem;line-height:1}
.lijst{list-style:none;padding:0;margin:.8rem 0}.lijst li{display:flex;gap:.8rem;align-items:flex-start;margin:.7rem 0}.lijst .icoon{width:2.6rem;height:2.6rem;font-size:1.3rem}
.kaart{background:var(--kaart);border:2px solid var(--rand);border-radius:24px;padding:1.1rem;margin:1.2rem 0;box-shadow:var(--schaduw)}
.kaart img{display:block;width:100%;max-height:24rem;object-fit:contain;background:#f1eadb;border-radius:16px}
.kaart h2{margin-top:.8rem;font-size:1.5rem}
.kaart.gekozen{border:6px solid var(--accent);background:var(--accent-zacht)}
.badge{display:inline-block;margin-bottom:.6rem;background:var(--accent);color:var(--accent-ink);border-radius:999px;padding:.25rem .9rem;font-weight:800;font-size:.9rem}
.bubbel{position:relative;margin:.9rem 0;padding:.9rem 1rem;background:var(--accent-zacht);border-radius:18px;border:2px solid var(--rand)}
.bubbel::before{content:"Voor jou";display:block;font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin-bottom:.2rem}
details:not(.menu){margin:.6rem 0;padding:.7rem 1rem;border:2px solid var(--rand);border-radius:16px;background:var(--kaart)}summary{cursor:pointer;font-weight:700}
details:not(.menu)[open] summary{margin-bottom:.4rem}
#laden{position:fixed;inset:0;background:color-mix(in srgb,var(--bg) 94%,transparent);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2rem;z-index:20}#laden[hidden]{display:none}
.draai{width:3.6rem;height:3.6rem;border:.45rem solid var(--rand);border-top-color:var(--accent);border-radius:50%;animation:draai 1s linear infinite;margin-bottom:1rem}@keyframes draai{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition:none!important}}
.menu{position:relative}.menu summary{list-style:none;cursor:pointer;background:var(--kaart);border:2px solid var(--rand);border-radius:999px;padding:.45rem 1rem;font-weight:800;box-shadow:var(--schaduw)}
.menu summary::-webkit-details-marker{display:none}.menu[open] summary{border-color:var(--accent)}
.menu nav{position:absolute;right:0;top:calc(100% + .4rem);min-width:16rem;background:var(--kaart);border:2px solid var(--rand);border-radius:18px;padding:.4rem;box-shadow:var(--schaduw)}
.menu nav a{display:block;padding:.75rem .9rem;color:var(--ink);text-decoration:none;border-radius:12px;font-weight:600}.menu nav a:active,.menu nav a:hover{background:var(--accent-zacht)}
table{width:100%;border-collapse:collapse;font-size:.9rem}td,th{padding:.5rem .4rem;border-bottom:1px solid var(--rand);text-align:left}
@media print{.geen-print,#laden,.top{display:none!important}body{background:#fff;color:#000}.tegel{break-inside:avoid}}
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

# The interest chips: only a few may be ticked; the counter shows how many are. Limits come from data-min / data-max on `.chips`.
CHIPSSCRIPT = """
(function () {
  var wrap = document.querySelector('.chips'), tel = document.getElementById('telling');
  if (!wrap) return;
  var min = +wrap.dataset.min, max = +wrap.dataset.max, vakjes = [].slice.call(wrap.querySelectorAll('input'));
  function bijwerken() {
    var n = vakjes.filter(function (x) { return x.checked; }).length;
    vakjes.forEach(function (x) { x.disabled = !x.checked && n >= max; });
    tel.textContent = n + ' gekozen (kies ' + min + ' of ' + max + ')';
  }
  vakjes.forEach(function (x) { x.addEventListener('change', bijwerken); });
  bijwerken();
})();
"""


# Who is looking, for the menu on every page. Set once per request by the (async) login check, so that code running after it
# in the same request sees it; the pages are built far from the request. `profiel` looks the viewer up, but only when a menu is built.
KIJKER: contextvars.ContextVar = contextvars.ContextVar("kijker", default=None)

def _iedereen(k) -> bool:
    return True


def _leiding(k) -> bool:
    return bool(k.get("leiding"))


def _heeft_match(k) -> bool:
    return bool(k["profiel"]().get("heeft_match"))


def _mag_opnieuw(k) -> bool:
    """After the first step, and only until the game starts (the same rule `reset_invulling` enforces)."""
    p = k["profiel"]()
    return p.get("stap") not in (None, "welkom") and not p.get("spel_gestart")


# (href, title, explanation for the start page, group on the start page, who sees it). The menu and the start page both come from this list.
PAGINAS = [
    ("/menu", "Alle pagina's", None, "kind", _iedereen),
    ("/quiz", "Mijn quiz", None, "kind", _iedereen),
    ("/mijn", "Mijn heilige", "Lees je drie heiligen en je keuze nog eens terug.", "kind", _heeft_match),
    ("/spel", "Het raadspel", "Stem op je telefoon tijdens het spel op de middag.", "kind", _iedereen),
    ("/quiz/opnieuw", "Quiz opnieuw invullen", "Wis je antwoorden en begin opnieuw. Je gekozen heilige komt dan weer vrij.", "kind", _mag_opnieuw),
    ("/beheer", "Overzicht en uitleg lezen", "Wie is klaar, welke uitleg is gemarkeerd. Een uitleg openen telt als lezen.", "leiding", _leiding),
    ("/beheer/spel", "Het raadspel bedienen", "Het spel starten en de rondes doorlopen, vanaf je eigen scherm.", "leiding", _leiding),
    ("/beheer/tv", "Tv-scherm", "Open dit op de tv; het ververst zichzelf.", "leiding", _leiding),
    ("/beheer/print", "Printversie van het bord", "Een genummerd bord op papier, voor als de app uitvalt.", "leiding", _leiding),
    ("/beheer/export", "Alles downloaden", "Alle antwoorden en het spel als JSON.", "leiding", _leiding),
]


def kijker() -> dict:
    return KIJKER.get() or {}


def zichtbaar() -> list[tuple]:
    """The pages this viewer may use. A page's rule runs only for that page, so the viewer is looked up only when a rule needs it."""
    k = kijker()
    return [p for p in PAGINAS if p[4](k)]


def menu_items() -> list[tuple[str, str]]:
    return [(h, t) for h, t, *_ in zichtbaar()] + list(kijker().get("extra", ()))


def keuzekaart(soort: str, naam: str, waarde: str, tekst: str, **kw):
    """A tappable choice (radio or checkbox) drawn as a card or chip; the real input is hidden but stays reachable by keyboard."""
    return Label(Input(type=soort, name=naam, value=waarde, cls="verborgen", **kw), Span(tekst, cls="vorm"), cls="keuze")


QUIZSTAPPEN = 5   # you, the questions, the interests, a bit about you, your saint


def pagina(titel: str, *inhoud, toon_menu: bool = True, stap: int | None = None, vraag: tuple[int, int] | None = None, fout: str = ""):
    """The frame of every page: brand and menu on top, then (in the quiz) the step dots and a progress bar, then the title.

    `stap` is the quiz step (1 to 5); `vraag` is (questions answered, questions in all) and draws the bar and "Vraag 3 van 12"."""
    kop = Header(Div(Span("✦ "), "Durf heilig te zijn", cls="merk"),
                 Details(Summary("☰ Menu"), Nav(*[A(t, href=h) for h, t in menu_items()]), cls="menu geen-print"), cls="top geen-print") if toon_menu else ""
    laden = Div(Div(cls="draai"), P("Even geduld…", style="font-size:1.2rem;font-weight:700"), id="laden", hidden=True, role="status",
                onclick="this.hidden=true")
    boven = []
    if stap:
        boven.append(Div(*[I(cls="klaar" if n <= stap else "") for n in range(1, QUIZSTAPPEN + 1)], cls="stappen", role="img", aria_label=f"Stap {stap} van {QUIZSTAPPEN}"))
    if vraag:
        gedaan, totaal = vraag
        boven += [Div(I(style=f"width:{100 * gedaan / totaal:.0f}%"), cls="balk"), P(f"Vraag {gedaan + 1} van {totaal}", cls="voortgang")]
    return Title(f"{titel} · Durf heilig te zijn"), kop, Main(*boven, H1(titel), *([P(fout, cls="fout")] if fout else []), *inhoud, laden, Script(LAADSCRIPT))


TOEGESTANE_LINKHOSTS = {"nl.wikipedia.org", "en.wikipedia.org", "commons.wikimedia.org"}


def info(h: Heilige) -> list:
    """Alles wat een jongere over deze heilige erbij mag lezen. Bewust zonder de notities voor de leiding."""
    r = h.record
    uit = []
    if r.get("waarom_voorbeeld"):
        uit += [H2("Waarom een voorbeeld?"), P(r["waarom_voorbeeld"])]
    if r.get("waarom_heilig"):
        uit += [H2("Waarom heilig?"), P(r["waarom_heilig"])]
    if r.get("haakjes"):
        uit.append(H2("Verhalen over deze heilige"))
        for x in r["haakjes"]:
            soort = x.get("soort") or ""
            label = [x["kort"], *([Span(f" ({soort})", cls="klein")] if soort else [])]
            uit.append(Details(Summary(*label), P(x["meer"])) if x.get("meer") else P(*label))
    if r.get("wat_er_nog_van_over_is"):
        uit += [H2("Wat er nog van over is"), P(r["wat_er_nog_van_over_is"])]
    if r.get("begrippen"):
        uit.append(H2("Woorden uitgelegd"))
        uit += [Details(Summary(b["term"]), P(b["uitleg"])) for b in r["begrippen"]]
    links = [x for x in r.get("lees_zelf", []) if urlparse(x.get("url", "")).scheme == "https" and "\\" not in x["url"]
             and urlparse(x["url"]).hostname in TOEGESTANE_LINKHOSTS]
    if links:
        uit += [H2("Zelf verder lezen"), *[P(A(x["titel"], href=x["url"], target="_blank", rel="noopener noreferrer")) for x in links]]
    return uit
