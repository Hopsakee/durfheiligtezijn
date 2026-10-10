"""Probeer een taalmodel uit met de echte prompts van de app, op verzonnen deelnemers.

    uv run python -m durfheilig.modeltest --modellen scaleway          welke modellen heeft deze aanbieder?
    uv run python -m durfheilig.modeltest --ping mistral:mistral-small-2603     één kleine vraag: status, limietkoppen en de melding
    uv run python -m durfheilig.modeltest --model scaleway:mistral-small-3.2-24b-instruct-2506 --model mistral:mistral-small-latest
    uv run python -m durfheilig.modeltest --model scaleway:X --n 8 --gelijktijdig 12

`aanbieder:model` kiest de aanbieder per model (mistral, scaleway, openai of gemini), zodat je er in één run meerdere kunt vergelijken; hun
sleutels staan naast elkaar in `.env` (`MISTRAL_API_KEY`, `SCALEWAY_API_KEY`). Zonder voorvoegsel geldt de aanbieder uit `.env`. Er gaan alleen verzonnen antwoorden naar het model, nooit gegevens van kinderen. Het rapport komt in `modeltest/`
(genegeerd door git) en bevat de volledige teksten, want of een uitleg warm en kloppend klinkt, beoordeel je door te lezen. De controles ervoor
zijn grof: ze vangen het ergste (ongeldige JSON, Engels, markdown, verzonnen jaartallen, een uitleg zonder verwijzing naar het kind).
"""

import argparse
import logging
import os
import random
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .data import Heilige, Vragenbank, laad_heiligen, laad_vragen
from .dev import laad_env
from .llm import AANBIEDERS, Llm, LlmFout, Uitslag, Vervolgvraag, beschrijving, finale, lijst_modellen, llm_uit_omgeving, ping, vervolgvragen
from .scoring import kies_vragen, profiel, rangschik

OPEN_ANTWOORDEN = [
    ("Ik ben goed in tekenen", "Ik word boos als iemand wordt buitengesloten"),
    ("Voetballen en mensen aan het lachen maken", "Oneerlijke scheidsrechters"),
    ("Ik kan goed luisteren naar vrienden", "Als dieren slecht worden behandeld"),
    ("Gamen en dingen uitzoeken hoe ze werken", "Dat sommige mensen niks hebben terwijl anderen veel hebben"),
    ("Zingen en gitaar spelen", "Pesten op school"),
    ("Koken en bakken voor mijn familie", "Dat niemand naar elkaar luistert"),
    ("", ""),
    ("Sporten en doorzetten als het zwaar is", "Wanneer mensen liegen"),
]
ENGELS = {"the", "and", "you", "your", "with", "this", "that", "because", "who", "was", "were", "his", "her"}
RAAD = r"(als ai|taalmodel|als een ai|artificial)"


@dataclass
class Meting:
    soort: str                      # "vervolg" or "finale"
    duur: float
    door_llm: bool
    problemen: list[str] = field(default_factory=list)
    tekst: str = ""


def zinnen(tekst: str) -> int:
    return len([z for z in re.split(r"(?<=[.!?])\s+", tekst.strip()) if z])


def _engels(tekst: str) -> bool:
    return len(ENGELS & set(re.findall(r"[a-z']+", tekst.lower()))) >= 3


def controleer_uitleg(uitleg: str, h: Heilige, open_antwoorden: list[str]) -> list[str]:
    """Rough checks on one personal explanation: what a reader would notice at once."""
    p = []
    if not 2 <= zinnen(uitleg) <= 4:
        p.append(f"{zinnen(uitleg)} zinnen (bedoeld 2 of 3)")
    if re.search(r"\b(u|uw|uzelf)\b", uitleg, re.I):
        p.append("u-vorm")
    if _engels(uitleg):
        p.append("Engels")
    if re.search(r"(\*\*|^#|`|^\s*[-*] )", uitleg, re.M):
        p.append("markdown")
    if re.search(RAAD, uitleg, re.I):
        p.append("praat over zichzelf als AI")
    bron = " ".join(str(v) for v in h.record.values() if isinstance(v, (str, list, dict)))
    onbekend = {j for j in re.findall(r"\b(1[0-9]{3}|20[0-9]{2})\b", uitleg) if j not in bron}
    if onbekend:
        p.append(f"jaartal niet in het record: {', '.join(sorted(onbekend))}")
    return p


def verwijst_naar_kind(uitleg: str, open_antwoorden: list[str]) -> bool:
    woorden = {w for t in open_antwoorden for w in re.findall(r"[a-zà-ÿ]{5,}", t.lower())}
    return bool(woorden) and any(w[:5] in uitleg.lower() for w in woorden)


def controleer_vraag(v: Vervolgvraag) -> list[str]:
    p = []
    if not v.vraag.rstrip().endswith("?"):
        p.append("vraag eindigt niet op ?")
    if _engels(f"{v.vraag} {v.min} {v.plus}"):
        p.append("Engels")
    if len(v.min) < 3 or len(v.plus) < 3:
        p.append("antwoord te kort")
    return p


def verzonnen_deelnemer(i: int, seed: int, heiligen: list[Heilige], vragen: Vragenbank):
    rng = random.Random(seed * 1000 + i)
    antw = {q.id: rng.choice(("min", "plus")) for q in kies_vragen(vragen, rng)}
    p = profiel(antw, vragen)
    interesses = rng.sample(vragen.interesses, rng.choice((2, 3)))
    open_ = [t for t in OPEN_ANTWOORDEN[i % len(OPEN_ANTWOORDEN)] if t]
    top = [h for h, _ in rangschik(p, interesses, heiligen, rng.choice(("man", "vrouw", "maakt niet uit")), n=12, interesse_lijst=vragen.interesses)]
    return antw, p, interesses, open_, top


def draai_deelnemer(llm: Llm, i: int, seed: int, heiligen, vragen) -> tuple[list[Meting], dict]:
    antw, p, interesses, open_, top = verzonnen_deelnemer(i, seed, heiligen, vragen)
    metingen = []
    begin = time.monotonic()
    vq, door = vervolgvragen(llm, p, interesses, open_, top, vragen, set(antw))
    problemen = [x for v in vq for x in controleer_vraag(v)] if door else []
    metingen.append(Meting("vervolg", time.monotonic() - begin, door, problemen,
                           "\n".join(f"- {v.vraag}  [{v.min} / {v.plus}]" for v in vq)))
    kies = {v.id: ("min" if k % 2 else "plus") for k, v in enumerate(vq)}
    begin = time.monotonic()
    uit: Uitslag = finale(llm, p, interesses, open_, top, vq, kies)
    duur = time.monotonic() - begin
    per_qid = {h.qid: h for h in top}
    problemen, regels, verwijst = [], [], False
    for k in uit.keuzes:
        h = per_qid[k.qid]
        if uit.door_llm:
            problemen += [f"{h.naam}: {x}" for x in controleer_uitleg(k.uitleg, h, open_)]
            verwijst = verwijst or verwijst_naar_kind(k.uitleg, open_)
        regels.append(f"**{h.naam}**: {k.uitleg}")
    if uit.door_llm and open_ and not verwijst:
        problemen.append("geen enkele uitleg verwijst naar wat het kind schreef")
    if uit.markering:
        regels.append(f"_markering: {uit.markering}_")
    metingen.append(Meting("finale", duur, uit.door_llm, problemen, "\n\n".join(regels)))
    return metingen, {"open": open_, "interesses": interesses}


def percentiel(waarden: list[float], q: float) -> float:
    return sorted(waarden)[round(q * (len(waarden) - 1))]


def samenvatting(naam: str, per_deelnemer: list[list[Meting]], gelijktijdig: list[float] | None = None) -> str:
    alle = [m for ms in per_deelnemer for m in ms]
    regels = [f"### {naam}", ""]
    for soort in ("vervolg", "finale"):
        ms = [m for m in alle if m.soort == soort]
        duur = [m.duur for m in ms]
        regels.append(f"- **{soort}**: {sum(m.door_llm for m in ms)} van {len(ms)} bruikbaar (de rest viel terug op vaste tekst), "
                      f"mediaan {statistics.median(duur):.1f} s, traagste {max(duur):.1f} s, {sum(len(m.problemen) for m in ms)} opvallende punten")
    if gelijktijdig:
        regels.append(f"- **{len(gelijktijdig)} tegelijk** (finale): mediaan {statistics.median(gelijktijdig):.1f} s, p95 {percentiel(gelijktijdig, .95):.1f} s, traagste {max(gelijktijdig):.1f} s")
    return "\n".join(regels)


def rapport(naam: str, per_deelnemer, context, gelijktijdig=None) -> str:
    uit = [f"# Modeltest: {naam}", "", f"Datum {date.today().isoformat()}. Verzonnen deelnemers, echte prompts.", "", samenvatting(naam, per_deelnemer, gelijktijdig), ""]
    for i, (ms, c) in enumerate(zip(per_deelnemer, context), 1):
        uit += [f"## Deelnemer {i}", f"Interesses: {', '.join(c['interesses'])}. Eigen woorden: {' | '.join(c['open']) or '(niets ingevuld)'}", ""]
        for m in ms:
            uit += [f"**{m.soort}** ({m.duur:.1f} s, {'LLM' if m.door_llm else 'vaste tekst'})", "", m.tekst, ""]
            uit += [f"> let op: {p}" for p in m.problemen] + ([""] if m.problemen else [])
    return "\n".join(uit)


def draai_model(llm: Llm, n: int, seed: int, gelijktijdig: int = 0, heiligen=None, vragen=None):
    heiligen, vragen = heiligen or laad_heiligen(), vragen or laad_vragen()
    per, ctx = [], []
    for i in range(n):
        ms, c = draai_deelnemer(llm, i, seed, heiligen, vragen)
        per.append(ms), ctx.append(c)
    duren = []
    if gelijktijdig:
        def een(i):
            antw, p, interesses, open_, top = verzonnen_deelnemer(i, seed, heiligen, vragen)
            begin = time.monotonic()
            finale(llm, p, interesses, open_, top, [], {})
            return time.monotonic() - begin
        with ThreadPoolExecutor(gelijktijdig) as pool:
            duren = list(pool.map(een, range(gelijktijdig)))
    return per, ctx, duren


def omgeving_voor(spec: str, basis: dict) -> tuple[dict, str]:
    """The environment for one `--model`: `aanbieder:model` picks that provider, a bare name keeps the one in `.env`."""
    env = dict(basis)
    voorvoegsel, _, naam = spec.partition(":")
    if naam and voorvoegsel in (*AANBIEDERS, "openai", "gemini"):
        env["LLM_PROVIDER"] = voorvoegsel
        env["GEMINI_MODEL" if voorvoegsel == "gemini" else "LLM_MODEL"] = naam
        return env, naam
    kiest_compat = (env.get("LLM_PROVIDER", "").lower() in (*AANBIEDERS, "openai")) or (not env.get("LLM_PROVIDER") and env.get("LLM_BASE_URL"))
    env["LLM_MODEL" if kiest_compat else "GEMINI_MODEL"] = spec
    return env, spec


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except LlmFout as e:
        raise SystemExit(str(e))


def _main(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", action="append", default=[], help="modelnaam, of aanbieder:modelnaam; mag vaker")
    ap.add_argument("--ping", metavar="AANBIEDER:MODEL", help="stel één kleine vraag en toon status, limietkoppen en de melding van de aanbieder")
    ap.add_argument("--modellen", metavar="AANBIEDER", help="toon de modellen van deze aanbieder (mistral, scaleway, openai) en stop")
    ap.add_argument("--n", type=int, default=6, help="aantal verzonnen deelnemers per model")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--gelijktijdig", type=int, default=0, help="speel daarna zoveel finales tegelijk, om te zien hoe het onder druk gaat")
    ap.add_argument("--uit", type=Path, default=Path("modeltest"))
    a = ap.parse_args(argv)
    laad_env()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if a.ping:
        env, model = omgeving_voor(a.ping, dict(os.environ))
        aanbieder = env.get("LLM_PROVIDER") or "openai"
        u = ping(aanbieder, model, env)
        print(f"{aanbieder}, model {model}: HTTP {u['status']} na {u['duur']:.1f} s")
        print("limietkoppen:", u["limietkoppen"] or "(geen)")
        print("antwoord:", u["tekst"])
        return 0
    if a.modellen:
        print("\n".join(lijst_modellen(a.modellen, os.environ)))
        return 0
    if not a.model:
        raise SystemExit("Geef minstens één --model, of --modellen <aanbieder> om te zien wat er is")
    samenvattingen = []
    for spec in a.model:
        env, model = omgeving_voor(spec, dict(os.environ))
        llm = llm_uit_omgeving(env)
        if llm is None:
            raise SystemExit("Geen aanbieder ingesteld: zet LLM_BASE_URL, LLM_API_KEY (of de Gemini-variabelen) in .env, zie .env.example")
        print(f"\n== {model} ({beschrijving(llm)}) ==", flush=True)
        per, ctx, duren = draai_model(llm, a.n, a.seed, a.gelijktijdig)
        tekst = rapport(model, per, ctx, duren)
        a.uit.mkdir(parents=True, exist_ok=True)
        pad = a.uit / f"{date.today().isoformat()}-{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.md"
        pad.write_text(tekst, encoding="utf-8")
        s = samenvatting(model, per, duren)
        samenvattingen.append(s)
        print(s, f"\n  rapport: {pad}", flush=True)
    print("\n" + "\n\n".join(samenvattingen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
