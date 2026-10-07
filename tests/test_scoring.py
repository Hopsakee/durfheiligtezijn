import random
from collections import Counter

import pytest

import itertools
import math

from durfheilig.data import ASSEN, DataFout, Heilige, laad_heiligen, laad_vragen
from durfheilig.scoring import _AS_KANS, _PROFIELEN, kies_vragen, match_score, profiel, rangschik, relatieve_score


@pytest.fixture(scope="module")
def heiligen():
    return laad_heiligen()


@pytest.fixture(scope="module")
def vragen():
    return laad_vragen()


LIJST = tuple(laad_vragen().interesses)


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
    alles = rangschik(p, [], heiligen, voorkeur, n=None, interesse_lijst=LIJST)
    assert {h.geslacht for h, _ in alles} == toegestaan
    assert len(alles) == sum(h.geslacht in toegestaan for h in heiligen)


def test_al_gekozen_heiligen_komen_nooit_in_de_top(heiligen, vragen):
    rng = random.Random(1)
    for _ in range(50):
        p = profiel({v.id: rng.choice(("min", "plus")) for v in kies_vragen(vragen, rng)}, vragen)
        interesses = rng.sample(vragen.interesses, 3)
        vrij = rangschik(p, interesses, heiligen, n=5, interesse_lijst=LIJST)
        weg = [h.qid for h, _ in vrij[:3]]
        opnieuw = rangschik(p, interesses, heiligen, uitsluiten=weg, n=12, interesse_lijst=LIJST)
        assert not {h.qid for h, _ in opnieuw} & set(weg)
        assert len(opnieuw) == 12


def test_gelijke_scores_niet_beslist_op_naam_of_volgorde():
    # Twenty saints with identical scores: across many profiles the winner must vary,
    # and neither the alphabetically first nor the first in the list may win them all.
    gelijk = [maak(f"Q{i}", {a: 0 for a in ASSEN}, ["Mensen helpen"], naam=f"Heilige {i:02d}") for i in range(20)]
    winnaars = Counter()
    for k in range(200):
        p = {"samen_alleen": k % 5 - 2, "denken_doen": (k // 5) % 5 - 2, "plek_pad": (k // 25) % 5 - 2}
        winnaars[rangschik(p, ["Mensen helpen"], gelijk, n=1, interesse_lijst=LIJST)[0][0].qid] += 1
    assert len(winnaars) >= 15
    assert max(winnaars.values()) < 40


def test_rangschikking_is_deterministisch(heiligen):
    p = {a: 0 for a in ASSEN}
    assert rangschik(p, ["Mensen helpen"], heiligen, interesse_lijst=LIJST) == rangschik(p, ["Mensen helpen"], list(reversed(heiligen)), interesse_lijst=LIJST)


def test_kies_vragen_twee_per_as(vragen):
    gekozen = kies_vragen(vragen, random.Random(3))
    assert len(gekozen) == 12
    assert Counter(v.as_ for v in gekozen) == {a: 2 for a in ASSEN}


def test_onbekende_vraag_geeft_duidelijke_fout(vragen):
    with pytest.raises(DataFout, match="onbekende vraag"):
        profiel({"zz9": "plus"}, vragen)


def test_meer_dan_twee_antwoorden_per_as_geweigerd(vragen):
    drie = {v.id: "plus" for v in vragen.per_as("plek_pad")[:3]}
    with pytest.raises(DataFout, match="meer dan 2 antwoorden op as plek_pad"):
        profiel(drie, vragen)


@pytest.mark.parametrize("voorkeur,geslacht", [("vrouw", "vrouwelijk"), ("man", "mannelijk")])
def test_filter_en_uitsluiten_voor_het_afkappen(heiligen, voorkeur, geslacht):
    # Exclude five saints of the requested gender: a filter-after-slice implementation would return fewer than 12.
    weg = [h.qid for h in heiligen if h.geslacht == geslacht][:5]
    top = rangschik({a: 0 for a in ASSEN}, ["Mensen helpen"], heiligen, voorkeur, uitsluiten=weg, n=12, interesse_lijst=LIJST)
    assert len(top) == 12
    assert all(h.geslacht == geslacht and h.qid not in weg for h, _ in top)


def test_relatieve_score_is_gecentreerd_voor_een_gemiddeld_kind(heiligen):
    # Over the reference distribution (every answer pattern, every 2- or 3-interest pick)
    # each saint's relative score has mean 0 and standard deviation 1.
    keuzes = [(list(c), 0.5 / math.comb(len(LIJST), k)) for k in (2, 3) for c in itertools.combinations(LIJST, k)]
    for h in heiligen[:3] + [h for h in heiligen if len(h.interesses) == 1][:2]:
        m = v = 0.0
        for p, wp in _PROFIELEN:
            for i, wi in keuzes:
                z = relatieve_score(p, i, h, LIJST)
                m += wp * wi * z
                v += wp * wi * z * z
        assert m == pytest.approx(0, abs=1e-9), h.naam
        assert v == pytest.approx(1, abs=1e-9), h.naam


def test_centreren_haalt_de_voorsprong_van_een_heilige_met_een_interesse_weg():
    # Two saints with identical axes; one has a single interest, the other three.
    # Under the raw formula the single-interest saint wins every profile that picks its
    # interest; after centring the three-interest saint wins when the kid shares more of hers.
    een = maak("Q1", {a: 0 for a in ASSEN}, ["Mensen helpen"])
    drie = maak("Q2", {a: 0 for a in ASSEN}, ["Mensen helpen", "Lezen en schrijven", "Muziek en kunst"])
    p, kind = {a: 0 for a in ASSEN}, ["Mensen helpen", "Lezen en schrijven", "Muziek en kunst"]
    assert match_score(p, kind, een) == match_score(p, kind, drie)
    assert rangschik(p, kind, [een, drie], n=1, interesse_lijst=LIJST)[0][0].qid == "Q2"


def test_antwoord_anders_dan_min_of_plus_geweigerd(vragen):
    v = vragen.per_as("plek_pad")[0]
    with pytest.raises(DataFout, match="'min' of 'plus'"):
        profiel({v.id: "ja"}, vragen)
