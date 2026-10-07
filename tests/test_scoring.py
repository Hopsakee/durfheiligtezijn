import random
from collections import Counter

import pytest

from durfheilig.data import ASSEN, Heilige, laad_heiligen, laad_vragen
from durfheilig.scoring import kies_vragen, match_score, profiel, rangschik


@pytest.fixture(scope="module")
def heiligen():
    return laad_heiligen()


@pytest.fixture(scope="module")
def vragen():
    return laad_vragen()


def maak(qid, assen, interesses, geslacht="mannelijk", naam=None):
    return Heilige(qid, naam or qid, geslacht, {a: assen.get(a) for a in ASSEN}, tuple(interesses), {})


@pytest.mark.parametrize("kanten,verwacht", [(("min", "min"), -2), (("min", "plus"), 0), (("plus", "min"), 0), (("plus", "plus"), 2)])
def test_twee_antwoorden_per_as_geven_min2_0_of_plus2(vragen, kanten, verwacht):
    v1, v2 = vragen.per_as("plek_pad")[:2]
    assert profiel({v1.id: kanten[0], v2.id: kanten[1]}, vragen) == {"plek_pad": verwacht}


def test_as_zonder_antwoord_ontbreekt_in_profiel(vragen):
    v = vragen.per_as("denken_doen")[0]
    assert set(profiel({v.id: "plus"}, vragen)) == {"denken_doen"}


def test_matchformule_met_de_hand_berekend():
    # Saint known on 4 axes; the kid knows all 6.
    h = maak("Q1", {"samen_alleen": 2, "denken_doen": -2, "achter_voorop": 0, "plek_pad": 1},
             ["Mensen helpen", "Lezen en schrijven", "Muziek en kunst"])
    p = {"samen_alleen": 2, "denken_doen": 2, "achter_voorop": -2, "plek_pad": 0, "diepgang_licht": 2, "vrede_strijd": -2}
    # Axes: (1 - 0/4) + (1 - 4/4) + (1 - 2/4) + (1 - 1/4) = 1 + 0 + 0.5 + 0.75 = 2.25, over 4 -> 0.5625
    # Interests: 1 shared of the saint's 3 -> 1/3
    verwacht = 0.7 * 0.5625 + 0.3 * (1 / 3)
    assert match_score(p, ["Mensen helpen", "Sport en buiten bewegen"], h) == pytest.approx(verwacht)


def test_onbekende_as_telt_niet_mee():
    p = {"samen_alleen": 2, "denken_doen": 2}
    bekend = maak("Q1", {"samen_alleen": 2, "denken_doen": None, "achter_voorop": 0, "plek_pad": 0, "diepgang_licht": 0}, ["Mensen helpen"])
    # Only samen_alleen is known by both -> axes score 1.0; a 0 on denken_doen would have given 0.75.
    assert match_score(p, [], bekend) == pytest.approx(0.7)


@pytest.mark.parametrize("voorkeur,toegestaan", [("man", {"mannelijk"}), ("vrouw", {"vrouwelijk"}), ("maakt niet uit", {"mannelijk", "vrouwelijk"})])
def test_geslachtsfilter_voor_matching(heiligen, voorkeur, toegestaan):
    p = {a: 0 for a in ASSEN}
    alles = rangschik(p, [], heiligen, voorkeur, n=None)
    assert {h.geslacht for h, _ in alles} == toegestaan
    assert len(alles) == sum(h.geslacht in toegestaan for h in heiligen)


def test_al_gekozen_heiligen_komen_nooit_in_de_top(heiligen, vragen):
    rng = random.Random(1)
    for _ in range(50):
        p = profiel({v.id: rng.choice(("min", "plus")) for v in kies_vragen(vragen, rng)}, vragen)
        interesses = rng.sample(vragen.interesses, 3)
        vrij = rangschik(p, interesses, heiligen, n=5)
        weg = [h.qid for h, _ in vrij[:3]]
        opnieuw = rangschik(p, interesses, heiligen, uitsluiten=weg, n=12)
        assert not {h.qid for h, _ in opnieuw} & set(weg)


def test_gelijke_scores_niet_beslist_op_naam_of_volgorde():
    # Twenty saints with identical scores: across many profiles the winner must vary,
    # and neither the alphabetically first nor the first in the list may win them all.
    gelijk = [maak(f"Q{i}", {a: 0 for a in ASSEN}, ["Mensen helpen"], naam=f"Heilige {i:02d}") for i in range(20)]
    winnaars = Counter()
    for k in range(200):
        p = {"samen_alleen": k % 5 - 2, "denken_doen": (k // 5) % 5 - 2, "plek_pad": (k // 25) % 5 - 2}
        winnaars[rangschik(p, ["Mensen helpen"], gelijk, n=1)[0][0].qid] += 1
    assert len(winnaars) >= 15
    assert max(winnaars.values()) < 40


def test_rangschikking_is_deterministisch(heiligen):
    p = {a: 0 for a in ASSEN}
    assert rangschik(p, ["Mensen helpen"], heiligen) == rangschik(p, ["Mensen helpen"], list(reversed(heiligen)))


def test_kies_vragen_twee_per_as(vragen):
    gekozen = kies_vragen(vragen, random.Random(3))
    assert len(gekozen) == 12
    assert Counter(v.as_ for v in gekozen) == {a: 2 for a in ASSEN}
