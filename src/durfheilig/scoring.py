"""Profile and matching, exactly as `docs/design/rubric.md` specifies.

- Each either-or answer counts -1 (minus pole) or +1 (plus pole) on its axis, so two
  questions per axis give -2, 0 or +2.
- Axis score: mean over the axes both the saint and the profile know of 1 - |kid - saint| / 4.
- Interest score: shared interests / number of the saint's interests.
- Total: 0.7 * axes + 0.3 * interests. The gender filter runs before matching.
"""

import hashlib
import random
from collections.abc import Iterable, Mapping

from .data import ASSEN, Heilige, Vraag, Vragenbank

GEWICHT_ASSEN = 0.7
GEWICHT_INTERESSES = 0.3

VOORKEUR_GESLACHT = {"man": {"mannelijk"}, "vrouw": {"vrouwelijk"}, "maakt niet uit": {"mannelijk", "vrouwelijk"}}


def profiel(antwoorden: Mapping[str, str], vragen: Vragenbank) -> dict[str, int]:
    """Answers map question id -> "min" or "plus". Axes without an answer are absent."""
    per_id = {v.id: v for v in vragen.vragen}
    p: dict[str, int] = {}
    for vid, kant in antwoorden.items():
        if kant not in ("min", "plus"):
            raise ValueError(f"antwoord op {vid} moet 'min' of 'plus' zijn, niet {kant!r}")
        as_ = per_id[vid].as_
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
) -> list[tuple[Heilige, float]]:
    """Top-n saints for a profile. `uitsluiten` holds qids already chosen by other players."""
    interesses = list(interesses)
    toegestaan = VOORKEUR_GESLACHT[voorkeur]
    weg = set(uitsluiten)
    kandidaten = [h for h in heiligen if h.geslacht in toegestaan and h.qid not in weg]
    gescoord = [(h, match_score(p, interesses, h)) for h in kandidaten]
    gescoord.sort(key=lambda hs: (-round(hs[1], 9), _tiebreak(p, interesses, hs[0].qid)))
    return gescoord if n is None else gescoord[:n]


def kies_vragen(vragen: Vragenbank, rng: random.Random, per_as: int = 2) -> list[Vraag]:
    """Draw `per_as` questions per axis, in axis order."""
    return [v for a in ASSEN for v in rng.sample(vragen.per_as(a), per_as)]
