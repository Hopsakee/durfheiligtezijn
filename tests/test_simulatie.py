from collections import Counter

from durfheilig.data import laad_heiligen, laad_vragen
from durfheilig.simulatie import GroepUitslag, controleer, rapport


def test_zelfde_seed_zelfde_rapport():
    h, v = laad_heiligen(), laad_vragen()
    assert rapport(7, 40, h, v) == rapport(7, 40, h, v)


def test_rapport_noemt_elke_eis():
    tekst, _ = rapport(7, 40, laad_heiligen(), laad_vragen())
    for groep in ("man", "vrouw", "maakt niet uit"):
        for eis in ("geen heilige boven", "minstens 60%", "heiligen per interesse", "beide kanten"):
            assert any(r.startswith(f"| {groep}: ") and eis in r for r in tekst.splitlines()), (groep, eis)


def _groep(heiligen, eerste, top3):
    return GroepUitslag("vrouw", sum(eerste.values()), heiligen, eerste, top3)


def test_controle_keurt_een_te_geconcentreerde_groep_af():
    h, v = laad_heiligen(), laad_vragen()
    vrouwen = [x for x in h if x.geslacht == "vrouwelijk"]
    scheef = _groep(vrouwen, Counter({vrouwen[0].qid: 50, vrouwen[1].qid: 150}), Counter({vrouwen[0].qid: 1}))
    checks = controleer([scheef], v, 1)
    assert checks[0][2] is False   # 75% first choice > 4%
    assert checks[1][2] is False   # 1 of 31 in a top-3 < 60%


def test_controle_keurt_een_gelijk_verdeelde_groep_goed():
    h, v = laad_heiligen(), laad_vragen()
    vrouwen = [x for x in h if x.geslacht == "vrouwelijk"]
    gelijk = Counter({x.qid: 1 for x in vrouwen})
    checks = controleer([_groep(vrouwen, gelijk, gelijk)], v, 1)
    assert checks[0][2] is True   # each saint 1 of 31 = 3.2% <= 4%
    assert checks[1][2] is True   # 100% coverage


def test_interessecontrole_telt_per_geslacht():
    h, v = laad_heiligen(), laad_vragen()
    # Take away every woman with the technology interest so the check has something to find.
    vrouwen = [x for x in h if x.geslacht == "vrouwelijk" and "Techniek, bouwen en computers" not in x.interesses]
    gelijk = Counter({x.qid: 1 for x in vrouwen})
    eis, uitkomst, ok = controleer([_groep(vrouwen, gelijk, gelijk)], v, 1)[2]
    assert ok is False and "Techniek, bouwen en computers (0)" in uitkomst


def test_interesse_en_assencontrole_tellen_per_groep_niet_over_alles():
    # Two groups side by side: the women's interest and axis checks must use only the women,
    # even though the union with the men would pass.
    h, v = laad_heiligen(), laad_vragen()
    groepen = []
    for vk, gs in (("man", "mannelijk"), ("vrouw", "vrouwelijk")):
        lid = [x for x in h if x.geslacht == gs]
        gelijk = Counter({x.qid: 1 for x in lid})
        groepen.append(GroepUitslag(vk, len(lid), lid, gelijk, gelijk))
    checks = {e: ok for e, _, ok in controleer(groepen, v, 1)}
    assert checks["vrouw: minstens 5 heiligen per interesse"] is False


def test_beide_kanten_controle_keurt_een_eenzijdige_as_af():
    h, v = laad_heiligen(), laad_vragen()
    alleen_plus = [x for x in h if x.geslacht == "vrouwelijk" and (x.assen["plek_pad"] or 0) > 0]
    gelijk = Counter({x.qid: 1 for x in alleen_plus})
    eis, uitkomst, ok = controleer([GroepUitslag("vrouw", len(alleen_plus), alleen_plus, gelijk, gelijk)], v, 1)[3]
    assert ok is False and "plek_pad" in uitkomst
