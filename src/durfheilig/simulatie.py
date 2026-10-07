"""Simulation: does the matching spread over the set, or hand everyone the same saints?

Fictional profiles answer every either-or question 50/50 and pick 2 or 3 interests at
random. That tests spread, not realism; whether real people recognise their top-3 is
tested at the dress rehearsal.

Each gender preference gets its own 200 profiles, so the plan's two spread requirements
can be checked per group with the same thresholds ("comparable per gender preference").
"First choice" is the deterministic rank 1, standing in for the kid's pick from the
LLM's top-3.

    python -m durfheilig.simulatie [--seed 2026] [--n 200] [--out docs/simulatie/rapport.md]
"""

import argparse
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .data import ASSEN, Heilige, Vragenbank, laad_heiligen, laad_vragen
from .scoring import VOORKEUR_GESLACHT, kies_vragen, profiel, rangschik

MAX_AANDEEL_EERSTE = 0.04
MIN_DEKKING_TOP3 = 0.60
MIN_PER_INTERESSE = 5
VOORKEUREN = ("man", "vrouw", "maakt niet uit")
REPO = Path(__file__).resolve().parents[2]


@dataclass
class GroepUitslag:
    voorkeur: str
    n: int
    toegestaan: list[Heilige]
    eerste: Counter
    top3: Counter

    @property
    def max_aandeel(self) -> float:
        return max(self.eerste.values()) / self.n

    @property
    def dekking(self) -> float:
        return len(self.top3) / len(self.toegestaan)

    def ruis(self, seed: int) -> float:
        """Highest first-choice share if every profile got a uniformly random saint: the noise floor at this n."""
        rng = random.Random(seed)
        return max(Counter(rng.choice(self.toegestaan).qid for _ in range(self.n)).values()) / self.n


def simuleer_groep(voorkeur: str, n: int, heiligen: list[Heilige], vragen: Vragenbank, rng: random.Random) -> GroepUitslag:
    eerste, top3 = Counter(), Counter()
    for _ in range(n):
        antwoorden = {v.id: rng.choice(("min", "plus")) for v in kies_vragen(vragen, rng)}
        interesses = rng.sample(vragen.interesses, rng.choice((2, 3)))
        top = rangschik(profiel(antwoorden, vragen), interesses, heiligen, voorkeur, n=3)
        eerste[top[0][0].qid] += 1
        top3.update(h.qid for h, _ in top)
    toegestaan = [h for h in heiligen if h.geslacht in VOORKEUR_GESLACHT[voorkeur]]
    return GroepUitslag(voorkeur, n, toegestaan, eerste, top3)


def _vink(ok: bool) -> str:
    return "✅ ja" if ok else "❌ nee"


def rapport(seed: int, n: int, heiligen: list[Heilige], vragen: Vragenbank) -> tuple[str, bool]:
    rng = random.Random(seed)
    groepen = [simuleer_groep(v, n, heiligen, vragen, rng) for v in VOORKEUREN]
    naam = {h.qid: h.naam for h in heiligen}

    per_interesse = Counter(i for h in heiligen for i in h.interesses)
    zijden = {a: (sum(1 for h in heiligen if (h.assen[a] or 0) < 0), sum(1 for h in heiligen if (h.assen[a] or 0) > 0)) for a in ASSEN}

    checks: list[tuple[str, str, bool]] = []
    for g in groepen:
        top_qid, top_n = g.eerste.most_common(1)[0]
        checks.append((f"{g.voorkeur}: geen heilige boven {MAX_AANDEEL_EERSTE:.0%} van de eerste keuzes",
                       f"hoogste: {naam[top_qid]}, {top_n} van {g.n} ({g.max_aandeel:.1%}); gelijk verdeeld {1 / len(g.toegestaan):.1%}, puur toeval haalt {g.ruis(seed):.1%}",
                       g.max_aandeel <= MAX_AANDEEL_EERSTE))
        checks.append((f"{g.voorkeur}: minstens {MIN_DEKKING_TOP3:.0%} van de heiligen ooit in een top-3",
                       f"{len(g.top3)} van {len(g.toegestaan)} ({g.dekking:.0%})",
                       g.dekking >= MIN_DEKKING_TOP3))
    zwak = [i for i in vragen.interesses if per_interesse[i] < MIN_PER_INTERESSE]
    checks.append((f"minstens {MIN_PER_INTERESSE} heiligen per interesse",
                   "allemaal" if not zwak else "te weinig: " + ", ".join(f"{i} ({per_interesse[i]})" for i in zwak),
                   not zwak))
    eenzijdig = [a for a, (mn, pl) in zijden.items() if not (mn and pl)]
    checks.append(("per as heiligen aan beide kanten",
                   "allemaal" if not eenzijdig else "eenzijdig: " + ", ".join(eenzijdig),
                   not eenzijdig))
    alles_ok = all(ok for *_, ok in checks)

    r = [
        "# Simulatie van de matching",
        "",
        f"Gegenereerd door `python -m durfheilig.simulatie --seed {seed} --n {n}`. Zelfde seed, zelfde rapport.",
        "",
        f"{len(heiligen)} heiligen, {n} fictieve profielen per geslachtsvoorkeur. Profielen beantwoorden elke of-of-vraag 50/50 en kiezen 2 of 3 interesses; dat toetst de spreiding, niet of iemand zich herkent. \"Eerste keuze\" is plek 1 van de deterministische ranglijst.",
        "",
        f"**Eindoordeel: {'alle eisen gehaald' if alles_ok else 'niet alle eisen gehaald'}.**",
        "",
        "\"Puur toeval\" is wat een matching haalt die elke deelnemer een willekeurige heilige geeft, bij hetzelfde aantal profielen. Ligt een eis daaronder, dan is hij bij dit aantal profielen niet te halen door ruis alleen, ook niet met een perfecte matching.",
        "",
        "## Eisen uit het plan",
        "",
        "| Eis | Uitkomst | Gehaald |",
        "| --- | --- | --- |",
        *[f"| {e} | {u} | {_vink(ok)} |" for e, u, ok in checks],
        "",
        "## Heiligen die nooit in een top-3 komen",
        "",
    ]
    for g in groepen:
        nooit = sorted(naam[h.qid] for h in g.toegestaan if h.qid not in g.top3)
        r.append(f"- **{g.voorkeur}** ({len(nooit)}): {', '.join(nooit) if nooit else 'geen'}")
    r += ["", "## Per heilige", "",
          "Aantal keer eerste keuze en aantal keer in de top-3, per geslachtsvoorkeur. Gesorteerd op totaal aantal top-3-plekken.", "",
          "| Heilige | Geslacht | Bekende assen | " + " | ".join(f"{g.voorkeur}: 1e / top-3" for g in groepen) + " |",
          "| --- | --- | --- | " + " | ".join("---" for _ in groepen) + " |"]
    for h in sorted(heiligen, key=lambda h: (-sum(g.top3[h.qid] for g in groepen), h.naam)):
        cellen = [f"{g.eerste[h.qid]} / {g.top3[h.qid]}" if h in g.toegestaan else "–" for g in groepen]
        r.append(f"| {h.naam} | {h.geslacht} | {len(h.bekende_assen)} | " + " | ".join(cellen) + " |")
    r += ["", "## De set", "", "| Interesse | Heiligen |", "| --- | --- |",
          *[f"| {i} | {per_interesse[i]} |" for i in vragen.interesses],
          "", "| As | Min-kant | Plus-kant | Onbekend |", "| --- | --- | --- | --- |",
          *[f"| {a} | {mn} | {pl} | {sum(1 for h in heiligen if h.assen[a] is None)} |" for a, (mn, pl) in zijden.items()],
          ""]
    return "\n".join(r), alles_ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "simulatie" / "rapport.md")
    a = ap.parse_args(argv)
    tekst, ok = rapport(a.seed, a.n, laad_heiligen(), laad_vragen())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(tekst, encoding="utf-8")
    print(f"{'alle eisen gehaald' if ok else 'NIET alle eisen gehaald'} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
