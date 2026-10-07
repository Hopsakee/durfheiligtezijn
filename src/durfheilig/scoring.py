"""Profile and matching, exactly as `docs/design/rubric.md` specifies.

- Each either-or answer counts -1 (minus pole) or +1 (plus pole) on its axis, so two
  questions per axis give -2, 0 or +2.
- Axis score: mean over the axes both the saint and the profile know of 1 - |kid - saint| / 4.
- Interest score: shared interests / number of the saint's interests.
- Total: 0.7 * axes + 0.3 * interests. The gender filter runs before matching.

Ranking does not use that total directly. Some saints score high for almost everyone: a
saint with one interest gets the full interest score whenever a kid picks it, and a saint
with middling axis scores sits close to every profile. So each saint's total is compared
with what that same saint scores for an average kid (a z-score over all possible answer
patterns), and the ranking asks "how much better than usual does this kid fit this saint".
"""

import hashlib
import itertools
import math
import random
from collections.abc import Iterable, Mapping
from functools import lru_cache

from .data import ASSEN, DataFout, Heilige, Vraag, Vragenbank

GEWICHT_ASSEN = 0.7
GEWICHT_INTERESSES = 0.3
MAX_ANTWOORDEN_PER_AS = 2

VOORKEUR_GESLACHT = {"man": {"mannelijk"}, "vrouw": {"vrouwelijk"}, "maakt niet uit": {"mannelijk", "vrouwelijk"}}


def profiel(antwoorden: Mapping[str, str], vragen: Vragenbank) -> dict[str, int]:
    """Answers map question id -> "min" or "plus". Axes without an answer are absent.

    At most two answers per axis, so every axis score stays within -2..+2 like the saints'.
    """
    per_id = {v.id: v for v in vragen.vragen}
    p: dict[str, int] = {}
    aantal: dict[str, int] = {}
    for vid, kant in antwoorden.items():
        if vid not in per_id:
            raise DataFout(f"onbekende vraag {vid!r}")
        if kant not in ("min", "plus"):
            raise DataFout(f"antwoord op {vid} moet 'min' of 'plus' zijn, niet {kant!r}")
        as_ = per_id[vid].as_
        aantal[as_] = aantal.get(as_, 0) + 1
        if aantal[as_] > MAX_ANTWOORDEN_PER_AS:
            raise DataFout(f"meer dan {MAX_ANTWOORDEN_PER_AS} antwoorden op as {as_}")
        p[as_] = p.get(as_, 0) + (1 if kant == "plus" else -1)
    return p


def assen_score(p: Mapping[str, int], h: Heilige) -> float:
    gedeeld = [a for a in ASSEN if a in p and h.assen[a] is not None]
    if not gedeeld:
        return 0.0
    return sum(1 - abs(p[a] - h.assen[a]) / 4 for a in gedeeld) / len(gedeeld)


def interesse_score(interesses: Iterable[str], h: Heilige) -> float:
    return len(set(interesses) & set(h.interesses)) / len(h.interesses)


def match_score(p: Mapping[str, int], interesses: Iterable[str], h: Heilige) -> float:
    return GEWICHT_ASSEN * assen_score(p, h) + GEWICHT_INTERESSES * interesse_score(interesses, h)


# The reference "average kid": two 50/50 answers per axis (-2, 0, +2 with chance 1/4, 1/2, 1/4)
# and 2 or 3 interests (50/50) picked uniformly from the list.
# The reference assumes all six axes are answered, as the quiz always does (two questions per
# axis). Ranking a half-finished profile against it would shift the relative scores.
_AS_KANS = {-2: 0.25, 0: 0.5, 2: 0.25}
_PROFIELEN = [
    (dict(zip(ASSEN, waarden)), math.prod(_AS_KANS[w] for w in waarden))
    for waarden in itertools.product(_AS_KANS, repeat=len(ASSEN))
]


@lru_cache(maxsize=None)
def _referentie(assen: tuple, interesses: tuple, interesse_lijst: tuple) -> tuple[float, float]:
    h = Heilige("ref", "ref", "mannelijk", dict(assen), interesses, {})
    m_as = sum(w * assen_score(p, h) for p, w in _PROFIELEN)
    v_as = sum(w * (assen_score(p, h) - m_as) ** 2 for p, w in _PROFIELEN)
    per_k = []
    for k in (2, 3):
        scores = [interesse_score(c, h) for c in itertools.combinations(interesse_lijst, k)]
        per_k.append(scores)
    m_int = sum(sum(s) / len(s) for s in per_k) / 2
    v_int = sum(sum((x - m_int) ** 2 for x in s) / len(s) for s in per_k) / 2
    gemiddeld = GEWICHT_ASSEN * m_as + GEWICHT_INTERESSES * m_int
    spreiding = math.sqrt(GEWICHT_ASSEN**2 * v_as + GEWICHT_INTERESSES**2 * v_int)
    return gemiddeld, spreiding


def relatieve_score(p: Mapping[str, int], interesses: Iterable[str], h: Heilige, interesse_lijst: Iterable[str]) -> float:
    """How many standard deviations this kid's fit with `h` lies above an average kid's fit with `h`."""
    gemiddeld, spreiding = _referentie(tuple(sorted(h.assen.items())), h.interesses, tuple(interesse_lijst))
    return (match_score(p, interesses, h) - gemiddeld) / spreiding


def _tiebreak(p: Mapping[str, int], interesses: Iterable[str], qid: str) -> str:
    # Equal scores are common with integer axes. Break ties by a hash of the whole input,
    # so no saint wins ties because of its name or its position in the file.
    sleutel = repr((sorted(p.items()), sorted(interesses), qid))
    return hashlib.sha256(sleutel.encode()).hexdigest()


def rangschik(
    p: Mapping[str, int],
    interesses: Iterable[str],
    heiligen: Iterable[Heilige],
    voorkeur: str = "maakt niet uit",
    uitsluiten: Iterable[str] = (),
    n: int | None = 12,
    *,
    interesse_lijst: Iterable[str],
) -> list[tuple[Heilige, float]]:
    """Top-n saints for a profile, as (saint, match score 0..1), ranked by relative score.

    `uitsluiten` holds qids already chosen by other players. `interesse_lijst` is the full list
    of interests the kid could pick from; it defines the average kid.
    """
    interesses = list(interesses)
    heiligen = list(heiligen)
    lijst = tuple(interesse_lijst)
    if len(lijst) < 3:
        raise ValueError("interesse_lijst moet de volledige lijst zijn waaruit gekozen wordt")
    toegestaan = VOORKEUR_GESLACHT[voorkeur]
    weg = set(uitsluiten)
    kandidaten = [h for h in heiligen if h.geslacht in toegestaan and h.qid not in weg]
    gescoord = [(h, match_score(p, interesses, h), relatieve_score(p, interesses, h, lijst)) for h in kandidaten]
    gescoord.sort(key=lambda x: (-round(x[2], 9), _tiebreak(p, interesses, x[0].qid)))
    gescoord = [(h, s) for h, s, _ in gescoord]
    return gescoord if n is None else gescoord[:n]


def kies_vragen(vragen: Vragenbank, rng: random.Random, per_as: int = 2) -> list[Vraag]:
    """Draw `per_as` questions per axis, in axis order."""
    return [v for a in ASSEN for v in rng.sample(vragen.per_as(a), per_as)]
