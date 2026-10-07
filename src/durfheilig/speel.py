"""Play the quiz in the terminal, to try the questions and the matching yourself.

    python -m durfheilig.speel [--seed N]

Asks the gender preference, 12 either-or questions (2 per axis, drawn from 4) and 2 or 3
interests, then prints the top-3 and the rest of the top-12. No LLM: that comes in phase 4.
"""

import argparse
import random
import sys

from .data import laad_heiligen, laad_vragen
from .scoring import VOORKEUR_GESLACHT, kies_vragen, profiel, rangschik


def vraag(prompt: str, geldig: set[str]) -> str:
    while True:
        print(prompt, end="", flush=True)
        regel = sys.stdin.readline()
        if not regel:
            raise SystemExit("\nGestopt.")
        regel = regel.strip().lower()
        if regel in geldig:
            return regel
        print(f"  Kies uit: {', '.join(sorted(geldig))}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=None, help="vaste vragenkeuze, handig om te herhalen")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    heiligen, vragen = laad_heiligen(), laad_vragen()

    print("Mag je heilige een man, een vrouw, of maakt het niet uit?")
    voorkeuren = list(VOORKEUR_GESLACHT)
    for i, v in enumerate(voorkeuren, 1):
        print(f"  {i}. {v}")
    voorkeur = voorkeuren[int(vraag("> ", {"1", "2", "3"})) - 1]

    antwoorden = {}
    for i, v in enumerate(kies_vragen(vragen, rng), 1):
        print(f"\n{i}/12  {v.vraag}")
        print(f"  a. {v.min['icoon']} {v.min['tekst']}")
        print(f"  b. {v.plus['icoon']} {v.plus['tekst']}")
        antwoorden[v.id] = "min" if vraag("> ", {"a", "b"}) == "a" else "plus"

    iv = vragen.interessevraag
    print(f"\n{iv['vraag']} Typ de nummers, gescheiden door spaties.")
    for i, o in enumerate(iv["opties"], 1):
        print(f"  {i:2}. {o['icoon']} {o['interesse']}")
    while True:
        print("> ", end="", flush=True)
        regel = sys.stdin.readline()
        if not regel:
            raise SystemExit("\nGestopt.")
        try:
            keuzes = sorted({int(x) for x in regel.split()})
        except ValueError:
            keuzes = []
        if iv["min_keuzes"] <= len(keuzes) <= iv["max_keuzes"] and all(1 <= k <= len(iv["opties"]) for k in keuzes):
            break
        print(f"  Kies {iv['min_keuzes']} of {iv['max_keuzes']} nummers tussen 1 en {len(iv['opties'])}.")
    interesses = [iv["opties"][k - 1]["interesse"] for k in keuzes]

    p = profiel(antwoorden, vragen)
    top = rangschik(p, interesses, heiligen, voorkeur, n=12)
    print("\nJouw profiel: " + ", ".join(f"{a} {s:+d}" for a, s in p.items()))
    print("\nTop-3:")
    for i, (h, s) in enumerate(top[:3], 1):
        print(f"  {i}. {h.naam} ({s:.2f})\n     {h.record.get('wat_voor_mens', '')}")
    print("\nPlek 4 tot 12: " + ", ".join(f"{h.naam} ({s:.2f})" for h, s in top[3:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
