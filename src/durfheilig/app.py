"""De quiz-app voor thuis (fase 4): FastHTML, één scherm per stap, voortgang per stap bewaard.

De hele app zit achter Authelia; Caddy stuurt `Remote-User` mee. Er is geen eigen inlog.
De app leest alleen `Remote-User` (en `Remote-Groups` voor /beheer), nooit naam of e-mailadres.
Elke stap is een gewoon formulier met een POST en een redirect, zodat een telefoon die op slot
gaat of even geen bereik heeft niets verliest.
"""

import hashlib
import json
import os
import random
from urllib.parse import urlparse
from pathlib import Path

from fasthtml.common import (A, Button, Details, Div, FastHTML, FileResponse, Form, H1, H2, Img, Input, Label, P, RedirectResponse,
                             Response, Small, Span, Script, Style, Summary, Table, Td, Th, Titled, Tr, Textarea)

from . import db as spel
from . import raadspel
from .data import DATA_DIR, Heilige, Vragenbank, laad_heiligen, laad_vragen
from .llm import Llm, Uitslag, finale, llm_uit_omgeving, vervolgvragen, Vervolgvraag
from .scoring import VOORKEUR_GESLACHT, kies_vragen, profiel, rangschik

MAX_OPEN = 200
MAX_NICKNAME = 20
LEIDING_GROEPEN = {"admins", "durfte-leiding"}
STAPPEN = ("welkom", "voorkeur", "vragen", "interesses", "open", "vervolg", "keuze", "klaar")

CSS = raadspel.RAAD_CSS + """
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
.voortgang{color:#666;font-size:.9rem}label.optie{display:block;padding:.8rem;margin:.4rem 0;border:2px solid var(--rand);border-radius:12px;background:var(--kaart)}
table{width:100%;border-collapse:collapse;font-size:.9rem}td,th{padding:.4rem;border-bottom:1px solid var(--rand);text-align:left}
"""


def afbeelding_url(h: Heilige) -> str:
    """Lokaal bestand als dat er is (data/afbeeldingen), anders Wikimedia Commons."""
    bestand = h.record["afbeelding"]["bestand"]
    if (DATA_DIR / "afbeeldingen" / bestand).is_file():
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


def pagina(titel: str, *inhoud, voortgang: str | None = None):
    laden = Div(Div(cls="draai"), P("Even geduld…", style="font-size:1.2rem;font-weight:600"), id="laden", hidden=True, role="status",
                onclick="this.hidden=true")
    return Titled(titel, *( [P(voortgang, cls="voortgang")] if voortgang else []), *inhoud, laden, Script(LAADSCRIPT))


def knop_formulier(actie: str, *velden, tekst: str = "Verder", laad: str | None = None, **hidden):
    extra = {"data-laad": laad} if laad else {}
    return Form(*velden, *[Input(type="hidden", name=k, value=v) for k, v in hidden.items()],
                Button(tekst, cls="hoofd", type="submit"), method="post", action=actie, **extra)


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
            soort = {"feit": "feit", "legende": "legende"}.get(x.get("soort"), x.get("soort") or "")
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


def maak_app(db, heiligen: list[Heilige], vragen: Vragenbank, llm: Llm | None, rng: random.Random | None = None) -> FastHTML:
    rng = rng or random.Random()
    per_qid = {h.qid: h for h in heiligen}
    per_vraag = {v.id: v for v in vragen.vragen}

    def auth(req):
        gebruiker = (req.headers.get("remote-user") or "").strip()
        if not gebruiker:
            return Response("Niet ingelogd.", status_code=401)
        req.scope["gebruiker"] = gebruiker

    from fasthtml.common import Beforeware
    app = FastHTML(before=Beforeware(auth, skip=[r"/health", r"/img/.*"]), hdrs=(Style(CSS),), secret_key=os.urandom(16).hex(),
                   pico=False)
    route = app.route

    def leiding(req) -> bool:
        groepen = set((req.headers.get("remote-groups") or "").replace(" ", "").split(","))
        return bool(groepen & LEIDING_GROEPEN)

    def leiding_link(req):
        """Begeleiders spelen zelf ook mee; het overzicht is voor hen een klik weg."""
        return Div(A("Overzicht voor begeleiders", href="/beheer", cls="knop"), cls="klein") if leiding(req) else ""

    def wie(req) -> tuple[dict, dict]:
        sp = spel.speler_voor(db, req.scope["gebruiker"])
        return sp, spel.invulling(db, sp["id"])

    def naar(stap_route: str = "/"):
        return RedirectResponse(stap_route, status_code=303)

    def kandidaten_voor(sp: dict, inv: dict, afgewezen=()) -> list[Heilige]:
        p = profiel(inv["antwoorden"], vragen)
        weg = spel.gekozen_heiligen(db, behalve_speler=sp["id"]) | set(afgewezen)
        top = rangschik(p, inv["interesses"], heiligen, inv["voorkeur"], uitsluiten=weg, n=12, interesse_lijst=vragen.interesses)
        if len(top) < 3:   # rejections must never leave the pool empty: let rejected saints back in
            weg = spel.gekozen_heiligen(db, behalve_speler=sp["id"])
            top = rangschik(p, inv["interesses"], heiligen, inv["voorkeur"], uitsluiten=weg, n=12, interesse_lijst=vragen.interesses)
        return [h for h, _ in top]

    def maak_vervolg(sp: dict, inv: dict, afgewezen=()) -> None:
        kand = kandidaten_voor(sp, inv, afgewezen)
        p = profiel(inv["antwoorden"], vragen)
        uit, _ = vervolgvragen(llm, p, inv["interesses"], inv["open_antwoorden"], kand, vragen, set(inv["antwoorden"]))
        spel.bewaar(db, sp["id"], kandidaten=[h.qid for h in kand], vervolg=[v.__dict__ for v in uit],
                    vervolg_antwoorden={}, stap="vervolg")

    def maak_match(sp: dict, inv: dict) -> None:
        m = spel.match_van(db, sp["id"])
        afgewezen = m["afgewezen"] if m else {}
        kand = kandidaten_voor(sp, inv, afgewezen)
        vervolg = [Vervolgvraag(**{**v, "stijgt_bij_min": tuple(v["stijgt_bij_min"]), "stijgt_bij_plus": tuple(v["stijgt_bij_plus"])})
                   for v in inv["vervolg"]]
        p = profiel(inv["antwoorden"], vragen)
        uit: Uitslag = finale(llm, p, inv["interesses"], inv["open_antwoorden"], kand, vervolg, inv["vervolg_antwoorden"], afgewezen)
        top3 = []
        for k in uit.keuzes:
            h = per_qid[k.qid]
            top3.append({"qid": h.qid, "naam": h.naam, "uitleg": k.uitleg, "levensverhaal": h.record.get("levensverhaal", ""),
                         "afbeelding": afbeelding_url(h),
                         "credit": f"{h.record['afbeelding'].get('maker', '')}, {h.record['afbeelding'].get('licentie', '')}"})
        spel.bewaar_match(db, sp["id"], top3, uit.door_llm, uit.markering, afgewezen)
        spel.bewaar(db, sp["id"], stap="keuze")

    # ------------------------------------------------------------------ schermen

    def scherm_welkom(sp, inv, fout=""):
        return pagina("Welkom!",
            P("Je gaat een heilige zoeken die bij jou past. Het duurt ongeveer 5 tot 7 minuten."),
            P("Spelregels: je gebruikt een bijnaam, je vertelt alleen wat je ook aan de groep zou vertellen, en op de middag gaan we raden wie welke heilige heeft."),
            P(fout, style="color:#b00") if fout else "",
            knop_formulier("/welkom", Label("Kies een bijnaam", Input(type="text", name="nickname", maxlength=MAX_NICKNAME, required=True,
                                                                         value=sp["nickname"] or "")), tekst="Beginnen"))

    def scherm_voorkeur(sp, inv):
        return pagina("Jouw heilige",
            P("Mag je heilige een man, een vrouw, of maakt het niet uit?"),
            *[Form(Input(type="hidden", name="voorkeur", value=v), Button(v.capitalize(), type="submit"), method="post", action="/voorkeur")
              for v in VOORKEUR_GESLACHT])

    def scherm_vraag(sp, inv):
        klaar = len(inv["antwoorden"])
        vid = next(v for v in inv["vraag_ids"] if v not in inv["antwoorden"])   # vraag_ids is the one source of the count
        v = per_vraag[vid]
        kanten = [("min", v.min), ("plus", v.plus)]
        if int(hashlib.sha256(f"{sp['id']}{vid}".encode()).hexdigest(), 16) % 2:
            kanten.reverse()
        return pagina(v.vraag, voortgang=f"Vraag {klaar + 1} van {len(inv['vraag_ids'])}", *[
            Form(Input(type="hidden", name="vid", value=vid), Input(type="hidden", name="kant", value=k),
                 Button(Span(a["icoon"], cls="icoon"), a["tekst"], type="submit"), method="post", action="/vraag")
            for k, a in kanten])

    def scherm_interesses(sp, inv, fout=""):
        iv = vragen.interessevraag
        return pagina(iv["vraag"], P(f"Kies {iv['min_keuzes']} of {iv['max_keuzes']}."), P(fout, style="color:#b00") if fout else "",
            knop_formulier("/interesses", *[
                Label(Input(type="checkbox", name="interesse", value=o["interesse"]), f" {o['icoon']} {o['interesse']}", cls="optie")
                for o in iv["opties"]]))

    def scherm_open(sp, inv):
        return pagina("Nog twee dingen over jou",
            P("Een zin is genoeg. Je mag ook overslaan."),
            knop_formulier("/open",
                Label("Waar ben je stiekem goed in?", Textarea(name="a1", maxlength=MAX_OPEN, rows=2)),
                Label("Waar kun je je echt over opwinden?", Textarea(name="a2", maxlength=MAX_OPEN, rows=2)),
                laad="We bedenken drie vragen speciaal voor jou…"))

    def scherm_vervolg(sp, inv):
        return pagina("Nog drie vragen", P("Zo vinden we jouw heilige nog beter."),
            Form(*[Div(H2(v["vraag"]),
                       *[Label(Input(type="radio", name=v["id"], value=k, required=True), f" {v[k]}", cls="optie") for k in ("min", "plus")])
                   for v in inv["vervolg"]],
                 Button("Verder", cls="hoofd", type="submit"), method="post", action="/vervolg",
                 **{"data-laad": "We zoeken de heiligen die bij jou passen…"}))

    def kaarten(m, keuze=False, eigen=None):
        out = []
        # Your own choice goes first and stands out; the other two follow in their original order.
        for h in sorted(m["top3"], key=lambda h: h["qid"] != eigen):
            gekozen = eigen == h["qid"]
            out.append(Div(
                *([Span("✔ Jouw heilige", cls="badge")] if gekozen else []),
                Img(src=h["afbeelding"], alt=h["naam"]), Small(f"Foto: {h['credit']}", cls="klein"),
                H2(h["naam"]), P(h["levensverhaal"]), P(h["uitleg"]),
                A(f"Meer over {h['naam']}", href=f"/heilige/{h['qid']}", cls="knop"),
                *([Label(Input(type="radio", name="gekozen", value=h["qid"], required=True), " Deze past bij mij", cls="optie"),
                   Label("Deze niet, want… (mag leeg)", Input(type="text", name=f"niet_{h['qid']}", maxlength=MAX_OPEN))] if keuze else []),
                cls="kaart gekozen" if gekozen else "kaart"))
        return out

    def scherm_keuze(sp, inv):
        m = spel.match_van(db, sp["id"])
        extra = [] if inv["extra_ronde"] else [Button("Er past er geen bij mij", type="submit", formaction="/geen-past", formnovalidate=True,
                                          **{"data-laad": "We zoeken nieuwe vragen en heiligen voor je…"})]
        return pagina("Drie heiligen voor jou", P("Kies de heilige die het best bij je past."),
            Form(*kaarten(m, keuze=True), Label("Deze past bij mij, want…", Textarea(name="want", maxlength=MAX_OPEN, rows=2)),
                 Button("Dit is mijn heilige", cls="hoofd", type="submit"), *extra, method="post", action="/keuze"))

    def scherm_klaar(sp, inv):
        return pagina("Bedankt!", H1("Houd je heilige geheim tot de middag!"),
                      P("Zonder geheimhouding valt het raadspel om."), A("Lees je heilige nog eens terug", href="/mijn", cls="knop"),
                      A("Naar het raadspel", href="/spel", cls="knop"))

    SCHERMEN = {"welkom": scherm_welkom, "voorkeur": scherm_voorkeur, "vragen": scherm_vraag, "interesses": scherm_interesses,
                "open": scherm_open, "vervolg": scherm_vervolg, "keuze": scherm_keuze, "klaar": scherm_klaar}

    # ------------------------------------------------------------------ routes

    @route("/health")
    def health():
        return "ok"

    @route("/img/{naam}")
    def img(naam: str):
        pad = (DATA_DIR / "afbeeldingen" / naam).resolve()
        if (DATA_DIR / "afbeeldingen").resolve() not in pad.parents or not pad.is_file():
            return Response("Niet gevonden.", status_code=404)
        return FileResponse(pad)

    @route("/")
    def get(req):
        sp, inv = wie(req)
        return SCHERMEN[inv["stap"]](sp, inv), leiding_link(req)

    @route("/welkom", methods=["post"])
    def post_welkom(req, nickname: str = ""):
        sp, inv = wie(req)
        naam = nickname.strip()[:MAX_NICKNAME]
        if spel.spel_status(db) and sp["nickname"]:   # the nickname is on the tv: no renaming once the game runs
            return naar()
        if len(naam) < 2:
            return scherm_welkom(sp, inv, "Kies een bijnaam van minstens 2 letters.")
        if db.q("select 1 from speler where lower(nickname) = lower(?) and id != ?", [naam, sp["id"]]):
            return scherm_welkom(sp, inv, "Die bijnaam is al gebruikt. Kies een andere.")
        try:
            spel.zet_nickname(db, sp["id"], naam)
        except spel.NicknameBezet:
            return scherm_welkom(sp, inv, "Die bijnaam is al gebruikt. Kies een andere.")
        if inv["stap"] == "welkom":
            spel.bewaar(db, sp["id"], stap="voorkeur")
        return naar()

    @route("/voorkeur", methods=["post"])
    def post_voorkeur(req, voorkeur: str = ""):
        sp, inv = wie(req)
        if inv["stap"] != "voorkeur" or voorkeur not in VOORKEUR_GESLACHT:
            return naar()
        spel.bewaar(db, sp["id"], voorkeur=voorkeur, vraag_ids=[v.id for v in kies_vragen(vragen, rng)], stap="vragen")
        return naar()

    @route("/vraag", methods=["post"])
    def post_vraag(req, vid: str = "", kant: str = ""):
        sp, inv = wie(req)
        if inv["stap"] == "vragen" and vid in inv["vraag_ids"] and vid not in inv["antwoorden"] and kant in ("min", "plus"):
            antw = {**inv["antwoorden"], vid: kant}
            spel.bewaar(db, sp["id"], antwoorden=antw, **({"stap": "interesses"} if len(antw) == len(inv["vraag_ids"]) else {}))
        return naar()

    @route("/interesses", methods=["post"])
    async def post_interesses(req):
        sp, inv = wie(req)
        if inv["stap"] != "interesses":
            return naar()
        gekozen = list(dict.fromkeys((await req.form()).getlist("interesse")))
        iv = vragen.interessevraag
        if not (iv["min_keuzes"] <= len(gekozen) <= iv["max_keuzes"]) or not set(gekozen) <= set(vragen.interesses):
            return scherm_interesses(sp, inv, f"Kies {iv['min_keuzes']} of {iv['max_keuzes']} dingen.")
        spel.bewaar(db, sp["id"], interesses=gekozen, stap="open")
        return naar()

    @route("/open", methods=["post"])
    def post_open(req, a1: str = "", a2: str = ""):
        sp, inv = wie(req)
        if inv["stap"] != "open":
            return naar()
        spel.bewaar(db, sp["id"], open_antwoorden=[t.strip()[:MAX_OPEN] for t in (a1, a2) if t.strip()])
        maak_vervolg(sp, spel.invulling(db, sp["id"]))
        return naar()

    @route("/vervolg", methods=["post"])
    async def post_vervolg(req):
        sp, inv = wie(req)
        if inv["stap"] != "vervolg":
            return naar()
        form = await req.form()
        antw = {v["id"]: form.get(v["id"]) for v in inv["vervolg"] if form.get(v["id"]) in ("min", "plus")}
        spel.bewaar(db, sp["id"], vervolg_antwoorden=antw)
        maak_match(sp, spel.invulling(db, sp["id"]))
        return naar()

    @route("/keuze", methods=["post"])
    async def post_keuze(req):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        if inv["stap"] != "keuze" or not m:
            return naar()
        form = await req.form()
        qids = [h["qid"] for h in m["top3"]]
        gekozen = form.get("gekozen")
        if gekozen not in qids:
            return naar()
        niet = {q: str(form.get(f"niet_{q}") or "").strip()[:MAX_OPEN] for q in qids if q != gekozen and form.get(f"niet_{q}")}
        try:
            spel.kies(db, sp["id"], gekozen, str(form.get("want") or "").strip()[:MAX_OPEN], niet)
        except spel.AlGekozen:
            # A parallel player confirmed this saint first: quietly offer a fresh top-3.
            maak_match(sp, inv)
            return naar()
        spel.bewaar(db, sp["id"], stap="klaar")
        return naar()

    @route("/geen-past", methods=["post"])
    async def post_geen_past(req):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        if inv["stap"] != "keuze" or inv["extra_ronde"] or not m:
            return naar()
        form = await req.form()
        afgewezen = {**m["afgewezen"], **{h["qid"]: str(form.get(f"niet_{h['qid']}") or "").strip()[:MAX_OPEN] for h in m["top3"]}}
        spel.bewaar_match(db, sp["id"], m["top3"], bool(m["via_llm"]), None, afgewezen)
        spel.bewaar(db, sp["id"], extra_ronde=1)
        maak_vervolg(sp, spel.invulling(db, sp["id"]), afgewezen)
        return naar()

    @route("/mijn")
    def mijn(req):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        if not m:
            return naar()
        return pagina("Mijn heilige", *kaarten(m, eigen=m["gekozen"]), A("Terug", href="/", cls="knop")), leiding_link(req)

    @route("/heilige/{qid}")
    def heilige(req, qid: str):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        mag = ({h["qid"] for h in m["top3"]} | set(m["afgewezen"])) if m else set()
        if qid not in per_qid or (qid not in mag and not leiding(req)):
            return Response("Niet gevonden.", status_code=404)
        terug = "/mijn" if m and m["gekozen"] else "/"
        return pagina(per_qid[qid].naam, *info(per_qid[qid]), A("Terug", href=terug, cls="knop")), leiding_link(req)

    @route("/beheer")
    def beheer(req):
        if not leiding(req):
            return Response("Alleen voor begeleiders.", status_code=403)
        rijen = spel.overzicht(db)
        return pagina("Overzicht", P(f"{sum(r['stap'] == 'klaar' for r in rijen)} van {len(rijen)} klaar."),
            Table(Tr(Th("Bijnaam"), Th("Account"), Th("Stap"), Th("Uitleg door"), Th("Markering")),
                  *[Tr(Td(A(r["nickname"], href=f"/beheer/speler/{r['id']}") if r["nickname"] else "–"), Td(r["gebruikersnaam"]), Td(r["stap"]),
                       Td("–" if r["via_llm"] is None else "Gemini" if r["via_llm"] else "vaste tekst"), Td(r["markering"] or ""))
                    for r in rijen]),
            A("Het raadspel bedienen", href="/beheer/spel", cls="knop"),
            A("Alles downloaden (JSON)", href="/beheer/export", cls="knop"),
            Form(Label("Typ VERWIJDER om alle spelers en antwoorden te wissen", Input(type="text", name="bevestig")),
                 Button("Groep verwijderen", type="submit"), method="post", action="/beheer/verwijder"))

    @route("/beheer/export")
    def beheer_export(req):
        if not leiding(req):
            return Response("Alleen voor begeleiders.", status_code=403)
        return Response(json.dumps(spel.exporteer(db), ensure_ascii=False, indent=1), media_type="application/json",
                        headers={"content-disposition": 'attachment; filename="durfheilig-export.json"'})

    @route("/beheer/verwijder", methods=["post"])
    def beheer_verwijder(req, bevestig: str = ""):
        if not leiding(req):
            return Response("Alleen voor begeleiders.", status_code=403)
        # Own CSRF defence: a browser marks requests started by another site.
        if req.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return Response("Niet toegestaan.", status_code=403)
        if bevestig.strip() != "VERWIJDER":
            return pagina("Niets gewist", P("Typ VERWIJDER, precies zo, om alles te wissen."), A("Terug", href="/beheer", cls="knop"))
        spel.verwijder_alles(db)
        return naar("/beheer")

    raadspel.registreer(app, db, per_qid, leiding=leiding, wie=wie, pagina=pagina, naar=naar, afbeelding_url=afbeelding_url, rng=rng)
    return app


def main() -> int:
    import uvicorn

    heiligen, vragen = laad_heiligen(), laad_vragen()
    llm = llm_uit_omgeving()
    print("LLM:", "Gemini" if llm else "geen sleutel, terugval op vaste teksten")
    app = maak_app(spel.open_db(spel.db_pad()), heiligen, vragen, llm)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT") or os.environ.get("PORT") or 8000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
