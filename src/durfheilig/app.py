"""De quiz-app voor thuis (fase 4): FastHTML, één scherm per stap, voortgang per stap bewaard.

De hele app zit achter Authelia; Caddy stuurt `Remote-User` mee. Er is geen eigen inlog.
De app leest alleen `Remote-User` (en `Remote-Groups` voor /beheer), nooit naam of e-mailadres.
Elke stap is een gewoon formulier met een POST en een redirect, zodat een telefoon die op slot
gaat of even geen bereik heeft niets verliest.
"""

import functools
import hashlib
import json
import os
import random
from urllib.parse import urlparse

from starlette.concurrency import run_in_threadpool
from fasthtml.common import (A, Beforeware, Button, Details, Div, FastHTML, FileResponse, Form, H2, Img, Input, Label, Li, P, Response,
                             B, Script, Small, Span, Ul, Style, Summary, Table, Td, Th, Tr, Textarea)

from . import db as spel
from . import raadspel, ui
from .data import DATA_DIR, Heilige, Vragenbank, laad_heiligen, laad_vragen
from .llm import Llm, Uitslag, beschrijving, finale, llm_uit_omgeving, vervolgvragen, Vervolgvraag
from .scoring import VOORKEUR_GESLACHT, kies_vragen, profiel, rangschik
from .ui import CHIPSSCRIPT, KIJKER, afbeelding_url, is_leiding, keuzekaart, naar, pagina, zichtbaar

MAX_OPEN = 200
MAX_NICKNAME = 20
VOORKEUR_LABEL = {"man": ("👨", "Een man"), "vrouw": ("👩", "Een vrouw"), "maakt niet uit": ("🤷", "Maakt niet uit")}
STAPPEN = ("welkom", "voorkeur", "vragen", "interesses", "open", "vervolg", "keuze", "klaar")

CSS = ui.CSS + raadspel.RAAD_CSS


def knop_formulier(actie: str, *velden, tekst: str = "Verder", laad: str | None = None, knopcls: str = "hoofd", **hidden):
    extra = {"data-laad": laad} if laad else {}
    return Form(*velden, *[Input(type="hidden", name=k, value=v) for k, v in hidden.items()],
                Button(tekst, cls=knopcls, type="submit"), method="post", action=actie, **extra)


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


def maak_app(db, heiligen: list[Heilige], vragen: Vragenbank, llm: Llm | None, rng: random.Random | None = None,
             extra_menu: list[tuple[str, str]] = ()) -> FastHTML:
    """`extra_menu` is for the local launcher only: extra (href, title) entries in the menu."""
    rng = rng or random.Random()
    per_qid = {h.qid: h for h in heiligen}
    per_vraag = {v.id: v for v in vragen.vragen}

    async def auth(req):   # async, so the context variable set here is seen by the page code that runs after it
        gebruiker = (req.headers.get("remote-user") or "").strip()
        if not gebruiker:
            return Response("Niet ingelogd.", status_code=401)
        req.scope["gebruiker"] = gebruiker
        pad = req.url.path
        # The two rules that must never be forgotten on a new route live here: /beheer is for leaders only, and a request that changes
        # something must not be started by another site (a browser marks those; one that sends no marker is let through; Authelia's
        # SameSite=Lax session cookie, its default, covers the browsers that send none). A GET that changes something must check
        # `sec-fetch-site` itself.
        if (pad == "/beheer" or pad.startswith("/beheer/")) and not is_leiding(req.headers):
            return Response("Alleen voor begeleiders.", status_code=403)
        if req.method not in ("GET", "HEAD") and req.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return Response("Niet toegestaan.", status_code=403)
        KIJKER.set({"leiding": is_leiding(req.headers), "extra": extra_menu,
                    "profiel": functools.cache(lambda: spel.profiel_van(db, gebruiker) or {})})   # only looked up when a menu is built

    app = FastHTML(before=Beforeware(auth, skip=[r"/health", r"/img/.*"]), hdrs=(Style(CSS),), secret_key=os.urandom(16).hex(),
                   pico=False)
    route = functools.partial(app.route, methods=["get"])   # FastHTML answers GET and POST by default; a route that changes something says methods=["post"]

    def wie(req) -> tuple[dict, dict]:
        sp = spel.speler_voor(db, req.scope["gebruiker"])
        return sp, spel.invulling(db, sp["id"])

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
                    vervolg_antwoorden={}, stap="vervolg", alleen_bij_stap=inv["stap"])   # not over a quiz the kid restarted meanwhile

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
        spel.bewaar_match(db, sp["id"], top3, uit.door_llm, uit.markering, afgewezen, verwacht_stap=inv["stap"], stap_na="keuze")

    # ------------------------------------------------------------------ schermen

    def scherm_welkom(sp, inv, fout=""):
        punt = lambda icoon, tekst: Li(Span(icoon, cls="icoon"), Span(tekst))
        return pagina("Welkom!",
            Div(Div("😇", cls="groot"), P("Zullen we jouw heilige zoeken? Je doet een korte quiz en kiest daarna uit drie heiligen die bij jou passen."), cls="hero"),
            Ul(punt("⏱️", "Het duurt 5 tot 7 minuten."), punt("🎭", "Je gebruikt een bijnaam, geen echte naam."),
               punt("🤫", "Vertel alleen wat je ook aan de groep zou vertellen."), punt("🎲", "Op de middag raden we wie welke heilige heeft."), cls="lijst"),
            knop_formulier("/welkom", Label("Kies een bijnaam", Input(type="text", name="nickname", maxlength=MAX_NICKNAME, required=True,
                                                                         value=sp["nickname"] or "", placeholder="bijvoorbeeld Vos", autocomplete="off"), cls="veld"),
                           tekst="Beginnen"), stap=1, fout=fout)

    def scherm_voorkeur(sp, inv):
        return pagina("Jouw heilige", P("Mag je heilige een man of een vrouw zijn, of maakt het niet uit?"),
            *[Form(Input(type="hidden", name="voorkeur", value=v), Button(Span(icoon, cls="icoon"), tekst, type="submit"), method="post", action="/voorkeur")
              for v, (icoon, tekst) in VOORKEUR_LABEL.items()], stap=1)

    def terug_knop(tekst="← Vorige vraag"):
        return knop_formulier("/vraag/terug", tekst=tekst, knopcls="sec")

    def scherm_vraag(sp, inv):
        klaar = len(inv["antwoorden"])
        vid = next(v for v in inv["vraag_ids"] if v not in inv["antwoorden"])   # vraag_ids is the one source of the count
        v = per_vraag[vid]
        kanten = [("min", v.min), ("plus", v.plus)]
        if int(hashlib.sha256(f"{sp['id']}{vid}".encode()).hexdigest(), 16) % 2:
            kanten.reverse()
        return pagina(v.vraag, stap=2, vraag=(klaar, len(inv["vraag_ids"])), *[
            Form(Input(type="hidden", name="vid", value=vid), Input(type="hidden", name="kant", value=k),
                 Button(Span(a["icoon"], cls="icoon"), a["tekst"], type="submit"), method="post", action="/vraag")
            for k, a in kanten], *([terug_knop()] if klaar else []))

    def scherm_interesses(sp, inv, fout=""):
        iv = vragen.interessevraag
        return pagina(iv["vraag"], P(f"Kies {iv['min_keuzes']} of {iv['max_keuzes']}.", id="telling", cls="voortgang"),
            knop_formulier("/interesses", Div(*[keuzekaart("checkbox", "interesse", o["interesse"], f"{o['icoon']} {o['interesse']}") for o in iv["opties"]],
                                              cls="chips", data_min=iv["min_keuzes"], data_max=iv["max_keuzes"])),
            terug_knop("← Terug naar de vragen"), Script(CHIPSSCRIPT), stap=3, fout=fout)

    def scherm_open(sp, inv):
        return pagina("Nog twee dingen over jou", P("Een zin is genoeg. Je mag ook overslaan."),
            knop_formulier("/open",
                Label("Waar ben je stiekem goed in?", Textarea(name="a1", maxlength=MAX_OPEN, rows=2, placeholder="Bijvoorbeeld: tekenen, mensen aan het lachen maken…"), cls="veld"),
                Label("Waar kun je je echt over opwinden?", Textarea(name="a2", maxlength=MAX_OPEN, rows=2, placeholder="Bijvoorbeeld: oneerlijkheid, voetbal, dieren…"), cls="veld"),
                laad="We bedenken drie vragen speciaal voor jou…"), stap=4)

    def scherm_vervolg(sp, inv):
        return pagina("Nog drie vragen", P("Zo vinden we jouw heilige nog beter."),
            Form(*[Div(H2(v["vraag"]),
                       *[keuzekaart("radio", v["id"], k, v[k], required=True) for k in ("min", "plus")])
                   for v in inv["vervolg"]],
                 Button("Verder", cls="hoofd", type="submit"), method="post", action="/vervolg",
                 **{"data-laad": "We zoeken de heiligen die bij jou passen…"}), stap=4)

    def kaarten(m, keuze=False, eigen=None):
        out = []
        # Your own choice goes first and stands out; the other two follow in their original order.
        for h in sorted(m["top3"], key=lambda h: h["qid"] != eigen):
            gekozen = eigen == h["qid"]
            out.append(Div(
                *([Span("✔ Jouw heilige", cls="badge")] if gekozen else []),
                Img(src=h["afbeelding"], alt=h["naam"]), Small(f"Foto: {h['credit']}", cls="klein"),
                H2(h["naam"]), P(h["levensverhaal"]), Div(P(h["uitleg"]), cls="bubbel"),
                A(f"Meer over {h['naam']}", href=f"/heilige/{h['qid']}", cls="knop sec"),
                *([keuzekaart("radio", "gekozen", h["qid"], "Deze past bij mij", required=True),
                   Details(Summary("Past niet? Zeg waarom (mag leeg)"), Input(type="text", name=f"niet_{h['qid']}", maxlength=MAX_OPEN))] if keuze else []),
                cls="kaart gekozen" if gekozen else "kaart"))
        return out

    def scherm_keuze(sp, inv):
        m = spel.match_van(db, sp["id"])
        extra = [] if inv["extra_ronde"] else [Button("Er past er geen bij mij", cls="sec", type="submit", formaction="/geen-past", formnovalidate=True,
                                          **{"data-laad": "We zoeken nieuwe vragen en heiligen voor je…"})]
        return pagina("Drie heiligen voor jou", P("Kies de heilige die het best bij je past."),
            Form(*kaarten(m, keuze=True), Label("Deze past bij mij, want…", Textarea(name="want", maxlength=MAX_OPEN, rows=2), cls="veld"),
                 Button("Dit is mijn heilige", cls="hoofd", type="submit"), *extra, method="post", action="/keuze"), stap=5)

    def scherm_klaar(sp, inv):
        return pagina("Bedankt!", Div(Div("🤫", cls="groot"), H2("Houd je heilige geheim tot de middag!"),
                                      P("Zonder geheimhouding valt het raadspel om."), cls="hero"),
                      A("Lees je heilige nog eens terug", href="/mijn", cls="knop"), A("Naar het raadspel", href="/spel", cls="knop"),
                      A("Quiz opnieuw invullen", href="/quiz/opnieuw", cls="knop sec"), stap=5)

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
        # Leaders land on the menu page; kids land straight in their quiz, which is what the link in the group app is for.
        if is_leiding(req.headers):
            return hub(req)
        return quiz(req)

    @route("/quiz")
    def quiz(req):
        sp, inv = wie(req)
        return SCHERMEN[inv["stap"]](sp, inv)

    @route("/vraag/terug", methods=["post"])
    def post_vraag_terug(req):
        """Undo the last answer, so a mis-tap on a one-tap question can be corrected."""
        sp, inv = wie(req)
        if inv["stap"] in ("vragen", "interesses") and inv["antwoorden"]:
            laatste = max(inv["antwoorden"], key=inv["vraag_ids"].index)
            spel.bewaar(db, sp["id"], antwoorden={k: v for k, v in inv["antwoorden"].items() if k != laatste}, stap="vragen")
        return naar()

    @route("/quiz/opnieuw")
    def opnieuw_vragen(req):
        wie(req)
        if spel.spel_status(db):
            return pagina("Opnieuw invullen", P("Het spel is al begonnen, dus je kunt de quiz niet meer opnieuw doen. Vraag het een begeleider als er iets mis is."),
                          A("Terug", href="/menu", cls="knop sec"))
        return pagina("Quiz opnieuw invullen?",
                      Div(Div("🔄", cls="groot"), P("Je antwoorden en je gekozen heilige worden gewist. Je heilige komt dan weer vrij voor anderen, en je begint helemaal opnieuw. Je bijnaam blijft."), cls="hero"),
                      knop_formulier("/quiz/opnieuw", tekst="Ja, begin opnieuw"),
                      A("Nee, terug", href="/quiz", cls="knop sec"))

    @route("/quiz/opnieuw", methods=["post"])
    def opnieuw_doen(req):
        sp, _ = wie(req)
        return naar("/quiz" if spel.reset_invulling(db, sp["id"]) else "/quiz/opnieuw")   # refused once the game runs: that page explains

    @route("/menu")
    def hub(req):
        stap = ui.kijker()["profiel"]().get("stap")
        quiz = "Je quiz is af." if stap == "klaar" else "Je hebt de quiz nog niet gestart." if not stap else "Je quiz is nog bezig: ga verder waar je was."
        kaart = lambda href, titel, uitleg, *_: A(Div(B(titel), Span(uitleg or quiz, cls="uitleg")), href=href, cls="knop")
        paginas = [p for p in zichtbaar() if p[0] != "/menu"]
        voor_jou, voor_leiding = ([kaart(*p) for p in paginas if p[3] == groep] for groep in ("kind", "leiding"))
        return pagina("Start", H2("Voor jou"), *voor_jou, *([H2("Voor begeleiders"), *voor_leiding] if voor_leiding else []))

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
        await run_in_threadpool(maak_match, sp, spel.invulling(db, sp["id"]))   # waits for Gemini: not on the event loop
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
            await run_in_threadpool(maak_match, sp, inv)
            return naar()
        except spel.GeenMatch:   # the kid restarted the quiz in another tab: nothing to confirm
            return naar()
        spel.bewaar(db, sp["id"], stap="klaar", alleen_bij_stap="keuze")
        return naar()

    @route("/geen-past", methods=["post"])
    async def post_geen_past(req):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        if inv["stap"] != "keuze" or inv["extra_ronde"] or not m:
            return naar()
        form = await req.form()
        afgewezen = {**m["afgewezen"], **{h["qid"]: str(form.get(f"niet_{h['qid']}") or "").strip()[:MAX_OPEN] for h in m["top3"]}}
        spel.bewaar_match(db, sp["id"], m["top3"], bool(m["via_llm"]), None, afgewezen, verwacht_stap="keuze")
        spel.bewaar(db, sp["id"], extra_ronde=1, alleen_bij_stap="keuze")
        await run_in_threadpool(maak_vervolg, sp, spel.invulling(db, sp["id"]), afgewezen)
        return naar()

    @route("/mijn")
    def mijn(req):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        if not m:
            return naar()
        return pagina("Mijn heilige", *kaarten(m, eigen=m["gekozen"]), A("Terug", href="/quiz", cls="knop"))

    @route("/heilige/{qid}")
    def heilige(req, qid: str):
        sp, inv = wie(req)
        m = spel.match_van(db, sp["id"])
        mag = ({h["qid"] for h in m["top3"]} | set(m["afgewezen"])) if m else set()
        if qid not in per_qid or (qid not in mag and not is_leiding(req.headers)):
            return Response("Niet gevonden.", status_code=404)
        terug = "/mijn" if m and m["gekozen"] else "/quiz"
        return pagina(per_qid[qid].naam, *info(per_qid[qid]), A("Terug", href=terug, cls="knop"))

    @route("/beheer")
    def beheer(req):
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
        return Response(json.dumps(spel.exporteer(db), ensure_ascii=False, indent=1), media_type="application/json",
                        headers={"content-disposition": 'attachment; filename="durfheilig-export.json"'})

    @route("/beheer/verwijder", methods=["post"])
    def beheer_verwijder(req, bevestig: str = ""):
        if bevestig.strip() != "VERWIJDER":
            return pagina("Niets gewist", P("Typ VERWIJDER, precies zo, om alles te wissen."), A("Terug", href="/beheer", cls="knop"))
        spel.verwijder_alles(db)
        return naar("/beheer")

    raadspel.registreer(app, db, per_qid, wie=wie, rng=rng)
    return app


def main() -> int:
    import uvicorn

    heiligen, vragen = laad_heiligen(), laad_vragen()
    llm = llm_uit_omgeving()
    print("LLM:", beschrijving(llm))
    app = maak_app(spel.open_db(spel.db_pad()), heiligen, vragen, llm)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT") or os.environ.get("PORT") or 8000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
