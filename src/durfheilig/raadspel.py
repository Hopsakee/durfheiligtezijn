"""Het raadspel van de middag (fase 5): bord, rondes, stemmen, punten, tv-scherm en bediening.

De regels staan in `docs/design/plan-heiligen-welkomstspel.md` (Draaiboek van de middag):
- het bord heeft 2 x N heiligen: de N gekozen plus N willekeurige andere, één keer getrokken;
- per deelnemer een ronde: stemmen, uitslag (alleen aantallen), vragenronde, nog een keer stemmen, onthulling;
- nooit wie op wat stemde; punten zijn groepspunten: meer dan de helft goed na ronde 1 geeft 2, na ronde 2 geeft 1.

Alles wat de tv, de telefoons en de begeleider zien, komt uit de database; de pagina's vragen elke 2 seconden om een update.
"""

import random
from collections import Counter
from collections.abc import Iterable, Sequence

from fasthtml.common import A, Button, Div, Form, H1, H2, Img, Input, Label, Option, P, Response, Select, Small, Span, Table, Td, Th, Tr

from . import db as spel
from .data import Heilige

FASES = ("overleg1", "uitslag1", "vragen", "overleg2", "uitslag2", "onthuld")
STEMFASEN = {"overleg1": 1, "overleg2": 2}
MIN_SPELERS = 3

KNOP_TEKST = {
    "bord": "Start ronde 1",
    "overleg1": "Stemming sluiten en uitslag tonen",
    "uitslag1": "Vragenronde starten",
    "vragen": "Tweede stemronde openen",
    "overleg2": "Stemming sluiten en uitslag tonen",
    "uitslag2": "Onthul de heilige",
    "onthuld": "Volgende ronde",
    "plaat": "Afsluiting met groepsscore",
}
FASE_TEKST = {
    "overleg1": "Overleg en stem op je telefoon",
    "uitslag1": "De uitslag van de eerste stemronde",
    "vragen": "Vragenronde: stel één vraag",
    "overleg2": "Overleg en stem opnieuw",
    "uitslag2": "De uitslag van de tweede stemronde",
    "onthuld": "De heilige wordt onthuld",
}

RAAD_CSS = """
.bord{display:grid;grid-template-columns:repeat(auto-fill,minmax(9rem,1fr));gap:.6rem}
.tegel{position:relative;background:var(--kaart);border:2px solid var(--rand);border-radius:12px;padding:.5rem;text-align:center;font-size:.85rem}
.tegel img{display:block;width:100%;height:7rem;object-fit:contain;background:#f1eadb;border-radius:8px}
.tegel b{display:block;margin-top:.3rem}.tegel.juist{border:6px solid var(--accent);background:#fff4ee}
.tegel .aantal{position:absolute;top:.3rem;right:.3rem;background:var(--accent);color:#fff;border-radius:999px;padding:.1rem .6rem;font-weight:700}
.tegel .van{color:var(--accent);font-weight:700}.tegel.stem{border-color:var(--accent);border-width:4px}
.tv .bord{grid-template-columns:repeat(auto-fill,minmax(11rem,1fr))}.tv{font-size:1.2rem}.tv h1{font-size:2.2rem}
form.tegelknop{margin:0}form.tegelknop button{padding:.5rem;margin:0;text-align:center;font-weight:400;font-size:.85rem}
@media print{.geen-print,#laden{display:none!important}body{background:#fff}.tegel{break-inside:avoid}}
"""


# ---------------------------------------------------------------- de regels, zonder database

def trek_bord(gekozen: Sequence[str], alle: Iterable[str], rng: random.Random) -> list[tuple[str, bool]]:
    """De N gekozen heiligen plus N willekeurige andere, in een willekeurige volgorde zodat de gekozen niet opvallen."""
    gekozen = list(dict.fromkeys(gekozen))
    rest = sorted(set(alle) - set(gekozen))
    if len(rest) < len(gekozen):
        raise ValueError("te weinig heiligen over voor een bord van 2 x N")
    bord = [(q, True) for q in gekozen] + [(q, False) for q in rng.sample(rest, len(gekozen))]
    rng.shuffle(bord)
    return bord


def meerderheid(juist: str, qids: Iterable[str]) -> bool:
    """Meer dan de helft van de uitgebrachte stemmen is juist."""
    qids = list(qids)
    return bool(qids) and 2 * Counter(qids)[juist] > len(qids)


def punten(juist: str, ronde1: Iterable[str], ronde2: Iterable[str]) -> int:
    """2 punten als de groep het na stemronde 1 goed had, 1 als pas na ronde 2, anders 0."""
    if meerderheid(juist, ronde1):
        return 2
    return 1 if meerderheid(juist, ronde2) else 0


def volgende_fase(fase: str) -> str | None:
    i = FASES.index(fase)
    return FASES[i + 1] if i + 1 < len(FASES) else None


def volgorde_rondes(speler_ids: Sequence[int], eerste: int | None, rng: random.Random) -> list[int]:
    """Willekeurig, maar de eerste ronde is een deelnemer met een makkelijk te raden heilige als de begeleider die kiest."""
    ids = list(speler_ids)
    rng.shuffle(ids)
    if eerste in ids:
        ids.remove(eerste)
        ids.insert(0, eerste)
    return ids


# ---------------------------------------------------------------- de schermen

def registreer(app, db, per_qid: dict[str, Heilige], *, leiding, wie, pagina, naar, afbeelding_url, rng=None) -> None:
    rng = rng or random.Random()
    route = app.route

    def klaar_spelers():
        return spel.spelers_klaar(db)

    def tegel(h: Heilige, *, aantal=None, juist=False, van=None, stem=False, formulier=False):
        inhoud = [Img(src=afbeelding_url(h), alt=h.naam), Span(h.naam, cls="naam"), Small(h.record.get("wat_voor_mens", ""))]
        if aantal is not None:
            inhoud.insert(0, Span(f"{aantal}×", cls="aantal"))
        if van:
            inhoud.append(Span(f"✔ {van}", cls="van"))
        klassen = "tegel" + (" juist" if juist else "") + (" stem" if stem else "")
        if formulier:
            return Form(Div(*inhoud, cls=klassen), Input(type="hidden", name="qid", value=h.qid),
                        Button(f"Stem op {h.naam}", type="submit"), method="post", action="/spel/stem", cls="tegelknop")
        return Div(*inhoud, cls=klassen)

    def stand():
        """Alles wat de schermen nodig hebben, in één keer uit de database."""
        st = spel.spel_status(db)
        if not st:
            return None
        r = spel.rondes(db)
        huidige = next((x for x in r if x["id"] == st["huidige_ronde"]), None)
        # The players are those fixed at the start (they have a round), not whoever finished the quiz since.
        meedoen = {x["speler_id"] for x in r}
        spelers = {s["id"]: s for s in klaar_spelers() if s["id"] in meedoen}
        bord = [b for b in spel.bord_rijen(db) if b["qid"] in per_qid]   # a saint removed from the data never breaks a screen
        return {"status": st["status"], "ronde": huidige, "rondes": r, "bord": bord, "spelers": spelers}

    def stemmers(sd, ronde):
        """Wie mag stemmen: iedereen in het spel, behalve de deelnemer van deze ronde en wie diens uitleg las."""
        uit = set(spel.lezers(db, ronde["speler_id"]))
        return [sid for sid, s in sd["spelers"].items() if sid != ronde["speler_id"] and s["gebruikersnaam"] not in uit]

    def token(sd) -> str:
        """Names the exact step the leader's button belongs to, so a second tap on the same step does nothing."""
        r = sd["ronde"]
        return f"{sd['status']}:{r['id'] if r else 0}:{r['fase'] if r else ''}"

    def eindscore(sd):
        return sum(x["punten"] or 0 for x in sd["rondes"])

    # -------- telefoon van de deelnemer

    def kind_inhoud(req):
        sp, _ = wie(req)
        sd = stand()
        if not sd:
            return Div(P("Het spel begint straks. Wacht tot de begeleider het start."), id="spel")
        if sp["id"] not in sd["spelers"]:
            return Div(P("Je doet niet mee aan het spel, want je quiz was nog niet klaar. Kijk gerust mee op de tv."), id="spel")
        if sd["status"] == "bord":
            return Div(H2("Het bord"), P("Kijk naar de tv: de heiligen op het bord. Zo meteen begint de eerste ronde."), id="spel")
        if sd["status"] == "plaat":
            return Div(H2("De groepsplaat"), P("Kijk naar de tv."), id="spel")
        if sd["status"] == "einde":
            return Div(H2("Bedankt voor het spelen!"), P("Kijk naar de tv voor de groepsscore."), id="spel")
        ronde = sd["ronde"]
        nick = ronde["nickname"]
        if ronde["speler_id"] == sp["id"]:
            return Div(H2("Deze ronde gaat over jou"), P("Jij stemt niet. Blijf in de kamer en houd je heilige geheim."), id="spel")
        if ronde["fase"] not in STEMFASEN:
            return Div(H2(FASE_TEKST[ronde["fase"]]), P("Kijk naar de tv."), id="spel")
        if sp["id"] not in stemmers(sd, ronde):
            return Div(H2(f"Ronde over {nick}"), P(f"Je hebt de uitleg van {nick} gelezen, dus je stemt deze ronde niet mee. Kijk gerust mee."), id="spel")
        stemronde = STEMFASEN[ronde["fase"]]
        mijn = next((x["qid"] for x in spel.stemmen(db, ronde["id"], stemronde) if x["speler_id"] == sp["id"]), None)
        return Div(H2(f"Bij welke heilige hoort {nick}?"), P("Tik op een heilige om te stemmen. Je mag je keuze nog veranderen."),
                   *([P(f"Jouw stem: {per_qid[mijn].naam}", cls="klein")] if mijn else []),
                   Div(*[tegel(per_qid[b["qid"]], stem=(b["qid"] == mijn), formulier=True) for b in sd["bord"]], cls="bord"), id="spel")

    @route("/spel")
    def spel_pagina(req):
        return pagina("Het raadspel", Div(kind_inhoud(req), hx_get="/spel/inhoud", hx_trigger="every 2s", hx_target="this", hx_swap="innerHTML"))

    @route("/spel/inhoud")
    def spel_inhoud(req):
        return kind_inhoud(req)

    @route("/spel/stem", methods=["post"])
    def spel_stem(req, qid: str = ""):
        if req.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return Response("Niet toegestaan.", status_code=403)
        sp, _ = wie(req)
        sd = stand()
        if sd and sd["status"] == "ronde" and sd["ronde"]["fase"] in STEMFASEN and qid in {b["qid"] for b in sd["bord"]}:
            ronde = sd["ronde"]
            if sp["id"] in stemmers(sd, ronde):
                spel.stem_uit(db, ronde["id"], sp["id"], qid, STEMFASEN[ronde["fase"]])
        return naar("/spel")

    # -------- tv

    def tv_inhoud(req):
        sd = stand()
        if not sd:
            return Div(H1("Het spel is nog niet gestart"), P("De begeleider start het spel vanaf zijn scherm."), id="tv")
        host = req.headers.get("x-forwarded-host") or req.headers.get("host") or ""
        schema = "http" if host.startswith(("127.0.0.1", "localhost")) else "https"
        link = f"{schema}://{host}/spel"
        onthuld = {sd["spelers"][r["speler_id"]]["gekozen"]: r["nickname"] for r in sd["rondes"] if r["fase"] == "onthuld" and r["speler_id"] in sd["spelers"]}
        if sd["status"] == "plaat":
            return Div(H1("De groepsplaat"), P("Dit zijn onze heiligen naast elkaar. Wat zegt dit over ons als groep?"),
                       Div(*[Div(tegel(per_qid[s["gekozen"]]), Span(s["nickname"], cls="van")) for s in sd["spelers"].values()], cls="bord"), id="tv")
        if sd["status"] == "einde":
            n = len(sd["rondes"])
            return Div(H1("Groepsscore"), P(f"{eindscore(sd)} van de {2 * n} punten", style="font-size:2.4rem;font-weight:700"),
                       P("Bedankt voor het spelen! In juni doen we het opnieuw en kijken we wat er veranderd is."), id="tv")
        titel, regels, aantallen, toon_aantallen, juist = "Het bord", [], Counter(), False, None
        if sd["status"] == "bord":
            regels = [P(f"Doe mee op je telefoon: {link}", style="font-size:1.6rem;font-weight:700"), P("Kijk alvast naar de heiligen. Hun beschrijvingen staan erbij.")]
        else:
            r = sd["ronde"]
            titel = f"Ronde {r['volgorde'] + 1} van {len(sd['rondes'])}: wie hoort bij {r['nickname']}?"
            regels = [H2(FASE_TEKST[r["fase"]])]
            if r["fase"] in STEMFASEN:
                kan = len(stemmers(sd, r))
                gedaan = len(spel.stemmen(db, r["id"], STEMFASEN[r["fase"]]))
                regels.append(P(f"{gedaan} van {kan} hebben gestemd"))
            else:
                toon_aantallen = True
                aantallen = Counter(x["qid"] for x in spel.stemmen(db, r["id"], 1 if r["fase"] in ("uitslag1", "vragen") else 2))
            if r["fase"] == "onthuld":
                juist = sd["spelers"][r["speler_id"]]["gekozen"]
                onthuld[juist] = r["nickname"]
                regels.append(P(f"{r['nickname']} had {per_qid[juist].naam}. De groep krijgt {r['punten'] or 0} punt{'en' if (r['punten'] or 0) != 1 else ''}.",
                                style="font-size:1.6rem;font-weight:700"))
            regels.append(P(f"Punten tot nu toe: {sum(x['punten'] or 0 for x in sd['rondes'])}", cls="klein"))
        tegels = [tegel(per_qid[b["qid"]], aantal=aantallen[b["qid"]] if toon_aantallen else None,
                        juist=(b["qid"] == juist), van=onthuld.get(b["qid"])) for b in sd["bord"]]
        return Div(H1(titel), *regels, Div(*tegels, cls="bord"), id="tv")

    @route("/beheer/tv")
    def tv_pagina(req):
        if not leiding(req):
            return Response("Alleen voor begeleiders.", status_code=403)
        return pagina("Raadspel", Div(tv_inhoud(req), hx_get="/beheer/tv/inhoud", hx_trigger="every 2s", hx_target="this", hx_swap="innerHTML", cls="tv"), toon_menu=False)

    @route("/beheer/tv/inhoud")
    def tv_fragment(req):
        if not leiding(req):
            return Response("Alleen voor begeleiders.", status_code=403)
        return tv_inhoud(req)

    # -------- bediening door de begeleider

    def bediening(req):
        sd = stand()
        klaar = klaar_spelers()
        if not sd:
            opties = [Option(f"{s['nickname']}", value=str(s["id"])) for s in klaar if s["nickname"]]
            return Div(
                H2("Spel starten"), P(f"{len(klaar)} deelnemers hebben hun quiz af."),
                *([P(f"Minstens {MIN_SPELERS} deelnemers nodig.", style="color:#b00")] if len(klaar) < MIN_SPELERS else []),
                Form(Label("Eerste ronde (kies iemand met een makkelijk te raden heilige)", Select(Option("Willekeurig", value=""), *opties, name="eerste")),
                     Button("Trek het bord en start", type="submit", cls="hoofd"), method="post", action="/beheer/spel/start"), id="bediening")
        extra = []
        label = None
        if sd["status"] == "bord":
            label = KNOP_TEKST["bord"]
        elif sd["status"] == "ronde":
            r = sd["ronde"]
            extra = [H2(f"Ronde {r['volgorde'] + 1} van {len(sd['rondes'])}: {r['nickname']}"), P(FASE_TEKST[r["fase"]])]
            if r["fase"] in STEMFASEN:
                kan = len(stemmers(sd, r))
                gedaan = len(spel.stemmen(db, r["id"], STEMFASEN[r["fase"]]))
                extra.append(P(f"{gedaan} van {kan} hebben gestemd" + ("" if gedaan >= kan else " (nog niet iedereen)")))
            label = KNOP_TEKST[r["fase"]]
            if r["fase"] == "onthuld" and r["volgorde"] + 1 >= len(sd["rondes"]):
                label = "Naar de groepsplaat"
        elif sd["status"] == "plaat":
            label = KNOP_TEKST["plaat"]
        else:
            extra = [H2("Het spel is afgelopen"), P(f"Groepsscore: {eindscore(sd)} van {2 * len(sd['rondes'])}")]
        return Div(*extra, *([Form(Input(type="hidden", name="van", value=token(sd)), Button(label, type="submit", cls="hoofd"),
                                   method="post", action="/beheer/spel/volgende")] if label else []),
                   P(f"Punten tot nu toe: {eindscore(sd)}", cls="klein"), id="bediening")

    def nee(req):
        return None if leiding(req) else Response("Alleen voor begeleiders.", status_code=403)

    def post_nee(req):
        """Leader-only, and not started by another site. A browser that sends no marker (rare) is let through."""
        if (r := nee(req)) is not None:
            return r
        if req.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return Response("Niet toegestaan.", status_code=403)
        return None

    @route("/beheer/spel")
    def bediening_pagina(req):
        if (r := nee(req)) is not None:
            return r
        return pagina("Spel bedienen", Div(bediening(req), hx_get="/beheer/spel/inhoud", hx_trigger="every 2s", hx_target="this", hx_swap="innerHTML"),
                      A("Tv-scherm openen", href="/beheer/tv", cls="knop"), A("Printversie van het bord", href="/beheer/print", cls="knop"),
                      A("Terug naar het overzicht", href="/beheer", cls="knop"),
                      Form(Label("Typ OPNIEUW om het spel te wissen en opnieuw te beginnen (de antwoorden blijven)", Input(type="text", name="bevestig")),
                           Button("Spel opnieuw beginnen", type="submit"), method="post", action="/beheer/spel/reset"))

    @route("/beheer/spel/inhoud")
    def bediening_fragment(req):
        if (r := nee(req)) is not None:
            return r
        return bediening(req)

    @route("/beheer/spel/start", methods=["post"])
    def spel_start(req, eerste: str = ""):
        if (r := post_nee(req)) is not None:
            return r
        klaar = klaar_spelers()
        if spel.spel_status(db) or len(klaar) < MIN_SPELERS:
            return naar("/beheer/spel")
        bord = trek_bord([s["gekozen"] for s in klaar], per_qid, rng)
        volgorde = volgorde_rondes([s["id"] for s in klaar], int(eerste) if eerste.isdigit() else None, rng)
        spel.start_spel(db, bord, volgorde)
        return naar("/beheer/spel")

    @route("/beheer/spel/volgende", methods=["post"])
    def spel_volgende(req, van: str = ""):
        if (r := post_nee(req)) is not None:
            return r
        sd = stand()
        if not sd or van != token(sd):   # a second tap, or a stale screen: do nothing
            return naar("/beheer/spel")
        if sd["status"] == "bord":
            eerste = sd["rondes"][0]
            spel.zet_spelstatus(db, "ronde", eerste["id"])
        elif sd["status"] == "ronde":
            ronde = sd["ronde"]
            nieuw = volgende_fase(ronde["fase"])
            if nieuw:
                if nieuw == "onthuld":
                    juist = sd["spelers"][ronde["speler_id"]]["gekozen"]
                    spel.zet_punten(db, ronde["id"], punten(juist, [x["qid"] for x in spel.stemmen(db, ronde["id"], 1)],
                                                           [x["qid"] for x in spel.stemmen(db, ronde["id"], 2)]))
                spel.zet_fase(db, ronde["id"], nieuw)
            else:
                volgende = next((x for x in sd["rondes"] if x["volgorde"] == ronde["volgorde"] + 1), None)
                spel.zet_spelstatus(db, "ronde", volgende["id"]) if volgende else spel.zet_spelstatus(db, "plaat")
        elif sd["status"] == "plaat":
            spel.zet_spelstatus(db, "einde")
        return naar("/beheer/spel")

    @route("/beheer/spel/reset", methods=["post"])
    def spel_reset(req, bevestig: str = ""):
        if (r := post_nee(req)) is not None:
            return r
        if bevestig.strip() == "OPNIEUW":
            spel.reset_spel(db)
        return naar("/beheer/spel")

    # -------- printversie als terugval zonder app

    @route("/beheer/print")
    def print_pagina(req):
        if (r := nee(req)) is not None:
            return r
        sd = stand()
        if not sd:
            return pagina("Printversie", P("Het bord is er nog niet: start eerst het spel."), A("Terug", href="/beheer/spel", cls="knop"))
        return pagina("Het bord (printversie)",
                      P("Print dit en leg het klaar voor als de app uitvalt. Stem op nummer."),
                      Div(*[Div(Span(f"{i}. ", cls="van"), tegel(per_qid[b["qid"]])) for i, b in enumerate(sd["bord"], 1)], cls="bord"),
                      H2("Stembriefje"), P("Ronde over: ________   Eerste stem: ____   Tweede stem: ____"),
                      A("Terug", href="/beheer/spel", cls="knop geen-print"))

    # -------- uitleg lezen en markeren, voor de regel "wie de uitleg las, stemt niet mee"

    @route("/beheer/speler/{sid}")
    def speler_uitleg(req, sid: int):
        if (r := nee(req)) is not None:
            return r
        rij = next((x for x in spel.overzicht(db) if x["id"] == sid), None) if 0 < sid < 2**31 else None
        m = spel.match_van(db, sid) if rij else None
        if not rij or not m:
            return Response("Niet gevonden.", status_code=404)
        # Whoever opens an explanation has read it, and so does not vote in that player's round. Not a choice, so it cannot be forgotten.
        spel.markeer_gelezen(db, sid, req.scope["gebruiker"])
        return pagina(f"Uitleg voor {rij['nickname'] or 'deelnemer'}",
            *([P(f"Markering: {m['markering']}", style="color:#b00")] if m["markering"] else []),
            *[Div(H2(h["naam"]), P(h["uitleg"]), *([P("✔ Gekozen", cls="klein")] if h["qid"] == m["gekozen"] else []), cls="kaart") for h in m["top3"]],
            P("Je hebt deze uitleg nu gelezen: in de ronde van deze deelnemer stem je niet mee.", cls="klein"),
            A("Terug", href="/beheer", cls="knop"))
